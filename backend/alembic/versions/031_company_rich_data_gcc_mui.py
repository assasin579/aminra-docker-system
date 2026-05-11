"""Phase 1 — Company rich-data fields + GCC/MUI standards seed.

Two changes bundled (single migration, atomic):

1. users — 15 new columns for company-level placeholder data:
   - founded_year                   INT
   - halal_commitment_statement     TEXT
   - total_employees                INT
   - najis_handling_policy          TEXT
   - cross_contamination_controls   TEXT
   - product_categories             TEXT      (comma-separated, no FK)
   - primary_suppliers              TEXT      (comma-separated)
   - ingredient_origin_countries    TEXT      (comma-separated ISO codes)
   - packaging_materials_brief      TEXT
   - ihc_chairman_name              VARCHAR(255)
   - ihc_chairman_title             VARCHAR(255)
   - ihc_inception_date             DATE
   - ihc_members_brief              TEXT
   - ihc_meeting_frequency          VARCHAR(100)
   - production_capacity_brief      TEXT

   All nullable, all default NULL. Existing rows unaffected.

2. standard_types — seed 4 GCC/MUI standards:
   - UAE.S 2055-1:2015 (UAE/GCC Halal products)
   - GSO 2055-2:2021 (Gulf — animal slaughter)
   - OIC/SMIIC 1:2019 (OIC general Halal food)
   - HAS 23000:2012 (MUI/Indonesia Halal Assurance System)

   All `enabled=true`. Industry mapping NOT seeded — admin maps via /admin/industries
   when targeting specific markets (Gulf / Indonesia export).

Revision ID: 031_company_rich_data_gcc_mui
Revises: 030_documents_dossier_link
Create Date: 2026-05-11
"""
from typing import Sequence, Union
from alembic import op


revision: str = "031_company_rich_data_gcc_mui"
down_revision: Union[str, None] = "030_documents_dossier_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add 15 company-level columns to users
    op.execute("""
        ALTER TABLE users
            ADD COLUMN founded_year                  INT,
            ADD COLUMN halal_commitment_statement    TEXT,
            ADD COLUMN total_employees               INT,
            ADD COLUMN najis_handling_policy         TEXT,
            ADD COLUMN cross_contamination_controls  TEXT,
            ADD COLUMN product_categories            TEXT,
            ADD COLUMN primary_suppliers             TEXT,
            ADD COLUMN ingredient_origin_countries   TEXT,
            ADD COLUMN packaging_materials_brief     TEXT,
            ADD COLUMN ihc_chairman_name             VARCHAR(255),
            ADD COLUMN ihc_chairman_title            VARCHAR(255),
            ADD COLUMN ihc_inception_date            DATE,
            ADD COLUMN ihc_members_brief             TEXT,
            ADD COLUMN ihc_meeting_frequency         VARCHAR(100),
            ADD COLUMN production_capacity_brief     TEXT;
    """)

    # 2. Seed GCC + MUI standards
    op.execute("""
        INSERT INTO standard_types
            (code, name_vi, name_en, organization, scheme_version,
             description, full_text_url, enabled, display_order)
        VALUES
        ('uae_s_2055_1_2015',
         'UAE.S 2055-1:2015 — Halal Products (General requirements)',
         'UAE.S 2055-1:2015 Halal Products — General Requirements',
         'ESMA (UAE)', '2015',
         'Tiêu chuẩn Halal UAE/GCC chung cho sản phẩm Halal. Áp dụng xuất khẩu thị trường Gulf.',
         'https://www.esma.gov.ae/en-us/ESMA/Pages/Standards.aspx',
         true, 100),

        ('gso_2055_2_2021',
         'GSO 2055-2:2021 — Halal Products (Animal slaughter)',
         'GSO 2055-2:2021 Halal Products — Animal Slaughter',
         'GSO (Gulf Standardization Organization)', '2021',
         'Tiêu chuẩn Gulf cho giết mổ động vật Halal. Áp dụng cơ sở chăn nuôi-giết mổ xuất Gulf.',
         'https://www.gso.org.sa',
         true, 101),

        ('oic_smiic_1_2019',
         'OIC/SMIIC 1:2019 — General Halal Food Requirements',
         'OIC/SMIIC 1:2019 General Requirements for Halal Food',
         'SMIIC (OIC)', '2019',
         'Tiêu chuẩn chung Halal food của Tổ chức Hợp tác Hồi giáo (OIC). 57 nước thành viên.',
         'https://www.smiic.org/en/page/119/smiic-standards',
         true, 102),

        ('has_23000_2012',
         'HAS 23000:2012 — Halal Assurance System (MUI)',
         'HAS 23000:2012 Halal Assurance System Requirements',
         'MUI (Indonesia)', '2012',
         'Hệ thống Đảm bảo Halal MUI (Indonesia). Bắt buộc cho sản phẩm xuất Indonesia.',
         'https://halalmui.org',
         true, 103)

        ON CONFLICT (code) DO NOTHING;
    """)


def downgrade() -> None:
    # Drop seeded standards first (FK from industry_standards if mapped)
    op.execute("""
        DELETE FROM industry_standards
        WHERE standard_type_id IN (
            SELECT id FROM standard_types
            WHERE code IN ('uae_s_2055_1_2015', 'gso_2055_2_2021',
                           'oic_smiic_1_2019', 'has_23000_2012')
        );
    """)
    op.execute("""
        DELETE FROM standard_types
        WHERE code IN ('uae_s_2055_1_2015', 'gso_2055_2_2021',
                       'oic_smiic_1_2019', 'has_23000_2012');
    """)

    # Drop 15 user columns
    op.execute("""
        ALTER TABLE users
            DROP COLUMN IF EXISTS founded_year,
            DROP COLUMN IF EXISTS halal_commitment_statement,
            DROP COLUMN IF EXISTS total_employees,
            DROP COLUMN IF EXISTS najis_handling_policy,
            DROP COLUMN IF EXISTS cross_contamination_controls,
            DROP COLUMN IF EXISTS product_categories,
            DROP COLUMN IF EXISTS primary_suppliers,
            DROP COLUMN IF EXISTS ingredient_origin_countries,
            DROP COLUMN IF EXISTS packaging_materials_brief,
            DROP COLUMN IF EXISTS ihc_chairman_name,
            DROP COLUMN IF EXISTS ihc_chairman_title,
            DROP COLUMN IF EXISTS ihc_inception_date,
            DROP COLUMN IF EXISTS ihc_members_brief,
            DROP COLUMN IF EXISTS ihc_meeting_frequency,
            DROP COLUMN IF EXISTS production_capacity_brief;
    """)
