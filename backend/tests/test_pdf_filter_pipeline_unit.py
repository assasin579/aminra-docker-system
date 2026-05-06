"""Unit tests for services/pdf_filter_pipeline.py.

Each filter is a pure function — synthetic RawDataBundle in, RenderContext
out. No DB, no I/O. Tests should run in milliseconds.

Critical invariants:
  - SourceMergeFilter precedence: admin_defaults < company < submission < payload
  - FormatFilter is locale-aware (vi/en) and idempotent on already-formatted values
  - TruncationFilter caps lengths but logs (does not silently mangle)
  - WatermarkFilter only flips the cfg flag; templates handle visual
  - Pipeline runs filters in declared order; failures bubble up
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from services.pdf_data_aggregator import (
    AdminAssets,
    CompanyData,
    ProductData,
    RawDataBundle,
    ResponsiblePerson,
    SubmissionData,
)
from services.pdf_filter_pipeline import (
    FilterPipeline,
    FormatFilter,
    PlaceholderFillerFilter,
    RenderContext,
    SourceMergeFilter,
    TruncationFilter,
    ValidationFilter,
    WatermarkFilter,
)


# ── Bundle factory ─────────────────────────────────────────────────────────


def make_bundle(
    *,
    payload: dict | None = None,
    company: CompanyData | None = None,
    submission: SubmissionData | None = None,
    admin_cfg: dict | None = None,
    is_draft: bool = True,
    lang: str = "vi",
    doc_type: str = "company_profile",
) -> RawDataBundle:
    return RawDataBundle(
        doc_type=doc_type,
        tenant_id="t-A",
        actor_id="actor",
        actor_role="business",
        request_payload=payload or {},
        request_lang=lang,
        is_draft=is_draft,
        company=company,
        active_submission=submission,
        admin_cfg=admin_cfg or {},
        admin_assets=AdminAssets(),
    )


def empty_ctx(bundle: RawDataBundle) -> RenderContext:
    return RenderContext(
        doc_type=bundle.doc_type,
        title="Test",
        title_default="Test default",
        is_draft=bundle.is_draft,
        lang=bundle.request_lang,
        cfg=dict(bundle.admin_cfg),
    )


# ── ValidationFilter ───────────────────────────────────────────────────────


class TestValidationFilter:
    def test_valid_payload_populates_data(self):
        b = make_bundle(payload={
            "business_name": "ABC Co",
            "issued_date": "2026-05-05",
        })
        ctx = ValidationFilter().apply(b, empty_ctx(b))
        assert ctx.data["business_name"] == "ABC Co"

    def test_invalid_payload_raises(self):
        b = make_bundle(payload={"issued_date": "2026-05-05"})  # missing business_name
        with pytest.raises(ValidationError):
            ValidationFilter().apply(b, empty_ctx(b))

    def test_unimplemented_doc_type_passes_through(self):
        # When schema is not registered (None), filter doesn't crash —
        # downstream router returns 501 with a clear message.
        b = make_bundle(payload={"any": 1}, doc_type="ingredient_raw_material")  # Group 3 — not yet
        ctx = ValidationFilter().apply(b, empty_ctx(b))
        assert ctx.data == {"any": 1}


# ── SourceMergeFilter ──────────────────────────────────────────────────────


class TestSourceMergeFilter:
    def test_merge_company_into_data(self):
        company = CompanyData(
            business_name="From DB",
            tax_code="0123456789",
            address="DB address",
        )
        b = make_bundle(
            payload={"business_name": "From DB", "issued_date": "2026-05-05"},
            company=company,
        )
        ctx = empty_ctx(b)
        ctx.data = {}              # simulate after Validation skipped/empty
        merged = SourceMergeFilter().apply(b, ctx)
        assert merged.data["business_name"] == "From DB"
        assert merged.data["tax_code"] == "0123456789"
        assert merged.data["address"] == "DB address"

    def test_payload_overrides_company(self):
        company = CompanyData(business_name="DB Name", address="DB Address")
        b = make_bundle(
            payload={
                "business_name": "Payload Name",
                "issued_date": "2026-05-05",
            },
            company=company,
        )
        ctx = empty_ctx(b)
        ctx.data = {"business_name": "Payload Name", "issued_date": "2026-05-05"}
        merged = SourceMergeFilter().apply(b, ctx)
        assert merged.data["business_name"] == "Payload Name"  # payload wins
        assert merged.data["address"] == "DB Address"          # only DB has

    def test_admin_defaults_lowest_precedence(self):
        b = make_bundle(
            payload={"business_name": "Payload"},
            company=CompanyData(business_name="DB"),
            admin_cfg={"defaults": {"business_name": "Admin", "extra_field": "from_admin"}},
        )
        ctx = empty_ctx(b)
        ctx.data = {"business_name": "Payload"}
        merged = SourceMergeFilter().apply(b, ctx)
        assert merged.data["business_name"] == "Payload"
        assert merged.data["extra_field"] == "from_admin"  # admin defaults preserved

    def test_submission_products_merged(self):
        sub = SubmissionData(
            id="sub-1",
            status="evaluating",
            products=[
                ProductData(name="Product A", description="desc", annual_output="100t"),
            ],
            business_activities=["Activity 1", "Activity 2"],
            halal_commitment="We commit.",
        )
        b = make_bundle(payload={"business_name": "X"}, submission=sub)
        ctx = empty_ctx(b)
        ctx.data = {"business_name": "X"}
        merged = SourceMergeFilter().apply(b, ctx)
        assert len(merged.data["products"]) == 1
        assert merged.data["products"][0]["name"] == "Product A"
        assert merged.data["business_activities"] == ["Activity 1", "Activity 2"]
        assert merged.data["halal_commitment"] == "We commit."

    def test_issued_date_default_to_today(self):
        b = make_bundle(payload={"business_name": "X"})
        ctx = empty_ctx(b)
        ctx.data = {"business_name": "X"}
        merged = SourceMergeFilter().apply(b, ctx)
        assert merged.data["issued_date"] == date.today().isoformat()


# ── FormatFilter ───────────────────────────────────────────────────────────


class TestFormatFilter:
    def test_date_vi_iso_to_dd_mm_yyyy(self):
        b = make_bundle(lang="vi")
        ctx = empty_ctx(b)
        ctx.data = {"issued_date": "2026-05-05"}
        out = FormatFilter().apply(b, ctx)
        assert out.data["issued_date"] == "05/05/2026"

    def test_date_en_format(self):
        b = make_bundle(lang="en")
        ctx = empty_ctx(b)
        ctx.data = {"issued_date": "2026-05-05"}
        out = FormatFilter().apply(b, ctx)
        assert out.data["issued_date"] == "May 05, 2026"

    def test_date_invalid_passes_through(self):
        b = make_bundle()
        ctx = empty_ctx(b)
        ctx.data = {"issued_date": "not-a-date"}
        out = FormatFilter().apply(b, ctx)
        assert out.data["issued_date"] == "not-a-date"

    def test_date_object_input(self):
        b = make_bundle()
        ctx = empty_ctx(b)
        ctx.data = {"issued_date": date(2026, 12, 25)}
        out = FormatFilter().apply(b, ctx)
        assert out.data["issued_date"] == "25/12/2026"

    def test_phone_intl_grouped(self):
        b = make_bundle()
        ctx = empty_ctx(b)
        ctx.data = {"phone": "+842381234567"}
        out = FormatFilter().apply(b, ctx)
        assert out.data["phone"] == "+84 238 1234 567"

    def test_phone_local_grouped(self):
        b = make_bundle()
        ctx = empty_ctx(b)
        ctx.data = {"phone": "0238 1234 567"}
        out = FormatFilter().apply(b, ctx)
        # Already had spaces — normalised then re-grouped
        assert "0238" in out.data["phone"]
        assert "1234" in out.data["phone"]
        assert "567" in out.data["phone"]

    def test_currency_raw_digits_vi(self):
        b = make_bundle(lang="vi")
        ctx = empty_ctx(b)
        ctx.data = {"charter_capital": "12000000000"}
        out = FormatFilter().apply(b, ctx)
        assert out.data["charter_capital"] == "12.000.000.000 VND"

    def test_currency_already_formatted_passthrough(self):
        b = make_bundle(lang="vi")
        ctx = empty_ctx(b)
        ctx.data = {"charter_capital": "12.000.000.000 VND"}
        out = FormatFilter().apply(b, ctx)
        assert out.data["charter_capital"] == "12.000.000.000 VND"

    def test_format_doesnt_touch_unrelated_keys(self):
        b = make_bundle()
        ctx = empty_ctx(b)
        ctx.data = {"business_name": "Co.,Ltd", "issued_date": "2026-05-05"}
        out = FormatFilter().apply(b, ctx)
        assert out.data["business_name"] == "Co.,Ltd"


# ── TruncationFilter ───────────────────────────────────────────────────────


class TestTruncationFilter:
    def test_long_title_truncated(self, caplog):
        b = make_bundle()
        ctx = empty_ctx(b)
        ctx.title = "X" * 200
        out = TruncationFilter().apply(b, ctx)
        assert len(out.title) <= 80
        assert out.title.endswith("…")

    def test_short_title_unchanged(self):
        b = make_bundle()
        ctx = empty_ctx(b)
        ctx.title = "Short title"
        out = TruncationFilter().apply(b, ctx)
        assert out.title == "Short title"

    def test_long_address_truncated(self):
        b = make_bundle()
        ctx = empty_ctx(b)
        ctx.data = {"address": "A" * 400}
        out = TruncationFilter().apply(b, ctx)
        assert len(out.data["address"]) <= 200
        assert out.data["address"].endswith("…")

    def test_non_string_field_skipped(self):
        b = make_bundle()
        ctx = empty_ctx(b)
        ctx.data = {"address": None}
        out = TruncationFilter().apply(b, ctx)
        assert out.data["address"] is None


# ── PlaceholderFillerFilter ────────────────────────────────────────────────


class TestPlaceholderFillerFilter:
    def test_fills_empty_fields_from_curated_data(self):
        b = make_bundle(doc_type="company_profile")
        ctx = empty_ctx(b)
        ctx.data = {"business_name": "Verify"}     # only required field
        out = PlaceholderFillerFilter().apply(b, ctx)
        # Address / phone / etc. were missing → filled with placeholder
        assert out.data["address"]
        assert out.data["phone"]
        assert "halal_commitment" in out.data
        # business_name is PROTECTED — stays as user data
        assert out.data["business_name"] == "Verify"

    def test_real_data_wins_over_placeholder(self):
        b = make_bundle(doc_type="company_profile")
        ctx = empty_ctx(b)
        ctx.data = {
            "business_name": "Verify",
            "address": "Số 99 Real Street",          # real
            "phone": "0987654321",                    # real
        }
        out = PlaceholderFillerFilter().apply(b, ctx)
        assert out.data["address"] == "Số 99 Real Street"     # NOT overridden
        assert out.data["phone"] == "0987654321"               # NOT overridden

    def test_protected_keys_never_replaced(self):
        """business_name, *_date are NEVER touched even if empty."""
        b = make_bundle(doc_type="company_profile")
        ctx = empty_ctx(b)
        ctx.data = {"business_name": ""}             # empty string — still protected
        out = PlaceholderFillerFilter().apply(b, ctx)
        assert out.data["business_name"] == ""        # untouched

    def test_disable_via_cfg_flag(self):
        b = make_bundle(doc_type="company_profile")
        ctx = empty_ctx(b)
        ctx.cfg["disable_placeholder_filler"] = True
        ctx.data = {"business_name": "X"}
        out = PlaceholderFillerFilter().apply(b, ctx)
        assert "address" not in out.data              # nothing filled

    def test_unknown_doc_type_no_op(self):
        b = make_bundle(doc_type="totally_made_up")
        ctx = empty_ctx(b)
        ctx.data = {"business_name": "X"}
        out = PlaceholderFillerFilter().apply(b, ctx)
        assert out.data == {"business_name": "X"}      # no fallback exists

    def test_filled_fields_telemetry(self):
        b = make_bundle(doc_type="company_profile")
        ctx = empty_ctx(b)
        ctx.data = {"business_name": "Verify"}
        out = PlaceholderFillerFilter().apply(b, ctx)
        filled = out.cfg.get("_placeholder_filled_fields") or []
        assert isinstance(filled, list)
        assert len(filled) > 0
        assert "business_name" not in filled            # protected, not in list

    def test_sop_variants_use_per_type_purpose(self):
        """Different SOPs get different purpose text from placeholder data."""
        ctx_a = empty_ctx(make_bundle(doc_type="sop_raw_material_receiving"))
        ctx_a.data = {"business_name": "X"}
        out_a = PlaceholderFillerFilter().apply(
            make_bundle(doc_type="sop_raw_material_receiving"), ctx_a,
        )
        ctx_b = empty_ctx(make_bundle(doc_type="sop_complaint_recall"))
        ctx_b.data = {"business_name": "X"}
        out_b = PlaceholderFillerFilter().apply(
            make_bundle(doc_type="sop_complaint_recall"), ctx_b,
        )
        assert out_a.data["purpose"] != out_b.data["purpose"]
        assert "nguyên liệu" in out_a.data["purpose"].lower()
        assert "khiếu nại" in out_b.data["purpose"].lower() or "thu hồi" in out_b.data["purpose"].lower()

    def test_halal_manual_aliases_has_manual(self):
        for dt in ("has_manual", "halal_manual"):
            b = make_bundle(doc_type=dt)
            ctx = empty_ctx(b)
            ctx.data = {"business_name": "X"}
            out = PlaceholderFillerFilter().apply(b, ctx)
            assert out.data["introduction"]
            assert out.data["chapters"]


# ── WatermarkFilter ────────────────────────────────────────────────────────


class TestWatermarkFilter:
    def test_draft_sets_label(self):
        b = make_bundle(is_draft=True)
        ctx = empty_ctx(b)
        out = WatermarkFilter().apply(b, ctx)
        assert out.cfg.get("watermark_label") == "DRAFT"
        assert out.layout.show_watermark is True

    def test_non_draft_no_watermark(self):
        b = make_bundle(is_draft=False)
        ctx = empty_ctx(b)
        ctx.is_draft = False
        out = WatermarkFilter().apply(b, ctx)
        assert "watermark_label" not in out.cfg
        assert out.layout.show_watermark is False


# ── FilterPipeline ─────────────────────────────────────────────────────────


class TestPipeline:
    def test_runs_filters_in_order(self):
        b = make_bundle(payload={
            "business_name": "ABC Co",
            "issued_date": "2026-05-05",
        })
        pipeline = FilterPipeline()
        ctx = pipeline.run(b, title="My Doc", title_default="default")
        # All 6 default filters applied in declared order
        assert ctx.filters_applied == [
            "validation", "source_merge", "placeholder_filler",
            "format", "truncation", "watermark",
        ]

    def test_telemetry_durations_recorded(self):
        b = make_bundle(payload={
            "business_name": "X",
            "issued_date": "2026-05-05",
        })
        ctx = FilterPipeline().run(b, title="t", title_default="td")
        # Each filter has a non-negative duration_ms entry
        for name in ctx.filters_applied:
            assert name in ctx.filter_durations_ms
            assert ctx.filter_durations_ms[name] >= 0

    def test_pipeline_propagates_validation_error(self):
        b = make_bundle(payload={})  # missing required business_name
        with pytest.raises(ValidationError):
            FilterPipeline().run(b, title="t", title_default="td")

    def test_end_to_end_format_visible(self):
        """Full pipeline: payload date ISO → final ctx.data has vi-VN format."""
        b = make_bundle(
            payload={"business_name": "X", "issued_date": "2026-05-05",
                     "phone": "+842381234567"},
            lang="vi",
        )
        ctx = FilterPipeline().run(b, title="t", title_default="td")
        assert ctx.data["issued_date"] == "05/05/2026"
        assert ctx.data["phone"] == "+84 238 1234 567"

    def test_custom_filter_subset(self):
        """Custom pipeline: only Validation+Format runs."""
        b = make_bundle(
            payload={"business_name": "X", "issued_date": "2026-05-05"},
            lang="vi",
        )
        pipeline = FilterPipeline(filters=[ValidationFilter(), FormatFilter()])
        ctx = pipeline.run(b, title="t", title_default="td")
        assert ctx.filters_applied == ["validation", "format"]
        assert ctx.data["issued_date"] == "05/05/2026"
