"""Track Keycloak identity projection status on app users.

Revision ID: 042_identity_projection_status
Revises: 041_module_registry
Create Date: 2026-09-18
"""

from alembic import op

revision = "042_identity_projection_status"
down_revision = "041_module_registry"
branch_labels = None
depends_on = None


UP_SQL = [
    """
    ALTER TABLE users
      ADD COLUMN IF NOT EXISTS identity_status VARCHAR(40) NOT NULL DEFAULT 'linked'
        CHECK (identity_status IN ('linked', 'missing_in_keycloak', 'disabled_in_keycloak', 'unknown'))
    """,
    """
    ALTER TABLE users
      ADD COLUMN IF NOT EXISTS keycloak_deleted_at TIMESTAMPTZ
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_users_identity_status
      ON users(identity_status, keycloak_deleted_at)
    """,
]

DOWN_SQL = [
    "DROP INDEX IF EXISTS idx_users_identity_status",
    "ALTER TABLE users DROP COLUMN IF EXISTS keycloak_deleted_at",
    "ALTER TABLE users DROP COLUMN IF EXISTS identity_status",
]


def upgrade() -> None:
    for stmt in UP_SQL:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in DOWN_SQL:
        op.execute(stmt)
