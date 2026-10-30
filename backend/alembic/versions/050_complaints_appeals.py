"""complaints and appeals

Revision ID: 050_complaints_appeals
Revises: 048_conflicts_interest
Create Date: 2026-09-23
"""

from alembic import op

revision = "050_complaints_appeals"
down_revision = "048_conflicts_interest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS complaint_cases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            provider_id UUID NOT NULL,
            business_tenant UUID,
            certificate_id UUID REFERENCES halal_certificates(id),
            submission_id UUID REFERENCES submissions(id),
            case_type TEXT NOT NULL CHECK (case_type IN ('complaint_service','complaint_certified_client','appeal_decision')),
            source TEXT NOT NULL CHECK (source IN ('business','provider','public','internal')),
            status TEXT NOT NULL CHECK (status IN ('received','acknowledged','under_investigation','decision_made','closed','rejected')),
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            submitted_by_user_id UUID REFERENCES users(id),
            assigned_owner_id UUID REFERENCES users(id),
            original_decision_id UUID REFERENCES certification_decisions(id),
            due_at TIMESTAMPTZ,
            decision_summary TEXT,
            closure_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            closed_at TIMESTAMPTZ,
            CONSTRAINT ck_complaint_appeal_requires_decision
                CHECK (case_type <> 'appeal_decision' OR original_decision_id IS NOT NULL),
            CONSTRAINT ck_complaint_closed_requires_reason
                CHECK (status <> 'closed' OR (closure_reason IS NOT NULL AND btrim(closure_reason) <> '')),
            CONSTRAINT ck_complaint_decision_requires_summary
                CHECK (status <> 'decision_made' OR (decision_summary IS NOT NULL AND btrim(decision_summary) <> ''))
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_complaint_cases_provider_status ON complaint_cases(provider_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_complaint_cases_business ON complaint_cases(business_tenant)",
        "CREATE INDEX IF NOT EXISTS idx_complaint_cases_owner ON complaint_cases(assigned_owner_id)",
        "CREATE INDEX IF NOT EXISTS idx_complaint_cases_original_decision ON complaint_cases(original_decision_id)",
        """
        CREATE TABLE IF NOT EXISTS complaint_case_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id UUID NOT NULL REFERENCES complaint_cases(id) ON DELETE CASCADE,
            actor_user_id UUID REFERENCES users(id),
            event_type TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT,
            notes TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_complaint_case_events_case ON complaint_case_events(case_id, created_at)",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    statements = [
        "DROP INDEX IF EXISTS idx_complaint_case_events_case",
        "DROP TABLE IF EXISTS complaint_case_events",
        "DROP INDEX IF EXISTS idx_complaint_cases_original_decision",
        "DROP INDEX IF EXISTS idx_complaint_cases_owner",
        "DROP INDEX IF EXISTS idx_complaint_cases_business",
        "DROP INDEX IF EXISTS idx_complaint_cases_provider_status",
        "DROP TABLE IF EXISTS complaint_cases",
    ]
    for statement in statements:
        op.execute(statement)
