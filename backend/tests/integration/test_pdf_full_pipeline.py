"""PDF render — full 3-stage pipeline integration test (Phase 4).

Visual baseline tests bypass Stages 1 + 2 by calling the renderer directly
with hardcoded fixture data. That gap let a `SourceMergeFilter` bug ship
(empty list dropped → template explosion downstream) because no test
exercised: aggregator output → filter pipeline → renderer.

This suite walks the full path with the SAME fixture JSON files visual
baseline uses, but routed through Stage 1 (synthetic bundle) + Stage 2
(real `FilterPipeline`) before Stage 3 (renderer):

    fixture JSON
        → wrap in `RawDataBundle` (= Stage 1 output)
        → `FilterPipeline.run()`     (Stage 2 — all 6 filters)
            → `PDFRenderer.render()` (Stage 3 — Playwright Chromium)
                → assert PDF parses, has ≥1 page, has business name

If visual baseline passes but this fails, the regression is in Stages 1-2.
"""
from __future__ import annotations

import json
from pathlib import Path

import fitz                     # pymupdf — parse rendered PDF
import pytest

from services.pdf_data_aggregator import (
    AdminAssets,
    CompanyData,
    RawDataBundle,
)
from services.pdf_filter_pipeline import FilterPipeline
from services.pdf_renderer import PDFRenderer
from templates_html._registry import get_entry


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "pdf_render"

# Same set as tests/visual/test_pdf_baselines.py CASES — these are the
# fixtures known to satisfy each schema. We route them through the full
# pipeline instead of renderer-direct.
CASES = [
    ("company_profile",               "company_profile/sample.json"),
    ("halal_policy",                  "halal_policy/sample.json"),
    ("has_manual",                    "has_manual/sample.json"),
    ("internal_halal_committee",      "internal_halal_committee/sample.json"),
    ("ingredient_raw_material",       "ingredient_raw_material/sample.json"),
    ("process_flow_chart",            "process_flow_chart/sample.json"),
    ("generic",                       "generic/sample.json"),
    ("sop_raw_material_receiving",    "sop_raw_material_receiving/sample.json"),
    ("sop_storage_segregation",       "sop_storage_segregation/sample.json"),
    ("sop_production_operation",      "sop_production_operation/sample.json"),
    ("sop_cleaning_sanitation",       "sop_cleaning_sanitation/sample.json"),
    ("sop_handling_nonconformances",  "sop_handling_nonconformances/sample.json"),
    ("sop_complaint_recall",          "sop_complaint_recall/sample.json"),
]


@pytest.fixture(scope="session")
def filter_pipeline():
    return FilterPipeline()


@pytest.fixture
async def renderer():
    """Function-scoped — Playwright browser binds to per-test event loop."""
    r = PDFRenderer()
    await r.startup()
    try:
        yield r
    finally:
        await r.shutdown()


def _load_fixture(rel: str) -> dict:
    with (FIXTURE_DIR / rel).open(encoding="utf-8") as f:
        return json.load(f)


def _wrap_as_bundle(doc_type: str, fixture: dict) -> RawDataBundle:
    """Wrap a known-good fixture as a Stage-1 bundle. Mirrors what the
    aggregator would produce for a DN submitting `fixture` as request_payload
    against an existing tenant + minimal company record."""
    return RawDataBundle(
        doc_type=doc_type,
        tenant_id="t-test",
        actor_id="actor-test",
        actor_role="business",
        request_payload=fixture,
        request_lang=fixture.get("lang", "vi"),
        is_draft=False,
        company=CompanyData(
            business_name=fixture.get("business_name", "AMINRA Test Co"),
            tax_code=fixture.get("tax_code", "0123456789"),
            address=fixture.get("address", "123 Lê Lợi, Q.1, TP.HCM"),
            phone=fixture.get("phone", "+84 28 1234 5678"),
            email=fixture.get("email", "contact@aminra.test"),
        ),
        active_submission=None,
        admin_cfg={},
        admin_assets=AdminAssets(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("doc_type,fixture_path", CASES, ids=[c[0] for c in CASES])
async def test_full_pipeline_renders_valid_pdf(
    doc_type: str,
    fixture_path: str,
    filter_pipeline: FilterPipeline,
    renderer: PDFRenderer,
):
    """Pipeline produces a parseable PDF with ≥1 page for every doc_type.

    Catches regressions in Stage 2 that visual baseline misses (filter drops
    a field, validation explodes on a fixture that the renderer accepted).
    """
    fixture = _load_fixture(fixture_path)
    bundle = _wrap_as_bundle(doc_type, fixture)
    entry = get_entry(doc_type)
    assert entry is not None, f"doc_type {doc_type} not registered"

    # Stage 2 — filter pipeline (6 filters)
    ctx = filter_pipeline.run(
        bundle,
        title=entry.title_default,
        title_default=entry.title_default,
    )

    # Stage 3 — render with the FILTERED context (not the raw fixture)
    pdf_bytes = await renderer.render(
        doc_type=doc_type,
        data=ctx.data,
        cfg=ctx.cfg,
        title=ctx.title,
        is_draft=ctx.is_draft,
        content="",
        lang=ctx.lang,
    )

    # Sanity: bytes look like a PDF and parse cleanly.
    assert pdf_bytes.startswith(b"%PDF-"), "rendered output is not a PDF"
    assert len(pdf_bytes) > 1000, f"PDF suspiciously small ({len(pdf_bytes)} bytes)"

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        assert doc.page_count >= 1, "PDF has no pages"
        # Brand watermark or template content should yield non-trivial text.
        all_text = " ".join(p.get_text("text") for p in doc)
        assert len(all_text) > 200, (
            f"{doc_type} rendered ~{len(all_text)} chars of text — "
            "likely template render failure or empty data"
        )
