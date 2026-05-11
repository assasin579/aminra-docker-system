"""Revert Phase 1 — drop 15 company rich-data columns from users.

Rationale: founder decided 2026-05-11 to abandon hybrid form approach
(centralized rich-data in Settings/Company) in favor of per-doc-type form
(Wow #1 Phase 2 plan — TASK #12). Columns introduced in migration 031
become dead schema; drop to avoid drift.

NOTE: GCC/MUI standards seeded in 031 + their industry mappings are KEPT
(orthogonal to form approach; standards used for dossier creation
regardless of where form fields live).

Revision ID: 032_revert_company_rich_data_columns
Revises: 031_company_rich_data_gcc_mui
Create Date: 2026-05-11
"""
from typing import Sequence, Union
from alembic import op


revision: str = "032_revert_rich_data"
down_revision: Union[str, None] = "031_company_rich_data_gcc_mui"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the 15 columns introduced in migration 031."""
    op.execute("""
        ALTER TABLE users
            DROP COLUMN IF EXISTS founded_year,
            DROP COLUMN IF EXISTS halal_commitment_statement,
            DROP COLUMN IF EXISTS total_employees,
            DROP COLUMN IF EXISTS najis_handling_policy,
            DROP COLUMN IF EXISTS cross_contamination_controls,
            DROP COLUMN IF EXISTS product_categories,
            DROP COLUMN IF EXISTS primary_suppliers,
            DROP COLUMN IF EXISTS ingredient_origin_countries,
            DROP COLUMN IF EXISTS packaging_materials_brief,
            DROP COLUMN IF EXISTS ihc_chairman_name,
            DROP COLUMN IF EXISTS ihc_chairman_title,
            DROP COLUMN IF EXISTS ihc_inception_date,
            DROP COLUMN IF EXISTS ihc_members_brief,
            DROP COLUMN IF EXISTS ihc_meeting_frequency,
            DROP COLUMN IF EXISTS production_capacity_brief;
    """)


def downgrade() -> None:
    """Re-add columns (same as 031 upgrade)."""
    op.execute("""
        ALTER TABLE users
            ADD COLUMN founded_year                  INT,
            ADD COLUMN halal_commitment_statement    TEXT,
            ADD COLUMN total_employees               INT,
            ADD COLUMN najis_handling_policy         TEXT,
            ADD COLUMN cross_contamination_controls  TEXT,
            ADD COLUMN product_categories            TEXT,
            ADD COLUMN primary_suppliers             TEXT,
            ADD COLUMN ingredient_origin_countries   TEXT,
            ADD COLUMN packaging_materials_brief     TEXT,
            ADD COLUMN ihc_chairman_name             VARCHAR(255),
            ADD COLUMN ihc_chairman_title            VARCHAR(255),
            ADD COLUMN ihc_inception_date            DATE,
            ADD COLUMN ihc_members_brief             TEXT,
            ADD COLUMN ihc_meeting_frequency         VARCHAR(100),
            ADD COLUMN production_capacity_brief     TEXT;
    """)
