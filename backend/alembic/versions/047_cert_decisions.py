"""certification decisions

Revision ID: 047_cert_decisions
Revises: 046_module_activation_escal
Create Date: 2026-09-23
"""

from alembic import op

revision = "047_cert_decisions"
down_revision = "046_module_activation_escal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS certification_decisions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            submission_id UUID NOT NULL REFERENCES submissions(id),
            business_tenant UUID NOT NULL,
            provider_id UUID NOT NULL,
            audit_visit_id UUID REFERENCES audit_visits(id),
            status TEXT NOT NULL CHECK (status IN ('pending_review','approved','rejected','cancelled')),
            reviewer_id UUID REFERENCES users(id),
            decision_maker_id UUID REFERENCES users(id),
            decision_reason TEXT,
            decision_notes TEXT,
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            decided_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_certification_decisions_final_requires_decision
                CHECK (
                    status NOT IN ('approved','rejected')
                    OR (
                        decision_maker_id IS NOT NULL
                        AND decision_reason IS NOT NULL
                        AND btrim(decision_reason) <> ''
                        AND decided_at IS NOT NULL
                    )
                )
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_certification_decisions_provider_status ON certification_decisions(provider_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_certification_decisions_submission ON certification_decisions(submission_id)",
        "CREATE INDEX IF NOT EXISTS idx_certification_decisions_business ON certification_decisions(business_tenant)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_certification_decisions_submission_active ON certification_decisions(submission_id) WHERE status IN ('pending_review','approved')",
        """
        CREATE TABLE IF NOT EXISTS certification_decision_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            decision_id UUID NOT NULL REFERENCES certification_decisions(id) ON DELETE CASCADE,
            action TEXT NOT NULL,
            actor_id UUID NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_certification_decision_events_decision ON certification_decision_events(decision_id, created_at)",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    statements = [
        "DROP INDEX IF EXISTS idx_certification_decision_events_decision",
        "DROP TABLE IF EXISTS certification_decision_events",
        "DROP INDEX IF EXISTS uq_certification_decisions_submission_active",
        "DROP INDEX IF EXISTS idx_certification_decisions_business",
        "DROP INDEX IF EXISTS idx_certification_decisions_submission",
        "DROP INDEX IF EXISTS idx_certification_decisions_provider_status",
        "DROP TABLE IF EXISTS certification_decisions",
    ]
    for statement in statements:
        op.execute(statement)
