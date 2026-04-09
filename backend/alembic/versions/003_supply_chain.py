"""supply chain: suppliers, materials, process templates, production batches

Revision ID: 003_supply_chain
Revises: 002_company_profile
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003_supply_chain"
down_revision: Union[str, None] = "002_company_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ──
    op.execute("CREATE TYPE supplier_status AS ENUM ('pending','verified','expired','suspended');")
    op.execute("CREATE TYPE material_risk AS ENUM ('safe','requires_cert','prohibited','unknown');")
    op.execute("CREATE TYPE batch_status AS ENUM ('draft','in_progress','completed','rejected');")

    # ── Suppliers ──
    op.execute("""
        CREATE TABLE suppliers (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL,
            name VARCHAR(255) NOT NULL,
            address TEXT,
            phone VARCHAR(50),
            email VARCHAR(255),
            contact_person VARCHAR(255),
            supplier_type VARCHAR(100),
            status supplier_status DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── Supplier certificates ──
    op.execute("""
        CREATE TABLE supplier_certificates (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL,
            cert_type VARCHAR(100),
            cert_number VARCHAR(255),
            issuing_body VARCHAR(255),
            issued_date DATE,
            expiry_date DATE,
            file_path TEXT,
            original_filename VARCHAR(255),
            file_size BIGINT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── Materials ──
    op.execute("""
        CREATE TABLE materials (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL,
            supplier_id UUID NOT NULL REFERENCES suppliers(id),
            name VARCHAR(255) NOT NULL,
            sku VARCHAR(100),
            category VARCHAR(100),
            halal_risk material_risk DEFAULT 'unknown',
            description TEXT,
            unit VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── Process templates ──
    op.execute("""
        CREATE TABLE process_templates (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            flowchart JSONB NOT NULL DEFAULT '{"nodes":[],"edges":[]}',
            version INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── Production batches ──
    op.execute("""
        CREATE TABLE production_batches (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL,
            batch_code VARCHAR(100) NOT NULL,
            product_name VARCHAR(255) NOT NULL,
            process_template_id UUID REFERENCES process_templates(id),
            status batch_status DEFAULT 'draft',
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            compliance_score INTEGER,
            qr_code_url TEXT,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── Batch ↔ Material link ──
    op.execute("""
        CREATE TABLE batch_materials (
            batch_id UUID NOT NULL REFERENCES production_batches(id) ON DELETE CASCADE,
            material_id UUID NOT NULL REFERENCES materials(id),
            quantity DECIMAL(12,3),
            unit VARCHAR(50),
            PRIMARY KEY (batch_id, material_id)
        );
    """)

    # ── Batch step tracking ──
    op.execute("""
        CREATE TABLE batch_steps (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            batch_id UUID NOT NULL REFERENCES production_batches(id) ON DELETE CASCADE,
            node_id VARCHAR(100) NOT NULL,
            step_name VARCHAR(255) NOT NULL,
            performed_by VARCHAR(255),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            status VARCHAR(50) DEFAULT 'pending',
            notes TEXT,
            photo_path TEXT,
            checklist JSONB DEFAULT '[]',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # ── Indexes ──
    op.execute("CREATE INDEX idx_suppliers_tenant ON suppliers(tenant_id);")
    op.execute("CREATE INDEX idx_materials_tenant ON materials(tenant_id);")
    op.execute("CREATE INDEX idx_materials_supplier ON materials(supplier_id);")
    op.execute("CREATE INDEX idx_production_batches_tenant ON production_batches(tenant_id);")
    op.execute("CREATE INDEX idx_production_batches_status ON production_batches(status);")
    op.execute("CREATE INDEX idx_batch_steps_batch ON batch_steps(batch_id);")
    op.execute("CREATE INDEX idx_supplier_certs_supplier ON supplier_certificates(supplier_id);")
    op.execute("CREATE INDEX idx_supplier_certs_expiry ON supplier_certificates(expiry_date);")

    # ── Triggers (reuse existing update_updated_at_column function) ──
    op.execute("CREATE TRIGGER update_suppliers_updated_at BEFORE UPDATE ON suppliers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();")
    op.execute("CREATE TRIGGER update_materials_updated_at BEFORE UPDATE ON materials FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();")
    op.execute("CREATE TRIGGER update_process_templates_updated_at BEFORE UPDATE ON process_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();")
    op.execute("CREATE TRIGGER update_production_batches_updated_at BEFORE UPDATE ON production_batches FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS batch_steps CASCADE;")
    op.execute("DROP TABLE IF EXISTS batch_materials CASCADE;")
    op.execute("DROP TABLE IF EXISTS production_batches CASCADE;")
    op.execute("DROP TABLE IF EXISTS process_templates CASCADE;")
    op.execute("DROP TABLE IF EXISTS materials CASCADE;")
    op.execute("DROP TABLE IF EXISTS supplier_certificates CASCADE;")
    op.execute("DROP TABLE IF EXISTS suppliers CASCADE;")
    op.execute("DROP TYPE IF EXISTS batch_status;")
    op.execute("DROP TYPE IF EXISTS material_risk;")
    op.execute("DROP TYPE IF EXISTS supplier_status;")
