"""Add missing batch sealing + assignment + approval columns

The batch_router has a fully-built sealing + traceability workflow
(approve_batch, verify, QR, PDF export) that references columns the schema
never grew. Result: every assign-member / approve / seal call 500s with
`UndefinedColumnError`. This migration backfills the schema to match the
shipped code.

production_batches gets:
  integrity_hash  TEXT          — SHA-256 of sealed_data, post-seal proof
  sealed_data     JSONB         — frozen snapshot of batch + steps + materials
  assigned_to     UUID          — member responsible for next-step approval
  assigned_name   VARCHAR(255)  — denormalised member display name
  approved_by     VARCHAR(255)  — approver email (matches code's user.email)
  approved_at     TIMESTAMPTZ   — when seal happened

batch_steps gets:
  step_hash       TEXT          — per-step SHA-256, individually verifiable
  approved_by     VARCHAR(255)  — approver email
  approved_at     TIMESTAMPTZ   — when step was signed off

All columns nullable — sealing is opt-in per batch lifecycle.

Revision ID: 026_batch_sealing_columns
Revises: 025_unique_batch_code
Create Date: 2026-05-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "026_batch_sealing_columns"
down_revision: Union[str, None] = "025_unique_batch_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("production_batches", sa.Column("integrity_hash", sa.Text(), nullable=True))
    op.add_column("production_batches", sa.Column("sealed_data", sa.dialects.postgresql.JSONB(), nullable=True))
    op.add_column("production_batches", sa.Column("assigned_to", sa.dialects.postgresql.UUID(), nullable=True))
    op.add_column("production_batches", sa.Column("assigned_name", sa.String(length=255), nullable=True))
    op.add_column("production_batches", sa.Column("approved_by", sa.String(length=255), nullable=True))
    op.add_column("production_batches", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("batch_steps", sa.Column("step_hash", sa.Text(), nullable=True))
    op.add_column("batch_steps", sa.Column("approved_by", sa.String(length=255), nullable=True))
    op.add_column("batch_steps", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("batch_steps", "approved_at")
    op.drop_column("batch_steps", "approved_by")
    op.drop_column("batch_steps", "step_hash")

    op.drop_column("production_batches", "approved_at")
    op.drop_column("production_batches", "approved_by")
    op.drop_column("production_batches", "assigned_name")
    op.drop_column("production_batches", "assigned_to")
    op.drop_column("production_batches", "sealed_data")
    op.drop_column("production_batches", "integrity_hash")
