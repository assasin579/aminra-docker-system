"""workflow integrity hardening — Phase 1 Batch 1 of bug audit 2026-04-26

Captures user policy decisions:
  - decision #3: split `documents.cb_approved_at` from `uploaded_at`
  - decision #4: enforce `audit_logs` immutability via trigger
  - W3-M1   : add CHECK constraint on `submissions.status`
  - C3      : add `submissions.archived_at` so finalize can preserve history
              instead of CASCADE-deleting revision rounds

Revision ID: 014_workflow_integrity
Revises: 013_push_subscriptions
Create Date: 2026-04-26
"""
from typing import Sequence, Union
from alembic import op

revision: str = "014_workflow_integrity"
down_revision: Union[str, None] = "013_push_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. cb_approved_at — separate column so we never mutate uploaded_at
    op.execute("""
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS cb_approved_at TIMESTAMPTZ;
    """)

    # 2. archived_at — finalize sets this instead of DELETEing the row, so
    #    revision history + cert linkage stay intact.
    op.execute("""
        ALTER TABLE submissions
        ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_submissions_active
        ON submissions(provider_id, business_tenant)
        WHERE archived_at IS NULL;
    """)

    # 3. CHECK constraint on submissions.status — block garbage values
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_submission_status_enum'
            ) THEN
                ALTER TABLE submissions
                ADD CONSTRAINT chk_submission_status_enum
                CHECK (status IN (
                    'pending','assigned','reviewing',
                    'revision_required','returned','rejected','approved'
                ));
            END IF;
        END $$;
    """)

    # 4. audit_logs immutability — trigger raises on UPDATE/DELETE
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_logs_immutable_guard()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only; UPDATE/DELETE not permitted (op=%)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_logs;
        CREATE TRIGGER trg_audit_logs_immutable
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable_guard();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_immutable_guard();")
    op.execute("ALTER TABLE submissions DROP CONSTRAINT IF EXISTS chk_submission_status_enum;")
    op.execute("DROP INDEX IF EXISTS idx_submissions_active;")
    op.execute("ALTER TABLE submissions DROP COLUMN IF EXISTS archived_at;")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS cb_approved_at;")
