"""Backfill schema gaps surfaced by full-codebase audit

Code-vs-schema audit found 8 mismatches across 4 tables — every one is a
500 in production the moment that code path runs. Migration 027 closes
all of them in one atomic step:

NEW TABLE — member_invites
  Powers the /business/members/invite flow. Owner generates an invite
  token, recipient signs up with it. Without this table, every invite
  attempt 500s.

users — 3 new columns
  permissions             JSONB        — per-member RBAC overrides
  notify_eval_done        BOOLEAN      — email pref toggles (default true)
  notify_submission_reply BOOLEAN

suppliers — 2 new columns
  invite_token       VARCHAR(255) UNIQUE — supplier-portal external link
  invite_expires_at  TIMESTAMPTZ

supplier_certificates — 1 new column
  uploaded_by        VARCHAR(50) — 'supplier' or 'business' (provenance
                                    drives can_verify gating)

Revision ID: 027_audit_missing_schema
Revises: 026_batch_sealing_columns
Create Date: 2026-05-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "027_audit_missing_schema"
down_revision: Union[str, None] = "026_batch_sealing_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── member_invites table ─────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE member_invites (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            email           VARCHAR(255) NOT NULL,
            invite_token    VARCHAR(255) NOT NULL UNIQUE,
            role            VARCHAR(100),
            department      VARCHAR(255),
            expires_at      TIMESTAMPTZ NOT NULL,
            accepted_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_member_invites_token ON member_invites (invite_token);")
    op.execute("CREATE INDEX idx_member_invites_tenant ON member_invites (tenant_id);")

    # ── users columns ────────────────────────────────────────────────────────
    op.add_column("users", sa.Column(
        "permissions",
        sa.dialects.postgresql.JSONB(),
        nullable=True,
        server_default="{}",
    ))
    op.add_column("users", sa.Column(
        "notify_eval_done", sa.Boolean(),
        nullable=True, server_default=sa.text("true"),
    ))
    op.add_column("users", sa.Column(
        "notify_submission_reply", sa.Boolean(),
        nullable=True, server_default=sa.text("true"),
    ))

    # ── suppliers columns ────────────────────────────────────────────────────
    op.add_column("suppliers", sa.Column("invite_token", sa.String(length=255), nullable=True))
    op.add_column("suppliers", sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "CREATE UNIQUE INDEX uq_suppliers_invite_token "
        "ON suppliers (invite_token) WHERE invite_token IS NOT NULL;"
    )

    # ── supplier_certificates column ─────────────────────────────────────────
    op.add_column("supplier_certificates", sa.Column(
        "uploaded_by", sa.String(length=50), nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("supplier_certificates", "uploaded_by")
    op.execute("DROP INDEX IF EXISTS uq_suppliers_invite_token;")
    op.drop_column("suppliers", "invite_expires_at")
    op.drop_column("suppliers", "invite_token")
    op.drop_column("users", "notify_submission_reply")
    op.drop_column("users", "notify_eval_done")
    op.drop_column("users", "permissions")
    op.execute("DROP TABLE IF EXISTS member_invites;")
