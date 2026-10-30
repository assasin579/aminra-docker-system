"""Provider authority and batch material eligibility snapshots.

Revision ID: 039_supplier_authority_snapshot
Revises: 038_cb_supplier_eligibility
Create Date: 2026-09-06
"""

from alembic import op

revision = "039_supplier_authority_snapshot"
down_revision = "038_cb_supplier_eligibility"
branch_labels = None
depends_on = None

UP_SQL = [
    """
    ALTER TABLE supplier_eligibilities
      ADD COLUMN IF NOT EXISTS provider_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
      ADD COLUMN IF NOT EXISTS source_certificate_id UUID NULL REFERENCES halal_certificates(id) ON DELETE SET NULL
    """,
    """
    UPDATE supplier_eligibilities
       SET provider_id = changed_by
     WHERE provider_id IS NULL
       AND changed_by IS NOT NULL
    """,
    """
    ALTER TABLE batch_materials
      ADD COLUMN IF NOT EXISTS supplier_id UUID NULL REFERENCES suppliers(id) ON DELETE SET NULL,
      ADD COLUMN IF NOT EXISTS eligibility_id UUID NULL REFERENCES supplier_eligibilities(id) ON DELETE SET NULL,
      ADD COLUMN IF NOT EXISTS eligibility_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb
    """,
    "CREATE INDEX IF NOT EXISTS idx_supplier_eligibilities_provider ON supplier_eligibilities(provider_id, tenant_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_supplier_eligibilities_source_cert ON supplier_eligibilities(source_certificate_id)",
    "CREATE INDEX IF NOT EXISTS idx_batch_materials_supplier_eligibility ON batch_materials(supplier_id, eligibility_id)",
]

DOWN_SQL = [
    "DROP INDEX IF EXISTS idx_batch_materials_supplier_eligibility",
    "DROP INDEX IF EXISTS idx_supplier_eligibilities_source_cert",
    "DROP INDEX IF EXISTS idx_supplier_eligibilities_provider",
    "ALTER TABLE batch_materials DROP COLUMN IF EXISTS eligibility_snapshot, DROP COLUMN IF EXISTS eligibility_id, DROP COLUMN IF EXISTS supplier_id",
    "ALTER TABLE supplier_eligibilities DROP COLUMN IF EXISTS source_certificate_id, DROP COLUMN IF EXISTS provider_id",
]


def upgrade() -> None:
    for sql in UP_SQL:
        op.execute(sql)


def downgrade() -> None:
    for sql in DOWN_SQL:
        op.execute(sql)
