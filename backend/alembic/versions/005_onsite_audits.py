"""onsite audits: templates, visits, checklist items, NCR

Revision ID: 005_onsite_audits
Revises: 004_provider_features
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "005_onsite_audits"
down_revision: Union[str, None] = "004_provider_features"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Checklist templates ──
    op.execute("""
        CREATE TABLE audit_checklist_templates (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            provider_id UUID NOT NULL REFERENCES users(id),
            name VARCHAR(255) NOT NULL,
            standard VARCHAR(100),
            items JSONB NOT NULL DEFAULT '[]',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── Audit visits ──
    op.execute("""
        CREATE TABLE audit_visits (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            business_tenant UUID NOT NULL,
            provider_id UUID NOT NULL REFERENCES users(id),
            auditor_id UUID REFERENCES users(id),
            template_id UUID REFERENCES audit_checklist_templates(id),
            visit_type VARCHAR(20) NOT NULL CHECK (visit_type IN ('initial','renewal','surprise')),
            status VARCHAR(30) DEFAULT 'scheduled' CHECK (status IN ('scheduled','in_progress','completed','report_submitted')),
            scheduled_date DATE NOT NULL,
            location TEXT,
            notes TEXT,
            auditor_signature_path TEXT,
            business_signature_path TEXT,
            start_gps JSONB,
            end_gps JSONB,
            report_pdf_path TEXT,
            compliance_score INTEGER CHECK (compliance_score >= 0 AND compliance_score <= 100),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── Checklist items per visit ──
    op.execute("""
        CREATE TABLE audit_visit_items (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            visit_id UUID NOT NULL REFERENCES audit_visits(id) ON DELETE CASCADE,
            code VARCHAR(20),
            category VARCHAR(255) NOT NULL,
            criteria TEXT NOT NULL,
            severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical','major','minor')),
            result VARCHAR(20) CHECK (result IN ('conform','minor_nc','major_nc','na','observation')),
            clause TEXT,
            audit_method TEXT,
            documents TEXT,
            evidence TEXT,
            corrective_action TEXT,
            corrective_status VARCHAR(20) CHECK (corrective_status IN ('pending','in_progress','completed')),
            note TEXT,
            photo_paths JSONB DEFAULT '[]',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── Non-Conformance Reports ──
    op.execute("""
        CREATE TABLE audit_ncr (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            visit_id UUID NOT NULL REFERENCES audit_visits(id) ON DELETE CASCADE,
            item_id UUID REFERENCES audit_visit_items(id),
            description TEXT NOT NULL,
            severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical','major','minor')),
            photo_paths JSONB DEFAULT '[]',
            corrective_action TEXT,
            deadline DATE,
            status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open','in_review','closed')),
            evidence_paths JSONB DEFAULT '[]',
            closed_at TIMESTAMPTZ,
            closed_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── Indexes ──
    op.execute("CREATE INDEX idx_audit_templates_provider ON audit_checklist_templates(provider_id);")
    op.execute("CREATE INDEX idx_audit_visits_provider ON audit_visits(provider_id);")
    op.execute("CREATE INDEX idx_audit_visits_auditor ON audit_visits(auditor_id);")
    op.execute("CREATE INDEX idx_audit_visits_business ON audit_visits(business_tenant);")
    op.execute("CREATE INDEX idx_audit_visits_status ON audit_visits(status);")
    op.execute("CREATE INDEX idx_audit_visit_items_visit ON audit_visit_items(visit_id);")
    op.execute("CREATE INDEX idx_audit_ncr_visit ON audit_ncr(visit_id);")
    op.execute("CREATE INDEX idx_audit_ncr_status ON audit_ncr(status);")

    # ── Triggers ──
    op.execute("""
        CREATE TRIGGER update_audit_checklist_templates_updated_at BEFORE UPDATE ON audit_checklist_templates
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    op.execute("""
        CREATE TRIGGER update_audit_visits_updated_at BEFORE UPDATE ON audit_visits
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    op.execute("""
        CREATE TRIGGER update_audit_ncr_updated_at BEFORE UPDATE ON audit_ncr
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_ncr CASCADE;")
    op.execute("DROP TABLE IF EXISTS audit_visit_items CASCADE;")
    op.execute("DROP TABLE IF EXISTS audit_visits CASCADE;")
    op.execute("DROP TABLE IF EXISTS audit_checklist_templates CASCADE;")
