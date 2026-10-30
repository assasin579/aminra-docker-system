"""Add business_response column to submission_revision_requests

When business resubmits with a `business_notes` payload (their reply to the
auditor's revision request), the message must be visible to the provider in
the revision history. Previously notes were written to `submissions.notes`
which is overwritten every round, so providers could never see what the
business said per round.

Revision ID: 023_add_business_response
Revises: 022_pdf_html_renderer_flags
Create Date: 2026-05-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "023_add_business_response"
down_revision: Union[str, None] = "022_pdf_html_renderer_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "submission_revision_requests",
        sa.Column("business_response", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("submission_revision_requests", "business_response")
