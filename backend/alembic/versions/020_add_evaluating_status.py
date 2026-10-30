"""Add 'evaluating' to document_status enum

The evaluate endpoint sets documents.status = 'evaluating' while AI
processing runs in background, then resets to 'uploaded' on completion.
This value was missing from the enum, causing a 500 on every evaluate call.

Revision ID: 020_add_evaluating_status
Revises: 019_add_manager_name
Create Date: 2026-05-03
"""
from typing import Sequence, Union
from alembic import op

revision: str = "020_add_evaluating_status"
down_revision: Union[str, None] = "019_add_manager_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE cannot run inside a transaction block in PG < 12,
    # but PG 15 (in use) supports it. IF NOT EXISTS makes it idempotent.
    op.execute("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'evaluating';")


def downgrade() -> None:
    # PostgreSQL does not support DROP VALUE from an enum.
    # Safe downgrade: migrate any 'evaluating' rows back to 'uploaded' first,
    # then recreate the enum without the value.
    op.execute("""
        UPDATE documents SET status = 'uploaded' WHERE status = 'evaluating';
    """)
    op.execute("""
        ALTER TABLE documents ALTER COLUMN status TYPE TEXT;
    """)
    op.execute("DROP TYPE document_status;")
    op.execute("""
        CREATE TYPE document_status AS ENUM ('uploaded', 'reviewing', 'approved', 'rejected');
    """)
    op.execute("""
        ALTER TABLE documents ALTER COLUMN status TYPE document_status
            USING status::document_status;
    """)
    op.execute("""
        ALTER TABLE documents ALTER COLUMN status SET DEFAULT 'uploaded';
    """)
