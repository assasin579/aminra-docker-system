"""Industry schemas (admin-managed CRUD) + tenant assignment.

NEW TABLES — industry_schemas, schema_doc_types
  Powers the multi-industry roadmap (TASK #19). Admin CRUD industry
  definitions; business users assign their tenant to one schema during
  onboarding; doc_type list filtered per schema.

  Phase 1: 3 schemas seeded (food_manufacturing, restaurant_hotel,
  livestock_slaughter), all share existing 13 doc_types.
  Phase 2 (defer): per-industry doc_type divergence when pilot CB
  demands industry-specific scheme (e.g. MPPHM slaughter SOP).

users — 1 new column
  industry_schema_id  UUID  FK industry_schemas — set during onboarding,
                            locked after first cert issued (admin override
                            with audit log).

Revision ID: 028_industry_schemas
Revises: 027_audit_missing_schema
Create Date: 2026-05-10
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "028_industry_schemas"
down_revision: Union[str, None] = "027_audit_missing_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── industry_schemas table ───────────────────────────────────────────────
    op.execute("""
        CREATE TABLE industry_schemas (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            code            VARCHAR(50) UNIQUE NOT NULL,
            name_vi         VARCHAR(255) NOT NULL,
            name_en         VARCHAR(255),
            description     TEXT,
            jakim_scheme    VARCHAR(100),
            icon            VARCHAR(50),
            enabled         BOOLEAN NOT NULL DEFAULT true,
            display_order   INTEGER NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by      UUID REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE INDEX idx_industry_schemas_enabled ON industry_schemas(enabled, display_order);
    """)

    # ── schema_doc_types junction (M:N) ──────────────────────────────────────
    op.execute("""
        CREATE TABLE schema_doc_types (
            schema_id       UUID NOT NULL REFERENCES industry_schemas(id) ON DELETE CASCADE,
            doc_type        VARCHAR(100) NOT NULL,
            required        BOOLEAN NOT NULL DEFAULT true,
            display_order   INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (schema_id, doc_type)
        );
        CREATE INDEX idx_schema_doc_types_schema ON schema_doc_types(schema_id, display_order);
    """)

    # ── users.industry_schema_id ─────────────────────────────────────────────
    op.execute("""
        ALTER TABLE users
        ADD COLUMN industry_schema_id UUID REFERENCES industry_schemas(id) ON DELETE SET NULL;
        CREATE INDEX idx_users_industry_schema ON users(industry_schema_id);
    """)

    # ── Seed Phase 1: 3 enabled schemas ──────────────────────────────────────
    # All 3 share the existing 13 doc_types per user clarification 2026-05-10.
    op.execute("""
        INSERT INTO industry_schemas (code, name_vi, name_en, description, jakim_scheme, icon, display_order)
        VALUES
          ('food_manufacturing',
           'Cơ sở sản xuất thực phẩm',
           'Food Manufacturing',
           'Halal coffee, bánh mì, bánh bao, đồ uống, thực phẩm chế biến đóng gói. Áp dụng cho cơ sở sản xuất, đóng gói, phân phối thực phẩm Halal.',
           'MS 1500:2019 + MS 1480',
           'factory',
           1),
          ('restaurant_hotel',
           'Nhà hàng - Khách sạn Halal',
           'Restaurant & Hotel',
           'Cơ sở dịch vụ ăn uống, lưu trú phục vụ khách Hồi giáo. Bao gồm nhà hàng, khách sạn, cafe, catering, bếp tập thể.',
           'MS 1500 + supplemental',
           'restaurant',
           2),
          ('livestock_slaughter',
           'Cơ sở chăn nuôi - Giết mổ động vật',
           'Livestock & Slaughter',
           'Trang trại chăn nuôi và cơ sở giết mổ Halal động vật theo MPPHM. Bao gồm gia cầm, gia súc, thủy sản giết mổ Halal.',
           'MPPHM + MS 1500 §6',
           'cow',
           3);
    """)

    # ── Seed schema_doc_types: all 3 schemas share 13 doc_types ──────────────
    op.execute("""
        INSERT INTO schema_doc_types (schema_id, doc_type, required, display_order)
        SELECT s.id, dt.code, true, dt.ord
        FROM industry_schemas s
        CROSS JOIN (VALUES
          ('company_profile', 1),
          ('halal_policy', 2),
          ('has_manual', 3),
          ('internal_halal_committee', 4),
          ('ingredient_raw_material', 5),
          ('process_flow_chart', 6),
          ('sop_personal_hygiene', 7),
          ('sop_cleaning_sanitation', 8),
          ('sop_pest_control', 9),
          ('sop_supplier_evaluation', 10),
          ('sop_traceability', 11),
          ('sop_complaint_handling', 12),
          ('generic', 13)
        ) AS dt(code, ord)
        WHERE s.code IN ('food_manufacturing', 'restaurant_hotel', 'livestock_slaughter');
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_industry_schema;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS industry_schema_id;")
    op.execute("DROP INDEX IF EXISTS idx_schema_doc_types_schema;")
    op.execute("DROP TABLE IF EXISTS schema_doc_types;")
    op.execute("DROP INDEX IF EXISTS idx_industry_schemas_enabled;")
    op.execute("DROP TABLE IF EXISTS industry_schemas;")
