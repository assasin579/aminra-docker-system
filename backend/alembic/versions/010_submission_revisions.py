"""submission revisions cycle — provider can request revisions with structured feedback

Adds the missing piece in the submission state machine: when provider reviews
and finds issues that aren't disqualifying, they now request revisions instead
of returning/rejecting outright. Business sees per-document feedback, fixes,
and resubmits — preserving audit trail across rounds.

Revision ID: 010_submission_revisions
Revises: 009_blockchain_anchors
Create Date: 2026-04-25
"""
from typing import Sequence, Union
from alembic import op

revision: str = "010_submission_revisions"
down_revision: Union[str, None] = "009_blockchain_anchors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Counter columns on submissions
    op.execute("""
        ALTER TABLE submissions
            ADD COLUMN IF NOT EXISTS revision_round INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS revision_requested_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS revision_resubmitted_at TIMESTAMPTZ;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_submissions_revision_state
            ON submissions(status, revision_round)
            WHERE status = 'revision_required';
    """)

    # 2) Per-round revision request records — keeps audit trail across rounds
    op.execute("""
        CREATE TABLE IF NOT EXISTS submission_revision_requests (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            submission_id   UUID NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
            round           INTEGER NOT NULL,
            requester_id    UUID NOT NULL REFERENCES users(id),
            requester_name  VARCHAR(255) NOT NULL,
            feedback        TEXT NOT NULL,
            document_feedback JSONB DEFAULT '[]'::jsonb,
            requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at     TIMESTAMPTZ,
            UNIQUE (submission_id, round)
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_revision_requests_submission
            ON submission_revision_requests(submission_id, round DESC);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_revision_requests_unresolved
            ON submission_revision_requests(submission_id)
            WHERE resolved_at IS NULL;
    """)

    # 3) Append-only — revision requests are part of audit trail
    op.execute("REVOKE DELETE ON submission_revision_requests FROM PUBLIC;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS submission_revision_requests;")
    op.execute("""
        ALTER TABLE submissions
            DROP COLUMN IF EXISTS revision_round,
            DROP COLUMN IF EXISTS revision_requested_at,
            DROP COLUMN IF EXISTS revision_resubmitted_at;
    """)
    op.execute("DROP INDEX IF EXISTS idx_submissions_revision_state;")
