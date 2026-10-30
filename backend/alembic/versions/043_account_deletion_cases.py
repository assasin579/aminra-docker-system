"""Governed account deletion cleanup cases.

Revision ID: 043_account_deletion_cases
Revises: 042_identity_projection_status
Create Date: 2026-09-19
"""

from alembic import op

revision = "043_account_deletion_cases"
down_revision = "042_identity_projection_status"
branch_labels = None
depends_on = None


UP_SQL = [
    """
    CREATE TABLE IF NOT EXISTS account_deletion_cases (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        email_snapshot VARCHAR(255) NOT NULL,
        identity_status_snapshot VARCHAR(40) NOT NULL,
        status VARCHAR(40) NOT NULL DEFAULT 'assessment_ready'
          CHECK (status IN ('assessment_ready', 'approval_required', 'running', 'completed', 'partially_completed', 'failed', 'blocked', 'cancelled')),
        risk_level VARCHAR(20) NOT NULL DEFAULT 'low'
          CHECK (risk_level IN ('low', 'medium', 'high', 'blocker')),
        created_by TEXT,
        approved_by TEXT,
        confirmation_phrase TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ,
        last_error TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS account_deletion_case_items (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        case_id UUID NOT NULL REFERENCES account_deletion_cases(id) ON DELETE CASCADE,
        reference_key VARCHAR(120) NOT NULL,
        label TEXT NOT NULL,
        table_name VARCHAR(120),
        column_name VARCHAR(120),
        record_count INTEGER NOT NULL DEFAULT 0 CHECK (record_count >= 0),
        action VARCHAR(80) NOT NULL,
        risk_level VARCHAR(20) NOT NULL DEFAULT 'low'
          CHECK (risk_level IN ('low', 'medium', 'high', 'blocker')),
        status VARCHAR(40) NOT NULL DEFAULT 'pending'
          CHECK (status IN ('pending', 'running', 'completed', 'skipped', 'failed', 'blocked')),
        reason TEXT NOT NULL,
        before_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
        after_result JSONB NOT NULL DEFAULT '{}'::jsonb,
        error_message TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_account_deletion_cases_user_id ON account_deletion_cases(user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_account_deletion_case_items_case_id ON account_deletion_case_items(case_id)",
    """
    ALTER TABLE users
      ADD COLUMN IF NOT EXISTS account_cleanup_status VARCHAR(40) NOT NULL DEFAULT 'not_started'
        CHECK (account_cleanup_status IN ('not_started', 'assessment_ready', 'cleaned', 'partially_cleaned', 'blocked', 'failed'))
    """,
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS account_cleanup_case_id UUID REFERENCES account_deletion_cases(id) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS idx_users_account_cleanup_status ON users(account_cleanup_status)",
]

DOWN_SQL = [
    "DROP INDEX IF EXISTS idx_users_account_cleanup_status",
    "ALTER TABLE users DROP COLUMN IF EXISTS account_cleanup_case_id",
    "ALTER TABLE users DROP COLUMN IF EXISTS account_cleanup_status",
    "DROP INDEX IF EXISTS idx_account_deletion_case_items_case_id",
    "DROP INDEX IF EXISTS idx_account_deletion_cases_user_id",
    "DROP TABLE IF EXISTS account_deletion_case_items",
    "DROP TABLE IF EXISTS account_deletion_cases",
]


def upgrade() -> None:
    for stmt in UP_SQL:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in DOWN_SQL:
        op.execute(stmt)
