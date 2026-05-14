"""Phase 4c-4: drop users.password_hash column.

Keycloak is now the sole credential store (Phase 4b cutover for end-user
auth; Phase 4c-1 → 4c-3 migrated the remaining admin / invite / member
flows). No code reads or writes password_hash anymore — drop it to reduce
schema surface and remove a tempting place to leak credentials.

Revision ID: 036_drop_password_hash
Revises: 035_drop_password_reset_tokens
Create Date: 2026-05-14
"""

from alembic import op


revision = "036_drop_password_hash"
down_revision = "035_drop_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS password_hash")


def downgrade() -> None:
    # Nullable: post-Phase-4b the column was already NULLABLE; restoring
    # NOT NULL would require a backfill that's impossible without the
    # original credentials. Re-create as nullable for parity.
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)")
