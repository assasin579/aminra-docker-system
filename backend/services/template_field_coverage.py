"""Template placeholder coverage calculator.

For each `doc_type`, defines which company-level user fields contribute to
template placeholders. Used by the coverage endpoint to show users which
fields they should fill to maximize real-data rendering (vs placeholder fill).

Pattern:
  - Identity fields (company_name, address, etc.) are universal — always
    contribute to all doc_types.
  - Specific fields contribute to specific doc_types (e.g. najis_handling_policy
    only matters for has_manual, sop_*).
  - Unknown doc_types fall through to identity fields only.

A future enhancement: read template `*.html` files at import time and grep
`{{ s.field }}` patterns to auto-derive the map. Today: hand-curated based
on `services/pdf_placeholder_data.py` placeholder shapes.
"""
from __future__ import annotations

from typing import Optional


# Universal company-level fields used by every doc_type for identity blocks.
IDENTITY_FIELDS = (
    "company_name",
    "address",
    "phone",
    "email",
    "representative_name",
)

# Per-doc-type fields beyond identity. Empty list = identity-only doc.
EXTRA_FIELDS_BY_DOC_TYPE: dict[str, tuple[str, ...]] = {
    "company_profile": (
        "founded_year",
        "total_employees",
        "halal_commitment_statement",
        "product_categories",
        "production_capacity_brief",
    ),
    "halal_policy": (
        "halal_commitment_statement",
        "founded_year",
        "total_employees",
    ),
    "has_manual": (
        "halal_commitment_statement",
        "najis_handling_policy",
        "cross_contamination_controls",
        "ihc_chairman_name",
    ),
    "halal_manual": (  # alias of has_manual
        "halal_commitment_statement",
        "najis_handling_policy",
        "cross_contamination_controls",
        "ihc_chairman_name",
    ),
    "internal_halal_committee": (
        "ihc_chairman_name",
        "ihc_chairman_title",
        "ihc_inception_date",
        "ihc_members_brief",
        "ihc_meeting_frequency",
    ),
    "ingredient_raw_material": (
        "product_categories",
        "primary_suppliers",
        "ingredient_origin_countries",
        "packaging_materials_brief",
    ),
    "process_flow_chart": (
        "production_capacity_brief",
        "cross_contamination_controls",
    ),
    "sop_personal_hygiene": (
        "najis_handling_policy",
        "cross_contamination_controls",
    ),
    "sop_cleaning_sanitation": (
        "najis_handling_policy",
        "cross_contamination_controls",
    ),
    "sop_pest_control": (),
    "sop_supplier_evaluation": (
        "primary_suppliers",
        "ingredient_origin_countries",
    ),
    "sop_traceability": (
        "primary_suppliers",
        "ingredient_origin_countries",
    ),
    "sop_complaint_handling": (),
    "generic": (),
}


# Display labels (vi) for FE rendering of coverage breakdown.
FIELD_LABELS_VI: dict[str, str] = {
    "company_name": "Tên công ty",
    "address": "Địa chỉ",
    "phone": "Số điện thoại",
    "email": "Email công ty",
    "representative_name": "Người đại diện",
    "founded_year": "Năm thành lập",
    "total_employees": "Tổng số nhân viên",
    "halal_commitment_statement": "Tuyên bố cam kết Halal",
    "najis_handling_policy": "Chính sách xử lý Najis",
    "cross_contamination_controls": "Kiểm soát nhiễm chéo",
    "product_categories": "Danh mục sản phẩm chính",
    "primary_suppliers": "Nhà cung cấp chính",
    "ingredient_origin_countries": "Quốc gia xuất xứ nguyên liệu",
    "packaging_materials_brief": "Vật liệu đóng gói",
    "ihc_chairman_name": "Chủ tịch IHC",
    "ihc_chairman_title": "Chức danh Chủ tịch IHC",
    "ihc_inception_date": "Ngày thành lập IHC",
    "ihc_members_brief": "Thành viên IHC (tóm tắt)",
    "ihc_meeting_frequency": "Tần suất họp IHC",
    "production_capacity_brief": "Năng lực sản xuất (tóm tắt)",
}


def fields_for_doc_type(doc_type: str) -> tuple[str, ...]:
    """Return ordered tuple of (identity + doc-specific) fields for a doc_type.

    Identity fields come first (universal); doc-specific extras follow.
    Returns identity-only for unknown doc_types (defensive).
    """
    extras = EXTRA_FIELDS_BY_DOC_TYPE.get(doc_type, ())
    seen: set[str] = set()
    ordered: list[str] = []
    for f in IDENTITY_FIELDS + extras:
        if f not in seen:
            seen.add(f)
            ordered.append(f)
    return tuple(ordered)


def _is_filled(value) -> bool:
    """A field is 'filled' if non-null, non-empty, non-zero-ish.

    Numeric 0 is treated as filled (year 0 is unrealistic but valid input);
    only str "" + None count as empty.
    """
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def calculate_coverage(
    user_row: dict,
    doc_type: str,
) -> dict:
    """Compute coverage for one doc_type given a user row.

    Returns:
      {
        "doc_type": "...",
        "total_fields": 8,
        "filled": 5,
        "empty": 3,
        "coverage_pct": 62.5,
        "fields": [
          {"key": "company_name", "label": "Tên công ty",
           "filled": True, "value_preview": "AMINRA Foods"},
          {"key": "founded_year", "label": "Năm thành lập",
           "filled": False, "value_preview": None},
          ...
        ]
      }
    """
    fields = fields_for_doc_type(doc_type)
    out_fields: list[dict] = []
    filled = 0
    for key in fields:
        v = user_row.get(key)
        is_filled = _is_filled(v)
        if is_filled:
            filled += 1
        # Truncate string previews to 60 chars for safety
        preview: Optional[str]
        if v is None:
            preview = None
        elif isinstance(v, str):
            preview = v if len(v) <= 60 else v[:57] + "..."
        else:
            preview = str(v)
        out_fields.append({
            "key": key,
            "label": FIELD_LABELS_VI.get(key, key),
            "filled": is_filled,
            "value_preview": preview if is_filled else None,
        })

    total = len(fields)
    return {
        "doc_type": doc_type,
        "total_fields": total,
        "filled": filled,
        "empty": total - filled,
        "coverage_pct": round((filled / total) * 100, 1) if total else 0.0,
        "fields": out_fields,
    }
