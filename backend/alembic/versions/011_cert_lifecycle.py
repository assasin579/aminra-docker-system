"""cert lifecycle — revocation reason + expiry alert tracking

Adds:
- halal_certificates.revocation_reason / revoked_at / revoked_by — capture WHO
  revoked, WHEN, and WHY for legal compliance + audit trail
- halal_certificates.expiry_alerts_sent — JSONB tracking which alerts already
  fired (90/60/30/expired) to avoid duplicate emails

Revision ID: 011_cert_lifecycle
Revises: 010_submission_revisions
Create Date: 2026-04-25
"""
from typing import Sequence, Union
from alembic import op

revision: str = "011_cert_lifecycle"
down_revision: Union[str, None] = "010_submission_revisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE halal_certificates
            ADD COLUMN IF NOT EXISTS revocation_reason TEXT,
            ADD COLUMN IF NOT EXISTS revoked_at        TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS revoked_by        UUID REFERENCES users(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS expiry_alerts_sent JSONB NOT NULL DEFAULT '[]'::jsonb;
    """)

    # Index for fast scheduling: "find certs expiring in next N days that haven't
    # had alert fired yet"
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_certs_expiry_active
            ON halal_certificates(expiry_date)
            WHERE status = 'active';
    """)

    # Constraint: revoked_at REQUIRES revocation_reason (cannot revoke without reason)
    op.execute("""
        ALTER TABLE halal_certificates
            DROP CONSTRAINT IF EXISTS chk_cert_revocation_has_reason;
    """)
    op.execute("""
        ALTER TABLE halal_certificates
            ADD CONSTRAINT chk_cert_revocation_has_reason
            CHECK (revoked_at IS NULL OR (revocation_reason IS NOT NULL AND revoked_by IS NOT NULL));
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE halal_certificates DROP CONSTRAINT IF EXISTS chk_cert_revocation_has_reason;")
    op.execute("DROP INDEX IF EXISTS idx_certs_expiry_active;")
    op.execute("""
        ALTER TABLE halal_certificates
            DROP COLUMN IF EXISTS expiry_alerts_sent,
            DROP COLUMN IF EXISTS revoked_by,
            DROP COLUMN IF EXISTS revoked_at,
            DROP COLUMN IF EXISTS revocation_reason;
    """)
