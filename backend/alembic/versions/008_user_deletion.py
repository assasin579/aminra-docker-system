"""user soft-delete + GDPR right-to-be-forgotten

Adds the columns needed to support GDPR Article 17 / VN Nghị định 13 right to
erasure: a deleted_at timestamp (soft delete preserves referential integrity
for audit / cert legal artifacts), and a separate deletion_tokens table for
the email-confirmation flow.

Revision ID: 008_user_deletion
Revises: 007_audit_logs
Create Date: 2026-04-25
"""
from typing import Sequence, Union
from alembic import op

revision: str = "008_user_deletion"
down_revision: Union[str, None] = "007_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Soft-delete column on users
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_deleted_at ON users(deleted_at) WHERE deleted_at IS NOT NULL;")

    # 2) deletion_tokens — separate table from password_reset_tokens for clarity
    #    and to make per-flow rate limiting easier.
    op.execute("""
        CREATE TABLE IF NOT EXISTS deletion_tokens (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token           VARCHAR(255) UNIQUE NOT NULL,
            expires_at      TIMESTAMPTZ NOT NULL,
            confirmed_at    TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_deletion_token ON deletion_tokens(token);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_deletion_user  ON deletion_tokens(user_id, created_at DESC);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS deletion_tokens;")
    op.execute("DROP INDEX IF EXISTS idx_users_deleted_at;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS deleted_at;")
