"""Opaque public trace identifiers for sealed batch QR links.

Revision ID: 040_public_trace_id
Revises: 039_supplier_authority_snapshot
Create Date: 2026-09-11
"""

from alembic import op

revision = "040_public_trace_id"
down_revision = "039_supplier_authority_snapshot"
branch_labels = None
depends_on = None

UP_SQL = [
    'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"',
    """
    ALTER TABLE production_batches
      ADD COLUMN IF NOT EXISTS public_trace_id UUID DEFAULT uuid_generate_v4(),
      ADD COLUMN IF NOT EXISTS public_trace_enabled BOOLEAN NOT NULL DEFAULT false
    """,
    """
    UPDATE production_batches
       SET public_trace_id = uuid_generate_v4()
     WHERE public_trace_id IS NULL
    """,
    """
    ALTER TABLE production_batches
      ALTER COLUMN public_trace_id SET NOT NULL
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_production_batches_public_trace_id
      ON production_batches(public_trace_id)
    """,
]

DOWN_SQL = [
    "DROP INDEX IF EXISTS uq_production_batches_public_trace_id",
    "ALTER TABLE production_batches DROP COLUMN IF EXISTS public_trace_enabled, DROP COLUMN IF EXISTS public_trace_id",
]


def upgrade() -> None:
    for sql in UP_SQL:
        op.execute(sql)


def downgrade() -> None:
    for sql in DOWN_SQL:
        op.execute(sql)
