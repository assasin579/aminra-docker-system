"""Seed feature_flags for HTML/CSS PDF renderer rollout.

One row per supported doc_type. All default to disabled (default_enabled = false,
rollout_percentage = 0) so the new route ships dark; admins flip the switch
per-tenant via tenant_feature_overrides once the template is QA'd.

Frontend will call /api/feature-flags/me to discover which doc_types are
HTML-renderable for the current tenant; for any disabled flag it falls
back to the legacy templates_docx + libreoffice route — no code branch
in the frontend needs to know which doc_types have HTML templates.

Revision ID: 022_pdf_html_renderer_flags
Revises: 021_custom_placeholders
Create Date: 2026-05-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "022_pdf_html_renderer_flags"
down_revision: Union[str, None] = "021_custom_placeholders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Mirrors templates_html/_registry.py keys. Phase 1 ships only company_profile
# as an actual HTML template; the rest are listed so admins can pre-configure
# tenant overrides ahead of Phase 2 template authoring.
DOC_TYPES = (
    ("company_profile", "Hồ sơ doanh nghiệp — HTML render"),
    ("halal_policy", "Chính sách Halal — HTML render"),
    ("has_manual", "Sổ tay HAS — HTML render"),
    ("halal_manual", "Sổ tay Halal — HTML render"),
    ("sop_raw_material_receiving", "SOP nhận nguyên liệu — HTML render"),
    ("sop_storage_segregation", "SOP lưu trữ và phân tách — HTML render"),
    ("sop_production_operation", "SOP vận hành sản xuất — HTML render"),
    ("sop_cleaning_sanitation", "SOP vệ sinh và làm sạch — HTML render"),
    ("sop_handling_nonconformances", "SOP xử lý không phù hợp — HTML render"),
    ("sop_complaint_recall", "SOP khiếu nại và thu hồi — HTML render"),
    ("internal_halal_committee", "Ban Halal nội bộ — HTML render"),
    ("ingredient_raw_material", "Nguyên liệu thô — HTML render"),
    ("process_flow_chart", "Sơ đồ quy trình — HTML render"),
)


def upgrade() -> None:
    for doc_type, description in DOC_TYPES:
        op.execute(
            """
            INSERT INTO feature_flags (name, description, default_enabled, rollout_percentage)
            VALUES (:name, :description, FALSE, 0)
            ON CONFLICT (name) DO NOTHING
            """.replace(":name", f"'pdf_html_renderer_v1.{doc_type}'")
              .replace(":description", "$$" + description + "$$")
        )


def downgrade() -> None:
    for doc_type, _ in DOC_TYPES:
        op.execute(
            f"DELETE FROM feature_flags WHERE name = 'pdf_html_renderer_v1.{doc_type}'"
        )
