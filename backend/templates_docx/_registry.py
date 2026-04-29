"""
Map doc_type → template builder.
Each builder has signature: build(doc, content, title, filename, **kwargs)
Loads admin docx_config from template JSON and passes it as `cfg` kwarg.
"""

import json
import logging
from pathlib import Path
from docx import Document as DocxDocument
from . import (
    halal_policy,
    has_manual,
    sop,
    company_profile,
    ingredient,
    process_flow,
    committee,
    generic,
)

log = logging.getLogger("aminra.templates")

_TEMPLATES = {
    "halal_policy": halal_policy,
    "has_manual": has_manual,
    "halal_manual": has_manual,
    "sop_raw_material_receiving": sop,
    "sop_storage_segregation": sop,
    "sop_production_operation": sop,
    "sop_cleaning_sanitation": sop,
    "sop_handling_nonconformances": sop,
    "sop_complaint_recall": sop,
    "company_profile": company_profile,
    "internal_halal_committee": committee,
    "ingredient_raw_material": ingredient,
    "process_flow_chart": process_flow,
}

TEMPLATES_DIR = Path("admin_templates")


def _load_docx_config(doc_type: str) -> dict:
    """Load docx_config from the admin template JSON, if it exists."""
    path = TEMPLATES_DIR / f"{doc_type}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("docx_config") or {}
    except Exception as e:
        log.warning(f"Failed to load docx_config for {doc_type}: {e}")
        return {}


def build_docx(
    content: str, *, doc_type: str = "", title: str = "Tài liệu Halal", filename: str = "document"
) -> DocxDocument:
    """Create a fully formatted Document using the template for doc_type."""
    doc = DocxDocument()
    module = _TEMPLATES.get(doc_type, generic)

    # Load admin-configured docx_config
    cfg = _load_docx_config(doc_type)

    kwargs: dict = {"cfg": cfg}
    if module is sop:
        kwargs["doc_type"] = doc_type

    module.build(doc, content, title, filename, **kwargs)
    return doc
