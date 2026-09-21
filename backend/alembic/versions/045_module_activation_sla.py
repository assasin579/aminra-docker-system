"""Module activation request SLA and operator notification metadata.

Revision ID: 045_module_activation_sla
Revises: 044_module_activation_req
Create Date: 2026-09-21
"""

from alembic import op

revision = "045_module_activation_sla"
down_revision = "044_module_activation_req"
branch_labels = None
depends_on = None

UP_SQL = [
    "ALTER TABLE module_activation_requests ADD COLUMN IF NOT EXISTS priority VARCHAR(20) NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'urgent'))",
    "ALTER TABLE module_activation_requests ADD COLUMN IF NOT EXISTS sla_due_at TIMESTAMPTZ",
    "ALTER TABLE module_activation_requests ADD COLUMN IF NOT EXISTS first_notified_at TIMESTAMPTZ",
    "ALTER TABLE module_activation_requests ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ",
    "ALTER TABLE module_activation_requests ADD COLUMN IF NOT EXISTS notification_count INTEGER NOT NULL DEFAULT 0 CHECK (notification_count >= 0)",
    "UPDATE module_activation_requests SET sla_due_at = COALESCE(sla_due_at, created_at + INTERVAL '24 hours') WHERE status = 'pending'",
    "CREATE INDEX IF NOT EXISTS idx_module_activation_requests_pending_sla ON module_activation_requests(status, sla_due_at ASC) WHERE status = 'pending'",
]

DOWN_SQL = [
    "DROP INDEX IF EXISTS idx_module_activation_requests_pending_sla",
    "ALTER TABLE module_activation_requests DROP COLUMN IF EXISTS notification_count",
    "ALTER TABLE module_activation_requests DROP COLUMN IF EXISTS last_notified_at",
    "ALTER TABLE module_activation_requests DROP COLUMN IF EXISTS first_notified_at",
    "ALTER TABLE module_activation_requests DROP COLUMN IF EXISTS sla_due_at",
    "ALTER TABLE module_activation_requests DROP COLUMN IF EXISTS priority",
]


def upgrade() -> None:
    for stmt in UP_SQL:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in DOWN_SQL:
        op.execute(stmt)
