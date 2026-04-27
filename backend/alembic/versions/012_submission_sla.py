"""submission SLA tracking — alert at 80% TTL + admin escalation

Adds submissions.sla_alerts_sent JSONB tracking which thresholds (80, 100=overdue)
have already had an alert dispatched, so daily cron stays idempotent.

Revision ID: 012_submission_sla
Revises: 011_cert_lifecycle
Create Date: 2026-04-25
"""
from typing import Sequence, Union
from alembic import op

revision: str = "012_submission_sla"
down_revision: Union[str, None] = "011_cert_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE submissions
            ADD COLUMN IF NOT EXISTS sla_alerts_sent JSONB NOT NULL DEFAULT '[]'::jsonb;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_submissions_deadline_active
            ON submissions(deadline)
            WHERE deadline IS NOT NULL
              AND status NOT IN ('approved', 'returned', 'rejected');
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_submissions_deadline_active;")
    op.execute("ALTER TABLE submissions DROP COLUMN IF EXISTS sla_alerts_sent;")
