"""conflicts of interest

Revision ID: 048_conflicts_interest
Revises: 047_cert_decisions
Create Date: 2026-09-23
"""

from alembic import op

revision = "048_conflicts_interest"
down_revision = "047_cert_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS conflict_declarations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            provider_id UUID NOT NULL,
            business_tenant UUID NOT NULL,
            person_user_id UUID NOT NULL REFERENCES users(id),
            person_role TEXT NOT NULL CHECK (person_role IN ('auditor','reviewer','decision_maker','cb_admin')),
            conflict_type TEXT NOT NULL CHECK (conflict_type IN ('prior_employment','consultancy','financial_interest','family_relationship','ownership','other')),
            description TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('declared','under_review','cleared','blocked','overridden')),
            declared_by UUID NOT NULL REFERENCES users(id),
            reviewed_by UUID REFERENCES users(id),
            review_reason TEXT,
            valid_from DATE,
            valid_until DATE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS conflict_overrides (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            declaration_id UUID NOT NULL REFERENCES conflict_declarations(id) ON DELETE CASCADE,
            overridden_by UUID NOT NULL REFERENCES users(id),
            override_reason TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_conflict_decl_provider ON conflict_declarations(provider_id)",
        "CREATE INDEX IF NOT EXISTS idx_conflict_decl_business ON conflict_declarations(business_tenant)",
        "CREATE INDEX IF NOT EXISTS idx_conflict_decl_person ON conflict_declarations(person_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_conflict_decl_status ON conflict_declarations(status)",
        """
        CREATE INDEX IF NOT EXISTS idx_conflict_decl_unresolved
        ON conflict_declarations(provider_id, business_tenant, person_user_id, status)
        WHERE status IN ('declared','under_review','blocked')
        """,
        "CREATE INDEX IF NOT EXISTS idx_conflict_overrides_declaration ON conflict_overrides(declaration_id)",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    statements = [
        "DROP INDEX IF EXISTS idx_conflict_overrides_declaration",
        "DROP INDEX IF EXISTS idx_conflict_decl_unresolved",
        "DROP INDEX IF EXISTS idx_conflict_decl_status",
        "DROP INDEX IF EXISTS idx_conflict_decl_person",
        "DROP INDEX IF EXISTS idx_conflict_decl_business",
        "DROP INDEX IF EXISTS idx_conflict_decl_provider",
        "DROP TABLE IF EXISTS conflict_overrides",
        "DROP TABLE IF EXISTS conflict_declarations",
    ]
    for statement in statements:
        op.execute(statement)
