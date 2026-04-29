"""drop self_assessments table — feature removed

Revision ID: 015_drop_self_assessments
Revises: 014_workflow_integrity
Create Date: 2026-04-28
"""
from typing import Sequence, Union
from alembic import op

revision: str = "015_drop_self_assessments"
down_revision: Union[str, None] = "014_workflow_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_self_assessments_updated_at ON self_assessments;")
    op.execute("DROP INDEX IF EXISTS idx_self_assessments_tenant;")
    op.execute("DROP TABLE IF EXISTS self_assessments CASCADE;")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE self_assessments (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL,
            template_id UUID REFERENCES audit_checklist_templates(id),
            standard VARCHAR(100),
            name VARCHAR(255),
            items JSONB NOT NULL DEFAULT '[]',
            score INTEGER,
            total_items INTEGER DEFAULT 0,
            passed_items INTEGER DEFAULT 0,
            status VARCHAR(20) DEFAULT 'in_progress' CHECK (status IN ('in_progress','completed')),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_self_assessments_tenant ON self_assessments(tenant_id);")
    op.execute("""
        CREATE TRIGGER update_self_assessments_updated_at BEFORE UPDATE ON self_assessments
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
