"""Stage 2 — transform a `RawDataBundle` into a `RenderContext` Jinja2 sees.

Filters are pure functions (no I/O, no DB) ordered by `DEFAULT_PIPELINE`.
Each takes (bundle, ctx) and returns a (mutated) ctx. Adding a new filter:
implement DesignFilter protocol + insert into pipeline + write a unit test.

Q3=a (this phase): focus on FORMAT — date vi-VN, currency VND, phone, address.
NOT a layout-rules engine (deferred Phase 2+).

Why filters are pure:
- Stage 1 (aggregator) handles I/O. Filters never touch DB or filesystem.
- Determinism — same bundle in → same context out. Crucial for ETag stability
  and visual regression baseline (a filter producing slightly different output
  per call would break both).
- Testability — each filter is unit-testable with synthetic bundles.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal, Optional, Protocol

from pydantic import ValidationError

from services.pdf_data_aggregator import RawDataBundle
from services.pdf_render_schemas import get_schema

log = logging.getLogger("aminra.pdf_filters")


# ── RenderContext (output of pipeline, input of renderer) ──────────────────


@dataclass
class LayoutHints:
    """Phase 1: all "auto"; Phase 2+ rules engine sets explicit values."""
    products_layout: Literal["auto", "stat_grid_4", "kv_block"] = "auto"
    activities_layout: Literal["auto", "single_col", "two_col"] = "auto"
    commitment_render: Literal["auto", "lede", "pull_quote"] = "auto"
    show_watermark: bool = True


@dataclass
class RenderContext:
    doc_type: str
    title: str
    title_default: str
    is_draft: bool
    lang: str
    data: dict = field(default_factory=dict)
    cfg: dict = field(default_factory=dict)
    layout: LayoutHints = field(default_factory=LayoutHints)

    # Diagnostics (NOT rendered into PDF)
    bundle_etag: str = ""
    filters_applied: list[str] = field(default_factory=list)
    filter_durations_ms: dict[str, int] = field(default_factory=dict)


# ── Filter protocol + base class ───────────────────────────────────────────


class DesignFilter(Protocol):
    name: str

    def apply(self, bundle: RawDataBundle, ctx: RenderContext) -> RenderContext: ...


# ── Filters ────────────────────────────────────────────────────────────────


class ValidationFilter:
    """Pydantic-validate `bundle.request_payload` according to doc_type schema.

    Failure raises ValidationError; the router catches it and returns 400.
    """
    name = "validation"

    def apply(self, bundle: RawDataBundle, ctx: RenderContext) -> RenderContext:
        schema = get_schema(bundle.doc_type)
        if schema is None:
            # No schema = unimplemented doc_type — caller should have caught;
            # skip silently here so the renderer 501s downstream cleanly.
            ctx.data = dict(bundle.request_payload)
            return ctx
        validated = schema.model_validate(bundle.request_payload)
        ctx.data = validated.model_dump(mode="json")
        return ctx


class SourceMergeFilter:
    """Merge company + active_submission + admin_cfg into ctx.data.

    Precedence (later overrides earlier):
        1. admin_cfg.defaults
        2. tenant company (DB)
        3. active_submission (DB)
        4. request payload (already in ctx.data after ValidationFilter)
    """
    name = "source_merge"

    def apply(self, bundle: RawDataBundle, ctx: RenderContext) -> RenderContext:
        merged: dict[str, Any] = {}

        # 1. admin defaults
        cfg_defaults = bundle.admin_cfg.get("defaults") or {}
        if isinstance(cfg_defaults, dict):
            merged.update(cfg_defaults)

        # 2. tenant company
        if bundle.company is not None:
            for key in (
                "business_name", "business_name_en", "tax_code",
                "address", "factory_address", "phone", "email", "website",
                "representative", "founded_year", "employee_count", "charter_capital",
            ):
                src_key = "representative" if key == "representative" else key
                # Map db field "representative_name" to template field "representative"
                db_value = getattr(bundle.company, "representative_name" if key == "representative" else key, None)
                if db_value not in (None, ""):
                    merged[key] = db_value

        # 3. active submission (Phase 2 wiring)
        if bundle.active_submission is not None:
            sub = bundle.active_submission
            if sub.business_activities:
                merged["business_activities"] = list(sub.business_activities)
            if sub.products:
                merged["products"] = [
                    {"name": p.name, "description": p.description, "annual_output": p.annual_output}
                    for p in sub.products
                ]
            if sub.halal_commitment:
                merged["halal_commitment"] = sub.halal_commitment
            if sub.halal_responsible_person is not None:
                merged["halal_responsible_person"] = {
                    "name": sub.halal_responsible_person.name,
                    "title": sub.halal_responsible_person.title,
                    "email": sub.halal_responsible_person.email,
                }

        # 4. request payload (last — admin override OR explicit user input)
        for k, v in (ctx.data or {}).items():
            if v not in (None, "", []):
                merged[k] = v

        # 5. ensure issued_date is always present (defaults to today)
        if "issued_date" not in merged or not merged["issued_date"]:
            merged["issued_date"] = date.today().isoformat()

        ctx.data = merged
        return ctx


class FormatFilter:
    """Locale-aware string transforms — vi-VN date/currency/phone/address.

    Operates only on string values; never restructures shape. After this
    filter, ctx.data is ready for the template (no further data mutation).
    """
    name = "format"

    _CURRENCY_PATTERN = re.compile(r"^\d{4,}$")              # raw integer-like (vd "12000000000")
    _PHONE_PATTERN    = re.compile(r"[\s\-().]+")            # any separator
    _MONTHS_VI = ["", "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4", "Tháng 5", "Tháng 6",
                  "Tháng 7", "Tháng 8", "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12"]

    def apply(self, bundle: RawDataBundle, ctx: RenderContext) -> RenderContext:
        d = ctx.data
        lang = ctx.lang

        if "issued_date" in d:
            d["issued_date"] = self._format_date(d["issued_date"], lang)

        if "phone" in d and d["phone"]:
            d["phone"] = self._format_phone(d["phone"])

        if "charter_capital" in d and d["charter_capital"]:
            d["charter_capital"] = self._format_currency(d["charter_capital"], lang)

        return ctx

    @classmethod
    def _format_date(cls, raw: Any, lang: str) -> str:
        """ISO `2026-05-05` → `05/05/2026` (vi) or `May 05, 2026` (en)."""
        if isinstance(raw, (date, datetime)):
            d = raw if isinstance(raw, date) and not isinstance(raw, datetime) else raw.date()
        elif isinstance(raw, str):
            try:
                d = date.fromisoformat(raw[:10])
            except ValueError:
                return raw
        else:
            return str(raw)
        if lang == "vi":
            return f"{d.day:02d}/{d.month:02d}/{d.year}"
        # en
        en_months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{en_months[d.month]} {d.day:02d}, {d.year}"

    @classmethod
    def _format_phone(cls, raw: str) -> str:
        digits = cls._PHONE_PATTERN.sub("", raw)
        # +84 238 1234 567   |  0238 1234 567
        if digits.startswith("+"):
            cc = digits[:3]
            rest = digits[3:]
            if len(rest) >= 9:
                return f"{cc} {rest[:3]} {rest[3:7]} {rest[7:]}"
            return f"{cc} {rest}"
        if digits.startswith("0") and len(digits) >= 10:
            return f"{digits[:4]} {digits[4:8]} {digits[8:]}"
        return raw

    @classmethod
    def _format_currency(cls, raw: str, lang: str) -> str:
        """If raw is bare digits, format with thousand separators + currency.

        Anything already formatted (e.g. "12.000.000.000 VND") passes through.
        """
        s = str(raw).strip()
        if cls._CURRENCY_PATTERN.match(s.replace(",", "").replace(".", "").replace(" ", "")) and not any(c in s for c in "VND$€"):
            n = int(s.replace(",", "").replace(".", "").replace(" ", ""))
            if lang == "vi":
                grouped = f"{n:,}".replace(",", ".")
                return f"{grouped} VND"
            return f"₫{n:,}"
        return s


class TruncationFilter:
    """Cap string lengths to layout-safe maxima.

    Goes AFTER FormatFilter because formatted strings can be longer than raw.
    """
    name = "truncation"

    LIMITS = {
        "title": 80,
        "business_name": 200,
        "business_name_en": 80,
        "address": 200,
    }

    def apply(self, bundle: RawDataBundle, ctx: RenderContext) -> RenderContext:
        # Title
        max_title = self.LIMITS["title"]
        if ctx.title and len(ctx.title) > max_title:
            log.warning("[filter:truncation] title trimmed %d → %d", len(ctx.title), max_title)
            ctx.title = ctx.title[: max_title - 1].rstrip() + "…"

        for k, lim in self.LIMITS.items():
            v = ctx.data.get(k)
            if isinstance(v, str) and len(v) > lim:
                log.warning("[filter:truncation] data.%s trimmed %d → %d", k, len(v), lim)
                ctx.data[k] = v[: lim - 1].rstrip() + "…"
        return ctx


class WatermarkFilter:
    """Inject draft / cross-tenant watermark flags into cfg for the template."""
    name = "watermark"

    def apply(self, bundle: RawDataBundle, ctx: RenderContext) -> RenderContext:
        ctx.layout.show_watermark = ctx.is_draft
        if ctx.is_draft:
            ctx.cfg.setdefault("watermark_label", "DRAFT")
        # Phase 2: cross_tenant.relationship == "assigned_audit" → "PROVIDER PREVIEW"
        return ctx


# ── Pipeline ────────────────────────────────────────────────────────────────


DEFAULT_PIPELINE: list[DesignFilter] = [
    ValidationFilter(),
    SourceMergeFilter(),
    FormatFilter(),
    TruncationFilter(),
    WatermarkFilter(),
]


class FilterPipeline:
    """Stateless runner — single instance OK across requests."""

    def __init__(self, filters: Optional[list[DesignFilter]] = None) -> None:
        self.filters: list[DesignFilter] = filters or DEFAULT_PIPELINE

    def run(self, bundle: RawDataBundle, *, title: str, title_default: str) -> RenderContext:
        ctx = RenderContext(
            doc_type=bundle.doc_type,
            title=title,
            title_default=title_default,
            is_draft=bundle.is_draft,
            lang=bundle.request_lang,
            cfg=dict(bundle.admin_cfg),                # cfg starts from admin
        )

        for f in self.filters:
            t0 = time.monotonic()
            try:
                ctx = f.apply(bundle, ctx)
            except ValidationError:
                # Re-raise so the router can map to 400 with field errors
                raise
            except Exception:
                log.exception("[filter:%s] failed", f.name)
                raise
            ctx.filters_applied.append(f.name)
            ctx.filter_durations_ms[f.name] = int((time.monotonic() - t0) * 1000)

        return ctx
