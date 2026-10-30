"""Phase 4b post-cutover cleanup: drop password_reset_tokens table.

password_reset_router.py was removed (Keycloak owns password reset flow via
/realms/aminra/login-actions/reset-credentials). The PG table has no writers
left in code. Drop to reduce schema surface.

users.password_hash column kept for now — admin user create + invite/member
flows still use it (Phase 4c TODO migrate to Keycloak invitation flow).

Revision ID: 035_drop_password_reset_tokens
Revises: 034_keycloak_nuclear_cutover
Create Date: 2026-05-14
"""

from alembic import op


revision = "035_drop_password_reset_tokens"
down_revision = "034_keycloak_nuclear_cutover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS password_reset_tokens CASCADE")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token VARCHAR(128) PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
