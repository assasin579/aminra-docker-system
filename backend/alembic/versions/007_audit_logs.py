"""audit logs — extend who-changed-what schema, append-only

The audit_logs table was created by an earlier ad-hoc script with a
narrower schema (user_id, action, details, ip_address). We ALTER it in
place to add the columns the service needs (user_email, user_role,
tenant_id, changes, metadata), migrate existing data, and revoke
UPDATE/DELETE for compliance.

Revision ID: 007_audit_logs
Revises: 006_self_assessment
Create Date: 2026-04-25
"""
from typing import Sequence, Union
from alembic import op

revision: str = "007_audit_logs"
down_revision: Union[str, None] = "006_self_assessment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create table if it doesn't exist; otherwise ALTER in place.
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id      UUID REFERENCES users(id) ON DELETE SET NULL,
            action       VARCHAR(64)  NOT NULL,
            entity_type  VARCHAR(64)  NOT NULL,
            entity_id    UUID,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # Add columns the service expects (idempotent).
    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_email VARCHAR(255);")
    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_role  VARCHAR(50);")
    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS tenant_id  UUID;")
    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS changes    JSONB;")
    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS metadata   JSONB DEFAULT '{}'::jsonb;")

    # Migrate legacy `details` + `ip_address` → `metadata` if those columns exist.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name='audit_logs' AND column_name='details') THEN
                UPDATE audit_logs
                   SET metadata = COALESCE(details, '{}'::jsonb)
                                  || CASE WHEN ip_address IS NOT NULL
                                          THEN jsonb_build_object('ip', host(ip_address))
                                          ELSE '{}'::jsonb END
                 WHERE metadata = '{}'::jsonb;
            END IF;
        END $$;
    """)

    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS details;")
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS ip_address;")

    # Backfill: ensure entity_type is NOT NULL (legacy rows may have NULL — set to 'unknown').
    op.execute("UPDATE audit_logs SET entity_type='unknown' WHERE entity_type IS NULL;")
    op.execute("ALTER TABLE audit_logs ALTER COLUMN entity_type SET NOT NULL;")

    # Indexes on common query patterns.
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_user        ON audit_logs(user_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity      ON audit_logs(entity_type, entity_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_action      ON audit_logs(action, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant      ON audit_logs(tenant_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_created     ON audit_logs(created_at DESC);")

    # Append-only at the DB level.
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC;")


def downgrade() -> None:
    # Don't recreate the legacy details/ip_address columns — would be lossy.
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS user_email;")
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS user_role;")
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS tenant_id;")
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS changes;")
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS metadata;")
    op.execute("DROP INDEX IF EXISTS idx_audit_entity;")
    op.execute("DROP INDEX IF EXISTS idx_audit_action;")
    op.execute("DROP INDEX IF EXISTS idx_audit_tenant;")
