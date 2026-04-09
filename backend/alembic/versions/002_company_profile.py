"""add company profile fields to users

Revision ID: 002_company_profile
Revises: 001_baseline
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002_company_profile"
down_revision: Union[str, None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS address TEXT;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50);")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS representative_name VARCHAR(255);")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS representative_name;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS phone;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS address;")
