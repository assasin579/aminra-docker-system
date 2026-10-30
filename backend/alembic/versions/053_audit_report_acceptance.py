"""Track CB acceptance of onsite audit reports.

Revision ID: 053_audit_report_acceptance
Revises: 052_mobile_replay_idem
Create Date: 2026-10-25
"""

from alembic import op

revision = "053_audit_report_acceptance"
down_revision = "052_mobile_replay_idem"
branch_labels = None
depends_on = None


_ACCEPTED_STATUS_CHECK = """
    ALTER TABLE audit_visits
    ADD CONSTRAINT audit_visits_status_check
    CHECK (status IN ('scheduled', 'in_progress', 'completed', 'report_submitted', 'report_accepted'))
"""

_OLD_STATUS_CHECK = """
    ALTER TABLE audit_visits
    ADD CONSTRAINT audit_visits_status_check
    CHECK (status IN ('scheduled', 'in_progress', 'completed', 'report_submitted'))
"""


def upgrade() -> None:
    op.execute("ALTER TABLE audit_visits ADD COLUMN report_accepted_at TIMESTAMPTZ")
    op.execute("ALTER TABLE audit_visits ADD COLUMN report_accepted_by UUID REFERENCES users(id)")
    op.execute("ALTER TABLE audit_visits DROP CONSTRAINT IF EXISTS audit_visits_status_check")
    op.execute(_ACCEPTED_STATUS_CHECK)
    op.execute(
        """
        ALTER TABLE audit_visits
        ADD CONSTRAINT ck_audit_visits_report_acceptance_consistency
        CHECK (
            (status = 'report_accepted'
                AND report_accepted_at IS NOT NULL
                AND report_accepted_by IS NOT NULL)
            OR
            (status IS DISTINCT FROM 'report_accepted'
                AND report_accepted_at IS NULL
                AND report_accepted_by IS NULL)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_audit_visits_provider_report_accepted
        ON audit_visits (provider_id, report_accepted_at DESC)
        WHERE status = 'report_accepted'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM audit_visits WHERE status = 'report_accepted') THEN
                RAISE EXCEPTION 'Cannot downgrade while accepted audit reports exist';
            END IF;
        END;
        $$
        """
    )
    op.execute("DROP INDEX idx_audit_visits_provider_report_accepted")
    op.execute("ALTER TABLE audit_visits DROP CONSTRAINT ck_audit_visits_report_acceptance_consistency")
    op.execute("ALTER TABLE audit_visits DROP COLUMN report_accepted_by")
    op.execute("ALTER TABLE audit_visits DROP COLUMN report_accepted_at")
    op.execute("ALTER TABLE audit_visits DROP CONSTRAINT audit_visits_status_check")
    op.execute(_OLD_STATUS_CHECK)
