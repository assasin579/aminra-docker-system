"""Module activation request workflow.

Revision ID: 044_module_activation_req
Revises: 043_account_deletion_cases
Create Date: 2026-09-21
"""

from alembic import op

revision = "044_module_activation_req"
down_revision = "043_account_deletion_cases"
branch_labels = None
depends_on = None

UP_SQL = [
    """
    CREATE TABLE IF NOT EXISTS module_activation_requests (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID NOT NULL,
        module_id UUID NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
        status VARCHAR(30) NOT NULL DEFAULT 'pending'
          CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
        requester_subject TEXT,
        requester_email TEXT,
        route_path TEXT,
        message TEXT,
        admin_note TEXT,
        reviewed_by TEXT,
        reviewed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_module_activation_requests_tenant_status
      ON module_activation_requests(tenant_id, status, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_module_activation_requests_module
      ON module_activation_requests(module_id, created_at DESC)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_module_activation_requests_one_pending
      ON module_activation_requests(tenant_id, module_id)
      WHERE status = 'pending'
    """,
]

DOWN_SQL = [
    "DROP INDEX IF EXISTS uq_module_activation_requests_one_pending",
    "DROP INDEX IF EXISTS idx_module_activation_requests_module",
    "DROP INDEX IF EXISTS idx_module_activation_requests_tenant_status",
    "DROP TABLE IF EXISTS module_activation_requests",
]


def upgrade() -> None:
    for stmt in UP_SQL:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in DOWN_SQL:
        op.execute(stmt)
