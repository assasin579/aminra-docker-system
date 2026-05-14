"""Phase 4c follow-up: idempotent admin@aminra.com bootstrap row.

After the Phase 4 nuclear cutover (TRUNCATE users CASCADE) + Keycloak
volume wipe, the seeded admin row disappeared. Three sites still expect
it to exist (U15 in brain):
  - `app.py::admin_delete_user` guards id 54182089-… from deletion
  - `industry_schema_router._require_admin` matches by email
  - `standard_type_router._require_admin` matches by email

This migration plants the row idempotently. Credentials live in Keycloak
(post-Phase-4 password_hash column is gone); this PG row is a stable FK
target for audit_logs.user_id + a sentinel for the legacy email-based
admin gates. `keycloak_sub` stays NULL and is JIT-linked on first
platform_admin login (see /auth/me flow in auth/router.py).

Revision ID: 037_seed_admin_bootstrap
Revises: 036_drop_password_hash
Create Date: 2026-05-14
"""

from alembic import op


revision = "037_seed_admin_bootstrap"
down_revision = "036_drop_password_hash"
branch_labels = None
depends_on = None


_ADMIN_ID = "54182089-3a6d-458a-994d-93ac4e0c504f"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO users (
            id, email, role, status, is_owner, tenant_id,
            company_name, company_code
        )
        VALUES (
            '{_ADMIN_ID}',
            'admin@aminra.com',
            'provider'::user_role,
            'active'::user_status,
            true,
            '{_ADMIN_ID}',
            'AMINRA Platform',
            'AMINRA-ADMIN'
        )
        ON CONFLICT (email) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM users WHERE id = '{_ADMIN_ID}'")
