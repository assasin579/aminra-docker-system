"""Registry mapping doc_type → HTML template path + version.

Mirrors the shape of `templates_docx/_registry.py` so that the same
`doc_type` identifier resolves to either a DOCX builder (legacy DOCX→PDF
via libreoffice) or an HTML template (new Playwright route), governed by
the `pdf_html_renderer_v1.{doc_type}` feature flag.

Path discipline:
- The renderer ONLY loads files under `templates_html/` and `templates_html/_shared/`.
- Path traversal protection is delegated to Jinja2's FileSystemLoader,
  which rejects `..` segments by default.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Optional

# ── Path constants ─────────────────────────────────────────────────────────

TEMPLATES_HTML_ROOT = Path(__file__).resolve().parent
DEFAULT_VERSION = "v1"


class TemplateEntry(NamedTuple):
    doc_type: str
    template_relpath: str        # e.g. "company_profile/v1/template.html"
    version: str                  # e.g. "v1"
    title_default: str            # fallback title if request omits it


# ── Registry: 13 doc_types (mirrors templates_docx/_registry.py keys) ──────

_REGISTRY: dict[str, TemplateEntry] = {
    "_style_guide": TemplateEntry(
        doc_type="_style_guide",
        template_relpath="_style_guide/v1/template.html",
        version="v1",
        title_default="AMINRA Design System",
    ),
    "company_profile": TemplateEntry(
        doc_type="company_profile",
        template_relpath="company_profile/v1/template.html",
        version="v1",
        title_default="Hồ sơ doanh nghiệp",
    ),

    # ── 6 SOP variants share the same `sop/v1/` template ────────────────
    # Per-variant differences (title, scope default) come from
    # admin_templates/<doc_type>.json — admin can tweak without dev help.
    "sop_raw_material_receiving": TemplateEntry(
        doc_type="sop_raw_material_receiving",
        template_relpath="sop/v1/template.html",
        version="v1",
        title_default="SOP — Tiếp nhận nguyên liệu",
    ),
    "sop_storage_segregation": TemplateEntry(
        doc_type="sop_storage_segregation",
        template_relpath="sop/v1/template.html",
        version="v1",
        title_default="SOP — Lưu trữ và phân tách",
    ),
    "sop_production_operation": TemplateEntry(
        doc_type="sop_production_operation",
        template_relpath="sop/v1/template.html",
        version="v1",
        title_default="SOP — Vận hành sản xuất",
    ),
    "sop_cleaning_sanitation": TemplateEntry(
        doc_type="sop_cleaning_sanitation",
        template_relpath="sop/v1/template.html",
        version="v1",
        title_default="SOP — Vệ sinh và làm sạch",
    ),
    "sop_handling_nonconformances": TemplateEntry(
        doc_type="sop_handling_nonconformances",
        template_relpath="sop/v1/template.html",
        version="v1",
        title_default="SOP — Xử lý không phù hợp",
    ),
    "sop_complaint_recall": TemplateEntry(
        doc_type="sop_complaint_recall",
        template_relpath="sop/v1/template.html",
        version="v1",
        title_default="SOP — Khiếu nại và thu hồi",
    ),

    # ── Group 2 — Halal Policy + HAS Manual ─────────────────────────────
    "halal_policy": TemplateEntry(
        doc_type="halal_policy",
        template_relpath="halal_policy/v1/template.html",
        version="v1",
        title_default="Chính sách Halal",
    ),
    # has_manual + halal_manual share the same template (HAS = Halal
    # Assurance System; the two slugs are JAKIM/MUI naming variants).
    "has_manual": TemplateEntry(
        doc_type="has_manual",
        template_relpath="has_manual/v1/template.html",
        version="v1",
        title_default="Sổ tay Hệ thống Đảm bảo Halal (HAS Manual)",
    ),
    "halal_manual": TemplateEntry(
        doc_type="halal_manual",
        template_relpath="has_manual/v1/template.html",
        version="v1",
        title_default="Sổ tay Halal",
    ),

    # Phase 2 remaining — Groups 3-5 (placeholder until template ships)
    "internal_halal_committee": None,
    "ingredient_raw_material": None,
    "process_flow_chart": None,
}


def get_entry(doc_type: str) -> Optional[TemplateEntry]:
    """Return the registry entry for `doc_type`, or None if not yet shipped.

    `None` is the explicit signal that the doc_type EXISTS in the design
    but the HTML template has not been authored yet. The router will
    return 501 Not Implemented in that case (vs 404 for unknown doc_type).
    """
    return _REGISTRY.get(doc_type)


def list_supported() -> list[dict]:
    """Snapshot for `GET /api/templates/render-pdf/registry` endpoint."""
    out: list[dict] = []
    for doc_type, entry in _REGISTRY.items():
        if entry is None:
            out.append({
                "doc_type": doc_type,
                "implemented": False,
                "version": None,
            })
        else:
            out.append({
                "doc_type": doc_type,
                "implemented": True,
                "version": entry.version,
                "title_default": entry.title_default,
            })
    return out


def is_known_doc_type(doc_type: str) -> bool:
    """Whether `doc_type` is in the registry (even if not yet implemented).

    Used to discriminate 404 (unknown) from 501 (planned, not shipped).
    """
    return doc_type in _REGISTRY
