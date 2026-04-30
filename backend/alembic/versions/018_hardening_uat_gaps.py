"""hardening: UAT-surfaced gaps (defense-in-depth + input validation)

Closes 1 of 3 UAT gaps from 2026-04-30 run:

C-50: documents.tenant_id is NOT NULL at schema level (was nullable=YES,
defended only by application code — single buggy migration could break
multi-tenant isolation invariant).

Pre-requisite verified at write time: 0 rows have NULL tenant_id, so the
ALTER COLUMN SET NOT NULL is safe to apply directly without backfill.

The other 2 gaps (oversize input crash, empty company_name accepted) are
fixed in `backend/auth/models.py` Pydantic Field constraints — no DB
migration needed.

Revision ID: 018_hardening_uat_gaps
Revises: 017_document_version_control
Create Date: 2026-04-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "018_hardening_uat_gaps"
down_revision: Union[str, None] = "017_document_version_control"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safety check: refuse to run if any NULL tenant_ids exist. Backfill must
    # happen explicitly before this migration (operational decision, not a
    # silent guess).
    op.execute("""
        DO $$
        DECLARE n INT;
        BEGIN
          SELECT COUNT(*) INTO n FROM documents WHERE tenant_id IS NULL;
          IF n > 0 THEN
            RAISE EXCEPTION 'Cannot ALTER tenant_id NOT NULL: % rows have NULL tenant_id. Backfill first.', n;
          END IF;
        END $$;
    """)

    op.execute("ALTER TABLE documents ALTER COLUMN tenant_id SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE documents ALTER COLUMN tenant_id DROP NOT NULL")
