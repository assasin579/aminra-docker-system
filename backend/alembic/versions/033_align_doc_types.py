"""Fix doc_type name drift: align standard_doc_types với templates_html registry.

Bug discovered 2026-05-11 via abc@gmail.com (restaurant_hotel) seeing only 8
of 13 doc_types in create-document flow. Root cause: migration 028 (initial
industry seed) + 029 (standard_types split) seeded SOP names that don't
match actual shipped templates (`templates_html/_registry.py`):

| Migration 028/029 seed         | templates_html registry          |
|--------------------------------|----------------------------------|
| sop_personal_hygiene           | sop_raw_material_receiving       |
| sop_pest_control               | sop_storage_segregation          |
| sop_supplier_evaluation        | sop_production_operation         |
| sop_traceability               | sop_handling_nonconformances     |
| sop_complaint_handling         | sop_complaint_recall             |
| sop_cleaning_sanitation        | sop_cleaning_sanitation ✓        |

FE filter logic in create-document intersects template registry with
standard.doc_types → only 8 matches (5 SOPs + 3 non-SOP overlap), so user
sees 8 doc_types instead of all 13.

Fix: re-seed standard_doc_types với 6 registry SOP names. Keep 7 non-SOP
doc_types unchanged (already match: company_profile, halal_policy,
has_manual, internal_halal_committee, ingredient_raw_material,
process_flow_chart, generic).

NOTE: GCC/MUI standards (uae_s_2055_1_2015, gso_2055_2_2021, oic_smiic_1_2019,
has_23000_2012) have no doc_types seeded yet — skip them. Phase 2 template
variant work will seed when those template variants ship.

Revision ID: 033_align_doc_types
Revises: 032_revert_rich_data
Create Date: 2026-05-11
"""
from typing import Sequence, Union
from alembic import op


revision: str = "033_align_doc_types"
down_revision: Union[str, None] = "032_revert_rich_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 5 SOP doc_types in registry that should replace the 5 mismatching seeds
_NEW_SOPS = [
    "sop_raw_material_receiving",
    "sop_storage_segregation",
    "sop_production_operation",
    "sop_handling_nonconformances",
    "sop_complaint_recall",
]

_OLD_SOPS = [
    "sop_personal_hygiene",
    "sop_pest_control",
    "sop_supplier_evaluation",
    "sop_traceability",
    "sop_complaint_handling",
]

# JAKIM standards that should have full 13 doc_types (from migration 028/029)
_JAKIM_FULL_STANDARDS = ("ms_1500_2019", "ms_1480_2007", "mpphm_2020")

# Plus 2 specialty JAKIM standards that had only 5 doc_types (no SOPs)
# These don't need SOP renames: ms_2424_2019, ms_2200_2_2013


def upgrade() -> None:
    # Step 1: Delete obsolete SOP rows from full-13 JAKIM standards
    op.execute(f"""
        DELETE FROM standard_doc_types
        WHERE doc_type = ANY(ARRAY{_OLD_SOPS!r}::text[])
          AND standard_type_id IN (
            SELECT id FROM standard_types
            WHERE code = ANY(ARRAY{list(_JAKIM_FULL_STANDARDS)!r}::text[])
          );
    """)

    # Step 2: Insert correct SOP rows for the 3 full-13 JAKIM standards
    for i, sop in enumerate(_NEW_SOPS):
        op.execute(f"""
            INSERT INTO standard_doc_types
                (standard_type_id, doc_type, required, display_order)
            SELECT id, '{sop}', true, {7 + i}
            FROM standard_types
            WHERE code = ANY(ARRAY{list(_JAKIM_FULL_STANDARDS)!r}::text[])
            ON CONFLICT DO NOTHING;
        """)


def downgrade() -> None:
    # Reverse: delete the new SOPs, re-insert the old ones
    op.execute(f"""
        DELETE FROM standard_doc_types
        WHERE doc_type = ANY(ARRAY{_NEW_SOPS!r}::text[])
          AND standard_type_id IN (
            SELECT id FROM standard_types
            WHERE code = ANY(ARRAY{list(_JAKIM_FULL_STANDARDS)!r}::text[])
          );
    """)

    for i, sop in enumerate(_OLD_SOPS):
        op.execute(f"""
            INSERT INTO standard_doc_types
                (standard_type_id, doc_type, required, display_order)
            SELECT id, '{sop}', true, {7 + i}
            FROM standard_types
            WHERE code = ANY(ARRAY{list(_JAKIM_FULL_STANDARDS)!r}::text[])
            ON CONFLICT DO NOTHING;
        """)
