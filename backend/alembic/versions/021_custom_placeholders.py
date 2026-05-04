"""Create custom_placeholders table with system seed data

The admin placeholder management system (/admin/placeholders) and public
endpoint (/placeholders) both query this table. It was never migrated,
causing UndefinedTableError on every request.

Revision ID: 021_custom_placeholders
Revises: 020_add_evaluating_status
Create Date: 2026-05-03
"""
from typing import Sequence, Union
from alembic import op

revision: str = "021_custom_placeholders"
down_revision: Union[str, None] = "020_add_evaluating_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS custom_placeholders (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key          VARCHAR(100) NOT NULL UNIQUE,
            label        VARCHAR(200) NOT NULL,
            description  TEXT,
            default_value TEXT,
            source       VARCHAR(200),
            is_system    BOOLEAN NOT NULL DEFAULT false,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_custom_placeholders_key
            ON custom_placeholders (key);
    """)

    # Seed system placeholders — used in document templates across the platform.
    # is_system=true: cannot be deleted via API, only updated.
    op.execute("""
        INSERT INTO custom_placeholders
            (key, label, description, default_value, source, is_system)
        VALUES
            ('company_name',        'Tên doanh nghiệp',         'Tên đầy đủ của doanh nghiệp',                     'Công ty TNHH Ví dụ',       'profile', true),
            ('company_address',     'Địa chỉ doanh nghiệp',     'Địa chỉ trụ sở chính',                            '123 Đường ABC, TP.HCM',    'profile', true),
            ('company_tax_code',    'Mã số thuế',                'Mã số thuế doanh nghiệp (10 chữ số)',              '0123456789',               'profile', true),
            ('contact_person',      'Người liên hệ',             'Họ tên người đại diện / liên hệ',                  'Nguyễn Văn A',             'profile', true),
            ('contact_email',       'Email liên hệ',             'Địa chỉ email liên hệ chính',                      'contact@example.com',      'profile', true),
            ('contact_phone',       'Số điện thoại',             'Số điện thoại liên hệ',                            '0901 234 567',             'profile', true),
            ('certification_body',  'Tổ chức chứng nhận',        'Tên tổ chức cấp chứng nhận Halal',                 'HALCERT Vietnam',          'system',  true),
            ('certification_date',  'Ngày chứng nhận',           'Ngày cấp chứng nhận (dd/mm/yyyy)',                 '01/01/2026',               'system',  true),
            ('certification_number','Số chứng nhận',             'Mã số chứng nhận Halal',                           'HALAL-2026-XXXXX',         'system',  true),
            ('expiry_date',         'Ngày hết hạn',              'Ngày hết hạn chứng nhận (dd/mm/yyyy)',             '01/01/2027',               'system',  true),
            ('product_name',        'Tên sản phẩm',              'Tên sản phẩm hoặc nhóm sản phẩm được chứng nhận', 'Sản phẩm XYZ',             'manual',  true),
            ('production_site',     'Địa điểm sản xuất',         'Địa chỉ nhà máy / cơ sở sản xuất',                '456 Khu CN ABC, Bình Dương','profile', true),
            ('document_date',       'Ngày lập tài liệu',         'Ngày soạn thảo tài liệu (dd/mm/yyyy)',             '01/05/2026',               'manual',  true),
            ('version_number',      'Số phiên bản',              'Phiên bản tài liệu (vd: v1.0)',                    'v1.0',                     'manual',  true),
            ('ihc_chairperson',     'Chủ tịch IHC',              'Họ tên chủ tịch Ủy ban Halal nội bộ',              'Nguyễn Văn B',             'profile', true)
        ON CONFLICT (key) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS custom_placeholders;")
