"""Module activation request operator escalation.

Revision ID: 046_module_activation_escal
Revises: 045_module_activation_sla
Create Date: 2026-09-21
"""

from alembic import op

revision = "046_module_activation_escal"
down_revision = "045_module_activation_sla"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        "ALTER TABLE module_activation_requests ADD COLUMN IF NOT EXISTS assigned_operator_id UUID REFERENCES users(id) ON DELETE SET NULL",
        "ALTER TABLE module_activation_requests ADD COLUMN IF NOT EXISTS escalation_count INTEGER NOT NULL DEFAULT 0 CHECK (escalation_count >= 0)",
        "ALTER TABLE module_activation_requests ADD COLUMN IF NOT EXISTS last_escalated_at TIMESTAMPTZ",
        "CREATE INDEX IF NOT EXISTS idx_module_activation_requests_escalation ON module_activation_requests(status, priority, sla_due_at ASC, last_escalated_at ASC) WHERE status = 'pending'",
        "CREATE INDEX IF NOT EXISTS idx_module_activation_requests_assignee ON module_activation_requests(assigned_operator_id, status) WHERE assigned_operator_id IS NOT NULL",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    statements = [
        "DROP INDEX IF EXISTS idx_module_activation_requests_assignee",
        "DROP INDEX IF EXISTS idx_module_activation_requests_escalation",
        "ALTER TABLE module_activation_requests DROP COLUMN IF EXISTS last_escalated_at",
        "ALTER TABLE module_activation_requests DROP COLUMN IF EXISTS escalation_count",
        "ALTER TABLE module_activation_requests DROP COLUMN IF EXISTS assigned_operator_id",
    ]
    for statement in statements:
        op.execute(statement)
