"""Split standard_type from industry_schema (TASK #19 refactor).

User clarification 2026-05-10: industry_schemas chỉ là LOẠI NGÀNH NGHỀ
(restaurant, food manufacturing, livestock). TIÊU CHUẨN ÁP DỤNG (MS 1500,
MS 1480, MPPHM, etc.) là object riêng — mỗi HỒ SƠ chọn 1 tiêu chuẩn, và
tiêu chuẩn quy định số lượng + loại doc.

NEW TABLES:
  standard_types       — bảng tiêu chuẩn (MS 1500:2019, MS 1480, MPPHM, ...)
  standard_doc_types   — doc_types per standard (M:N replaces schema_doc_types semantic)
  industry_standards   — M:N industries ↔ standards (1 industry có nhiều standards)
  dossiers             — instance of "hồ sơ" với chosen standard_type

DATA MIGRATION:
  - Seed 5 base standards (JAKIM/MUI/MPPHM family)
  - Copy doc_types từ schema_doc_types → standard_doc_types (gắn vào MS_1500_2019 — phân lớn schemes hiện share)
  - Map industry_standards default mappings
  - Keep industry_schemas.jakim_scheme nullable (deprecated, FE no longer reads)

Revision ID: 029_standard_types_split
Revises: 028_industry_schemas
Create Date: 2026-05-10
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "029_standard_types_split"
down_revision: Union[str, None] = "028_industry_schemas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── standard_types: tiêu chuẩn áp dụng ──────────────────────────────────
    op.execute("""
        CREATE TABLE standard_types (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            code            VARCHAR(50) UNIQUE NOT NULL,
            name_vi         VARCHAR(255) NOT NULL,
            name_en         VARCHAR(255),
            organization    VARCHAR(100),
            scheme_version  VARCHAR(50),
            description     TEXT,
            full_text_url   TEXT,
            enabled         BOOLEAN NOT NULL DEFAULT true,
            display_order   INTEGER NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by      UUID REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE INDEX idx_standard_types_enabled ON standard_types(enabled, display_order);
    """)

    # ── standard_doc_types: doc_types per standard ──────────────────────────
    op.execute("""
        CREATE TABLE standard_doc_types (
            standard_type_id UUID NOT NULL REFERENCES standard_types(id) ON DELETE CASCADE,
            doc_type         VARCHAR(100) NOT NULL,
            required         BOOLEAN NOT NULL DEFAULT true,
            display_order    INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (standard_type_id, doc_type)
        );
        CREATE INDEX idx_standard_doc_types_std ON standard_doc_types(standard_type_id, display_order);
    """)

    # ── industry_standards: M:N industry ↔ standard ─────────────────────────
    op.execute("""
        CREATE TABLE industry_standards (
            industry_schema_id UUID NOT NULL REFERENCES industry_schemas(id) ON DELETE CASCADE,
            standard_type_id   UUID NOT NULL REFERENCES standard_types(id) ON DELETE CASCADE,
            is_default         BOOLEAN NOT NULL DEFAULT false,
            display_order      INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (industry_schema_id, standard_type_id)
        );
        CREATE INDEX idx_industry_standards_industry ON industry_standards(industry_schema_id, display_order);
    """)

    # ── dossiers: instance of "hồ sơ" với chosen standard ───────────────────
    op.execute("""
        CREATE TABLE dossiers (
            id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id         UUID NOT NULL,
            standard_type_id  UUID REFERENCES standard_types(id) ON DELETE SET NULL,
            title             VARCHAR(255) NOT NULL,
            status            VARCHAR(50) NOT NULL DEFAULT 'draft',
            notes             TEXT,
            created_by        UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_dossiers_tenant ON dossiers(tenant_id, status, created_at DESC);
        CREATE INDEX idx_dossiers_standard ON dossiers(standard_type_id);
    """)

    # ── Seed: 5 base standards ──────────────────────────────────────────────
    op.execute("""
        INSERT INTO standard_types (code, name_vi, name_en, organization, scheme_version, description, display_order)
        VALUES
          ('ms_1500_2019',
           'MS 1500:2019 — Sản phẩm Halal Tổng quát',
           'MS 1500:2019 — General Halal Products',
           'JAKIM',
           '2019',
           'Tiêu chuẩn cốt lõi JAKIM cho sản phẩm Halal: nguyên liệu, chế biến, đóng gói, lưu kho, vận chuyển. Áp dụng cho hầu hết các ngành thực phẩm và dịch vụ ăn uống Halal.',
           1),
          ('ms_1480_2007',
           'MS 1480:2007 — An toàn Thực phẩm dựa trên HACCP',
           'MS 1480:2007 — Food Safety based on HACCP',
           'JAKIM',
           '2007',
           'Tiêu chuẩn HACCP áp dụng cho cơ sở sản xuất thực phẩm Halal. Thường đi kèm MS 1500 cho ngành chế biến thực phẩm.',
           2),
          ('mpphm_2020',
           'MPPHM — Quy phạm Halal Malaysia',
           'MPPHM — Malaysian Halal Compliance',
           'JAKIM',
           '2020',
           'Quy phạm Halal Malaysia (Manual Prosedur Pensijilan Halal Malaysia) — áp dụng riêng cho cơ sở chăn nuôi và giết mổ động vật. Bao gồm yêu cầu về stunning, đường cắt, phương pháp giết mổ.',
           3),
          ('ms_2424_2019',
           'MS 2424:2019 — Dược phẩm Halal',
           'MS 2424:2019 — Halal Pharmaceuticals',
           'JAKIM',
           '2019',
           'Tiêu chuẩn JAKIM cho dược phẩm Halal: nguồn nguyên liệu, capsule (gelatin gốc động vật), tá dược, dung môi (cồn).',
           4),
          ('ms_2200_2_2013',
           'MS 2200-2:2013 — Mỹ phẩm Halal',
           'MS 2200-2:2013 — Halal Cosmetics',
           'JAKIM',
           '2013',
           'Tiêu chuẩn JAKIM cho mỹ phẩm Halal: nguyên liệu gốc động vật, cồn ethanol, animal origin disclosure, packaging.',
           5);
    """)

    # ── Seed standard_doc_types: clone từ schema_doc_types ────────────────
    # Phase 1: cả 3 industry hiện đang share cùng 13 doc_types — clone tất cả
    # 13 vào MS_1500_2019 (default standard cho food + restaurant), và cũng
    # vào MPPHM (livestock thường dùng kết hợp MS 1500 + MPPHM).
    op.execute("""
        INSERT INTO standard_doc_types (standard_type_id, doc_type, required, display_order)
        SELECT s.id, dt.code, true, dt.ord
        FROM standard_types s
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
        WHERE s.code IN ('ms_1500_2019', 'mpphm_2020', 'ms_1480_2007');

        -- Pharma + cosmetic standards: chỉ 5 doc cơ bản Phase 1 (sẽ mở rộng khi
        -- enable industry pharma/cosmetic real)
        INSERT INTO standard_doc_types (standard_type_id, doc_type, required, display_order)
        SELECT s.id, dt.code, true, dt.ord
        FROM standard_types s
        CROSS JOIN (VALUES
          ('company_profile', 1),
          ('halal_policy', 2),
          ('has_manual', 3),
          ('ingredient_raw_material', 4),
          ('generic', 5)
        ) AS dt(code, ord)
        WHERE s.code IN ('ms_2424_2019', 'ms_2200_2_2013');
    """)

    # ── Industry ↔ Standard mapping (default per ngành) ─────────────────────
    op.execute("""
        -- food_manufacturing → MS 1500:2019 (default) + MS 1480:2007 (HACCP companion)
        INSERT INTO industry_standards (industry_schema_id, standard_type_id, is_default, display_order)
        SELECT i.id, s.id,
               CASE WHEN s.code='ms_1500_2019' THEN true ELSE false END,
               s.display_order
        FROM industry_schemas i
        CROSS JOIN standard_types s
        WHERE i.code='food_manufacturing' AND s.code IN ('ms_1500_2019', 'ms_1480_2007');

        -- restaurant_hotel → MS 1500:2019 only (default)
        INSERT INTO industry_standards (industry_schema_id, standard_type_id, is_default, display_order)
        SELECT i.id, s.id, true, s.display_order
        FROM industry_schemas i
        CROSS JOIN standard_types s
        WHERE i.code='restaurant_hotel' AND s.code='ms_1500_2019';

        -- livestock_slaughter → MPPHM (default) + MS 1500 supplemental
        INSERT INTO industry_standards (industry_schema_id, standard_type_id, is_default, display_order)
        SELECT i.id, s.id,
               CASE WHEN s.code='mpphm_2020' THEN true ELSE false END,
               s.display_order
        FROM industry_schemas i
        CROSS JOIN standard_types s
        WHERE i.code='livestock_slaughter' AND s.code IN ('mpphm_2020', 'ms_1500_2019');
    """)

    # ── Deprecate (don't drop yet): industry_schemas.jakim_scheme ───────────
    # FE will stop reading; keep column for rollback safety. Drop in 030 if all clean.
    op.execute("""
        COMMENT ON COLUMN industry_schemas.jakim_scheme IS
          'DEPRECATED 2026-05-10: scheme info moved to standard_types. See industry_standards M:N mapping.';
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_dossiers_standard;")
    op.execute("DROP INDEX IF EXISTS idx_dossiers_tenant;")
    op.execute("DROP TABLE IF EXISTS dossiers;")
    op.execute("DROP INDEX IF EXISTS idx_industry_standards_industry;")
    op.execute("DROP TABLE IF EXISTS industry_standards;")
    op.execute("DROP INDEX IF EXISTS idx_standard_doc_types_std;")
    op.execute("DROP TABLE IF EXISTS standard_doc_types;")
    op.execute("DROP INDEX IF EXISTS idx_standard_types_enabled;")
    op.execute("DROP TABLE IF EXISTS standard_types;")
