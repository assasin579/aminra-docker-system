"""Module registry for composable modular-monolith tenants.

Revision ID: 041_module_registry
Revises: 040_public_trace_id
Create Date: 2026-09-16
"""

from alembic import op

revision = "041_module_registry"
down_revision = "040_public_trace_id"
branch_labels = None
depends_on = None

UP_SQL = [
    'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"',
    """
    CREATE TABLE IF NOT EXISTS modules (
        id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        code            VARCHAR(80) UNIQUE NOT NULL,
        name_vi         VARCHAR(255) NOT NULL,
        name_en         VARCHAR(255),
        category        VARCHAR(80) NOT NULL,
        summary         TEXT,
        maturity_level  VARCHAR(30) NOT NULL DEFAULT 'beta'
            CHECK (maturity_level IN ('planned', 'alpha', 'beta', 'stable')),
        enabled         BOOLEAN NOT NULL DEFAULT true,
        display_order   INTEGER NOT NULL DEFAULT 0,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_modules_enabled_order
      ON modules(enabled, display_order, code)
    """,
    """
    CREATE TABLE IF NOT EXISTS business_model_modules (
        industry_schema_id UUID NOT NULL REFERENCES industry_schemas(id) ON DELETE CASCADE,
        module_id          UUID NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
        required           BOOLEAN NOT NULL DEFAULT false,
        default_enabled    BOOLEAN NOT NULL DEFAULT true,
        display_order      INTEGER NOT NULL DEFAULT 0,
        config_schema      JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (industry_schema_id, module_id),
        CHECK (required = false OR default_enabled = true)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_business_model_modules_industry_order
      ON business_model_modules(industry_schema_id, display_order)
    """,
    """
    CREATE TABLE IF NOT EXISTS tenant_modules (
        tenant_id       UUID NOT NULL,
        module_id       UUID NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
        status          VARCHAR(30) NOT NULL
            CHECK (status IN ('enabled', 'disabled', 'trial', 'locked')),
        source          VARCHAR(40) NOT NULL
            CHECK (source IN ('business_model_default', 'admin_override', 'migration', 'plan')),
        config          JSONB NOT NULL DEFAULT '{}'::jsonb,
        enabled_at      TIMESTAMPTZ,
        disabled_at     TIMESTAMPTZ,
        updated_by      UUID REFERENCES users(id) ON DELETE SET NULL,
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (tenant_id, module_id),
        CHECK (
            (status IN ('enabled', 'trial') AND enabled_at IS NOT NULL)
            OR (status IN ('disabled', 'locked') AND disabled_at IS NOT NULL)
        )
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_tenant_modules_tenant_status
      ON tenant_modules(tenant_id, status)
    """,
    """
    CREATE TABLE IF NOT EXISTS module_dependencies (
        module_id             UUID NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
        depends_on_module_id  UUID NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
        dependency_type       VARCHAR(30) NOT NULL
            CHECK (dependency_type IN ('required', 'optional', 'enhances')),
        created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (module_id, depends_on_module_id),
        CHECK (module_id <> depends_on_module_id)
    )
    """,
    """
    INSERT INTO modules (code, name_vi, name_en, category, summary, maturity_level, enabled, display_order)
    VALUES
      ('certification_dossier', 'Hồ sơ chứng nhận', 'Certification dossier', 'certification', 'Hồ sơ, submission, review, revision và certification workflow.', 'beta', true, 10),
      ('document_management', 'Quản lý tài liệu', 'Document management', 'certification', 'Upload, quản lý tài liệu, template/PDF render và versioning.', 'beta', true, 20),
      ('supplier_management', 'Quản lý nhà cung cấp', 'Supplier management', 'operations', 'Nhà cung cấp, chứng chỉ NCC, eligibility và supplier portal.', 'beta', true, 30),
      ('traceability', 'Truy xuất nguồn gốc', 'Traceability', 'operations', 'Nguyên liệu, lô sản xuất, batch steps, sealing và trace data.', 'beta', true, 40),
      ('process_digitization', 'Số hóa quy trình', 'Process digitization', 'operations', 'Định nghĩa quy trình sản xuất/dịch vụ và luồng step workflow.', 'beta', true, 50),
      ('workforce', 'Nhân sự và phân quyền vận hành', 'Workforce', 'operations', 'Members, auditors, assignments; mở rộng training/competency sau.', 'beta', true, 60),
      ('daily_operations', 'Vận hành hằng ngày', 'Daily operations', 'operations', 'Checklist/log/CAPA/approval vận hành hằng ngày theo mô hình kinh doanh.', 'planned', true, 70),
      ('audit_compliance', 'Audit và tuân thủ', 'Audit and compliance', 'assurance', 'Audit templates, visits, findings, evidence và compliance checks.', 'beta', true, 80),
      ('public_trace', 'QR truy xuất công khai', 'Public trace', 'trust', 'Public QR/trace từ sealed snapshots phục vụ buyer trust.', 'alpha', true, 90),
      ('notifications', 'Thông báo', 'Notifications', 'core', 'In-app/web-push/email notifications cho workflow.', 'beta', true, 100)
    ON CONFLICT (code) DO UPDATE SET
      name_vi = EXCLUDED.name_vi,
      name_en = EXCLUDED.name_en,
      category = EXCLUDED.category,
      summary = EXCLUDED.summary,
      maturity_level = EXCLUDED.maturity_level,
      enabled = EXCLUDED.enabled,
      display_order = EXCLUDED.display_order,
      updated_at = NOW()
    """,
    """
    INSERT INTO business_model_modules
      (industry_schema_id, module_id, required, default_enabled, display_order)
    SELECT i.id, m.id, v.required, v.default_enabled, v.display_order
    FROM (VALUES
      ('food_manufacturing', 'certification_dossier', true,  true,  10),
      ('food_manufacturing', 'document_management',    true,  true,  20),
      ('food_manufacturing', 'supplier_management',    true,  true,  30),
      ('food_manufacturing', 'traceability',           true,  true,  40),
      ('food_manufacturing', 'process_digitization',   true,  true,  50),
      ('food_manufacturing', 'audit_compliance',       true,  true,  60),
      ('food_manufacturing', 'notifications',          true,  true,  70),
      ('food_manufacturing', 'daily_operations',       false, false, 80),
      ('food_manufacturing', 'workforce',              false, false, 90),
      ('food_manufacturing', 'public_trace',           false, false, 100),

      ('restaurant_hotel', 'certification_dossier', true,  true,  10),
      ('restaurant_hotel', 'document_management',    true,  true,  20),
      ('restaurant_hotel', 'supplier_management',    true,  true,  30),
      ('restaurant_hotel', 'daily_operations',       true,  true,  40),
      ('restaurant_hotel', 'workforce',              true,  true,  50),
      ('restaurant_hotel', 'audit_compliance',       true,  true,  60),
      ('restaurant_hotel', 'notifications',          true,  true,  70),
      ('restaurant_hotel', 'traceability',           false, false, 80),
      ('restaurant_hotel', 'process_digitization',   false, false, 90),
      ('restaurant_hotel', 'public_trace',           false, false, 100),

      ('livestock_slaughter', 'certification_dossier', true,  true,  10),
      ('livestock_slaughter', 'document_management',    true,  true,  20),
      ('livestock_slaughter', 'supplier_management',    true,  true,  30),
      ('livestock_slaughter', 'traceability',           true,  true,  40),
      ('livestock_slaughter', 'process_digitization',   true,  true,  50),
      ('livestock_slaughter', 'workforce',              true,  true,  60),
      ('livestock_slaughter', 'daily_operations',       true,  true,  70),
      ('livestock_slaughter', 'audit_compliance',       true,  true,  80),
      ('livestock_slaughter', 'notifications',          true,  true,  90),
      ('livestock_slaughter', 'public_trace',           false, false, 100)
    ) AS v(industry_code, module_code, required, default_enabled, display_order)
    JOIN industry_schemas i ON i.code = v.industry_code
    JOIN modules m ON m.code = v.module_code
    ON CONFLICT (industry_schema_id, module_id) DO UPDATE SET
      required = EXCLUDED.required,
      default_enabled = EXCLUDED.default_enabled,
      display_order = EXCLUDED.display_order,
      updated_at = NOW()
    """,
    """
    INSERT INTO module_dependencies (module_id, depends_on_module_id, dependency_type)
    SELECT m.id, d.id, v.dependency_type
    FROM (VALUES
      ('traceability', 'supplier_management', 'required'),
      ('public_trace', 'traceability', 'required'),
      ('process_digitization', 'traceability', 'enhances'),
      ('daily_operations', 'workforce', 'enhances')
    ) AS v(module_code, depends_on_code, dependency_type)
    JOIN modules m ON m.code = v.module_code
    JOIN modules d ON d.code = v.depends_on_code
    ON CONFLICT (module_id, depends_on_module_id) DO UPDATE SET
      dependency_type = EXCLUDED.dependency_type
    """,
    """
    INSERT INTO tenant_modules
      (tenant_id, module_id, status, source, enabled_at, disabled_at)
    SELECT selected_tenants.tenant_id,
           bmm.module_id,
           CASE WHEN bmm.default_enabled THEN 'enabled' ELSE 'disabled' END AS status,
           'migration' AS source,
           CASE WHEN bmm.default_enabled THEN NOW() ELSE NULL END AS enabled_at,
           CASE WHEN bmm.default_enabled THEN NULL ELSE NOW() END AS disabled_at
    FROM (
      SELECT DISTINCT ON (tenant_id) tenant_id, industry_schema_id
      FROM users
      WHERE tenant_id IS NOT NULL AND industry_schema_id IS NOT NULL
      ORDER BY tenant_id, is_owner DESC, created_at ASC
    ) AS selected_tenants
    JOIN business_model_modules bmm
      ON bmm.industry_schema_id = selected_tenants.industry_schema_id
    ON CONFLICT (tenant_id, module_id) DO NOTHING
    """,
]

DOWN_SQL = [
    "DROP TABLE IF EXISTS tenant_modules CASCADE",
    "DROP TABLE IF EXISTS module_dependencies CASCADE",
    "DROP TABLE IF EXISTS business_model_modules CASCADE",
    "DROP TABLE IF EXISTS modules CASCADE",
]


def upgrade() -> None:
    for sql in UP_SQL:
        op.execute(sql)


def downgrade() -> None:
    for sql in DOWN_SQL:
        op.execute(sql)
