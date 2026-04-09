"""provider features: comments, certificates, notifications, evaluations, deadline

Revision ID: 004_provider_features
Revises: 003_supply_chain
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "004_provider_features"
down_revision: Union[str, None] = "003_supply_chain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Submission comments (threaded discussion) ──
    op.execute("""
        CREATE TABLE submission_comments (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            submission_id UUID NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
            author_id UUID NOT NULL REFERENCES users(id),
            author_role VARCHAR(20) NOT NULL,
            author_name VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── Halal certificates ──
    op.execute("""
        CREATE TABLE halal_certificates (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            submission_id UUID NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
            cert_number VARCHAR(100) UNIQUE NOT NULL,
            issued_by UUID NOT NULL REFERENCES users(id),
            business_tenant UUID NOT NULL,
            company_name VARCHAR(255),
            issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
            expiry_date DATE NOT NULL,
            pdf_path TEXT,
            status VARCHAR(50) DEFAULT 'active',
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── In-app notifications ──
    op.execute("""
        CREATE TABLE notifications (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(50) NOT NULL,
            title VARCHAR(255) NOT NULL,
            message TEXT,
            read BOOLEAN DEFAULT false,
            link TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── Auditor evaluation / scoring ──
    op.execute("""
        CREATE TABLE submission_evaluations (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            submission_id UUID NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
            auditor_id UUID NOT NULL REFERENCES users(id),
            checklist JSONB NOT NULL DEFAULT '[]',
            score INTEGER CHECK (score >= 0 AND score <= 100),
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(submission_id, auditor_id)
        );
    """)

    # ── Deadline column on submissions ──
    op.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS deadline TIMESTAMPTZ;")

    # ── Indexes ──
    op.execute("CREATE INDEX idx_comments_submission ON submission_comments(submission_id);")
    op.execute("CREATE INDEX idx_certificates_submission ON halal_certificates(submission_id);")
    op.execute("CREATE INDEX idx_certificates_business ON halal_certificates(business_tenant);")
    op.execute("CREATE INDEX idx_notifications_user_read ON notifications(user_id, read);")
    op.execute("CREATE INDEX idx_evaluations_submission ON submission_evaluations(submission_id);")
    op.execute("CREATE INDEX idx_submissions_deadline ON submissions(deadline);")
    op.execute("CREATE INDEX idx_submissions_auditor ON submissions(auditor_id);")

    # ── Triggers ──
    op.execute("""
        CREATE TRIGGER update_halal_certificates_updated_at BEFORE UPDATE ON halal_certificates
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    op.execute("""
        CREATE TRIGGER update_submission_evaluations_updated_at BEFORE UPDATE ON submission_evaluations
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS submission_evaluations CASCADE;")
    op.execute("DROP TABLE IF EXISTS notifications CASCADE;")
    op.execute("DROP TABLE IF EXISTS halal_certificates CASCADE;")
    op.execute("DROP TABLE IF EXISTS submission_comments CASCADE;")
    op.execute("ALTER TABLE submissions DROP COLUMN IF EXISTS deadline;")
