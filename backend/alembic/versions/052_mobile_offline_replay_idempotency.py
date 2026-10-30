"""mobile offline replay idempotency

Revision ID: 052_mobile_replay_idem
Revises: 051_official_artifacts
Create Date: 2026-09-27
"""

from alembic import op

revision = "052_mobile_replay_idem"
down_revision = "051_official_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS mobile_offline_replay_operations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            user_id UUID REFERENCES users(id),
            visit_id UUID,
            operation_type TEXT NOT NULL,
            route_key TEXT NOT NULL,
            resource_key TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            request_hash TEXT NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
            response_status INTEGER NOT NULL CHECK (response_status BETWEEN 100 AND 599),
            response_body JSONB NOT NULL DEFAULT '{}'::jsonb,
            conflict_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mobile_offline_replay_scope_key
          ON mobile_offline_replay_operations(tenant_id, operation_type, route_key, resource_key, idempotency_key)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_mobile_offline_replay_visit_created
          ON mobile_offline_replay_operations(tenant_id, visit_id, created_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_mobile_offline_replay_user_created
          ON mobile_offline_replay_operations(tenant_id, user_id, created_at DESC)
        """,
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    statements = [
        "DROP INDEX IF EXISTS idx_mobile_offline_replay_user_created",
        "DROP INDEX IF EXISTS idx_mobile_offline_replay_visit_created",
        "DROP INDEX IF EXISTS uq_mobile_offline_replay_scope_key",
        "DROP TABLE IF EXISTS mobile_offline_replay_operations",
    ]
    for statement in statements:
        op.execute(statement)
