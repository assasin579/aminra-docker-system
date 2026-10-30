"""Add tax_code column to suppliers

Backend code (router INSERT/UPDATE, Pydantic SupplierCreate/Update/Out, listing
projection) all reference suppliers.tax_code, but the DB column was never
created. Result: every POST /suppliers fails with
`UndefinedColumnError: column "tax_code" of relation "suppliers" does not exist`.

VN tax code (mã số thuế) is 10 digits for individuals/branches and 13 for
companies (10 + "-" + 3-digit branch suffix). VARCHAR(20) is comfortable.

Revision ID: 024_add_supplier_tax_code
Revises: 023_add_business_response
Create Date: 2026-05-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "024_add_supplier_tax_code"
down_revision: Union[str, None] = "023_add_business_response"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "suppliers",
        sa.Column("tax_code", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("suppliers", "tax_code")
