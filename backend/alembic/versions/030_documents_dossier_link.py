"""Link documents to dossiers (FK).

documents — 1 new column
  dossier_id  UUID nullable  FK → dossiers(id) ON DELETE SET NULL

Pattern:
  - Existing documents (pre-dossier) → dossier_id stays NULL
  - New documents created via dossier flow → set dossier_id explicitly
  - SET NULL on dossier delete (soft cancel): preserve document trace

Indexes:
  - dossier_id alone for "list docs in dossier" query

Revision ID: 030_documents_dossier_link
Revises: 029_standard_types_split
Create Date: 2026-05-10
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "030_documents_dossier_link"
down_revision: Union[str, None] = "029_standard_types_split"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE documents
        ADD COLUMN dossier_id UUID REFERENCES dossiers(id) ON DELETE SET NULL;
        CREATE INDEX idx_documents_dossier ON documents(dossier_id) WHERE dossier_id IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_documents_dossier;")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS dossier_id;")
