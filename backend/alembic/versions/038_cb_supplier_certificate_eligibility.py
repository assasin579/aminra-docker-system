"""CB-authoritative supplier certificate eligibility.

Revision ID: 038_cb_supplier_eligibility
Revises: 037_seed_admin_bootstrap
Create Date: 2026-09-06
"""

from alembic import op

revision = "038_cb_supplier_eligibility"
down_revision = "037_seed_admin_bootstrap"
branch_labels = None
depends_on = None

UP_SQL = [
    """
    CREATE TYPE supplier_certificate_status AS ENUM
      ('active','expired','suspended','revoked','pending_review')
    """,
    """
    CREATE TABLE supplier_eligibilities (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
        tenant_id UUID NOT NULL,
        certificate_no VARCHAR(255) NOT NULL,
        issuer_name VARCHAR(255) NOT NULL,
        status supplier_certificate_status NOT NULL DEFAULT 'pending_review',
        valid_from DATE NOT NULL,
        valid_until DATE NOT NULL,
        scope JSONB NOT NULL DEFAULT '{}'::jsonb,
        source_of_truth VARCHAR(50) NOT NULL DEFAULT 'cb',
        changed_at TIMESTAMPTZ DEFAULT NOW(),
        changed_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
        reason TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT supplier_eligibilities_valid_range_check CHECK (valid_until >= valid_from),
        CONSTRAINT supplier_eligibilities_one_per_supplier UNIQUE (supplier_id),
        CONSTRAINT supplier_eligibilities_scope_object_check CHECK (jsonb_typeof(scope) = 'object')
    )
    """,
    """
    CREATE TABLE supply_relationships (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        buyer_tenant_id UUID NOT NULL,
        supplier_tenant_id UUID NULL,
        supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
        material_category VARCHAR(100) NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'active'
            CHECK (status IN ('active','paused','ended')),
        last_purchase_at TIMESTAMPTZ NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE certificate_risk_alerts (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        impacted_tenant_id UUID NOT NULL,
        supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
        certificate_id UUID NOT NULL REFERENCES supplier_eligibilities(id) ON DELETE CASCADE,
        event_type VARCHAR(50) NOT NULL,
        severity VARCHAR(20) NOT NULL DEFAULT 'high'
            CHECK (severity IN ('info','medium','high','critical')),
        message TEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'open'
            CHECK (status IN ('open','acknowledged','resolved')),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX idx_supplier_eligibilities_tenant_supplier_status_dates ON supplier_eligibilities(tenant_id, supplier_id, status, valid_from, valid_until)",
    "CREATE INDEX idx_supplier_eligibilities_status_valid_until ON supplier_eligibilities(status, valid_until)",
    "CREATE INDEX idx_supply_relationships_supplier_active ON supply_relationships(supplier_id, status, buyer_tenant_id)",
    "CREATE INDEX idx_supply_relationships_buyer_active ON supply_relationships(buyer_tenant_id, status, supplier_id)",
    "CREATE INDEX idx_certificate_risk_alerts_impacted_status ON certificate_risk_alerts(impacted_tenant_id, status, created_at DESC)",
    "CREATE INDEX idx_certificate_risk_alerts_supplier_cert ON certificate_risk_alerts(supplier_id, certificate_id)",
    "CREATE TRIGGER update_supplier_eligibilities_updated_at BEFORE UPDATE ON supplier_eligibilities FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    "CREATE TRIGGER update_certificate_risk_alerts_updated_at BEFORE UPDATE ON certificate_risk_alerts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
]

DOWN_SQL = [
    "DROP TABLE IF EXISTS certificate_risk_alerts CASCADE",
    "DROP TABLE IF EXISTS supply_relationships CASCADE",
    "DROP TABLE IF EXISTS supplier_eligibilities CASCADE",
    "DROP TYPE IF EXISTS supplier_certificate_status",
]


def upgrade() -> None:
    for sql in UP_SQL:
        op.execute(sql)


def downgrade() -> None:
    for sql in DOWN_SQL:
        op.execute(sql)
