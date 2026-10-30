"""Enforce UNIQUE (tenant_id, batch_code) on production_batches

The /batches/trace/{batch_code} endpoint and downstream QR / cert artifacts
assume each batch has a globally-resolvable code within its tenant. Without
a UNIQUE constraint, duplicates produced ambiguous traces (the first row
won, silently). Adding (tenant_id, batch_code) UNIQUE — duplicates between
DIFFERENT tenants are still allowed (legal: each business owns its own LOT
numbering scheme).

If existing rows already collide, dedupe by appending the row's id suffix
to all but the earliest row before adding the constraint, so the migration
never aborts on legacy data.

Revision ID: 025_unique_batch_code
Revises: 024_add_supplier_tax_code
Create Date: 2026-05-08
"""
from typing import Sequence, Union
from alembic import op


revision: str = "025_unique_batch_code"
down_revision: Union[str, None] = "024_add_supplier_tax_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: dedupe legacy collisions before constraint creation.
    # For each (tenant_id, batch_code) group with >1 rows, keep the earliest
    # `created_at` and rewrite siblings to <code>-<short-id> so they remain
    # unique without losing data.
    op.execute(
        """
        WITH dups AS (
            SELECT id, tenant_id, batch_code,
                   ROW_NUMBER() OVER (
                       PARTITION BY tenant_id, batch_code
                       ORDER BY created_at, id
                   ) AS rn
              FROM production_batches
        )
        UPDATE production_batches pb
           SET batch_code = pb.batch_code || '-' || SUBSTRING(pb.id::text, 1, 6)
          FROM dups
         WHERE pb.id = dups.id AND dups.rn > 1;
        """
    )

    op.create_unique_constraint(
        "uq_production_batches_tenant_code",
        "production_batches",
        ["tenant_id", "batch_code"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_production_batches_tenant_code",
        "production_batches",
        type_="unique",
    )
