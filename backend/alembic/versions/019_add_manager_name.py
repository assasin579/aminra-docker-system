"""add manager_name column to users

Revision ID: 019_add_manager_name
Revises: 018_hardening_uat_gaps
Create Date: 2026-05-03

Backend code đã reference users.manager_name (auth/router.py company-profile endpoints,
template rendering), nhưng cột này chưa từng được migrate. Bug surface: GET/PUT
/auth/company-profile trả 500 UndefinedColumnError, form Thông tin doanh nghiệp
không lưu được.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "019_add_manager_name"
down_revision: Union[str, None] = "018_hardening_uat_gaps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS manager_name VARCHAR(255);")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS manager_name;")
