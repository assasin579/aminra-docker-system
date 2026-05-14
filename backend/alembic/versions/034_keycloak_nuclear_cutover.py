"""Keycloak nuclear cutover: wipe legacy PG auth data + add keycloak_sub column.

ADR-005 Phase 4 cutover (2026-05-14):
- 0 real production users → all 270 PG users are test/QA artifacts.
- Nuclear strategy: wipe legacy auth, switch to Keycloak as sole auth provider.

Strategy:
- TRUNCATE all user-activity tables CASCADE in one shot.
  TRUNCATE doesn't fire row-level triggers, so audit_logs immutable guard
  is bypassed naturally — no need to disable it.
- Re-add audit_logs.user_id FK with ON DELETE SET NULL (was NO ACTION
  — wrong design: user delete should preserve log row).
- ADD users.keycloak_sub UUID UNIQUE + ALTER password_hash NULLABLE.

Backup: backups/pre-keycloak-nuclear-*.sql.

Post-migration TODO (Phase 4b):
- Backend register endpoints → call Keycloak admin REST.
- /auth/login decommission.
- FE redirect Keycloak SSO only.
- Realm registrationAllowed=true.

Revision ID: 034_keycloak_nuclear_cutover
Revises: 033_align_doc_types
Create Date: 2026-05-14
"""

from alembic import op


revision = "034_keycloak_nuclear_cutover"
down_revision = "033_align_doc_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Fix audit_logs FK design (was NO ACTION → ON DELETE SET NULL)
    # Must happen BEFORE TRUNCATE so it doesn't conflict.
    op.execute("ALTER TABLE audit_logs DROP CONSTRAINT IF EXISTS audit_logs_user_id_fkey")
    op.execute("""
        ALTER TABLE audit_logs
        ADD CONSTRAINT audit_logs_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    """)

    # 2. TRUNCATE all user-activity tables CASCADE.
    # TRUNCATE bypasses row-level BEFORE triggers (incl. immutable guard
    # on audit_logs). Order independent under CASCADE.
    op.execute("""
        TRUNCATE TABLE
            users,
            audit_logs,
            audit_ncr, audit_visit_items, audit_visits, audit_checklist_templates,
            submission_comments, submission_evaluations,
            submission_revision_requests, submissions,
            halal_certificates, cert_anchor_proofs,
            documents, dossiers, custom_placeholders,
            notifications, password_reset_tokens, push_subscriptions,
            member_invites, deletion_tokens,
            blockchain_anchors, batch_anchor_proofs,
            production_batches, batch_steps, batch_materials,
            supplier_certificates, suppliers,
            tenant_feature_overrides
        RESTART IDENTITY CASCADE
    """)

    # 3. Schema changes on users
    op.execute("ALTER TABLE users ADD COLUMN keycloak_sub UUID UNIQUE")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_keycloak_sub ON users(keycloak_sub)")
    op.execute("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL")
    op.execute("DROP INDEX IF EXISTS ix_users_keycloak_sub")
    op.execute("ALTER TABLE users DROP COLUMN keycloak_sub")
    # FK ON DELETE SET NULL change NOT reverted (intentional design fix).
    # Data wipe NOT reversible — restore via pg_restore from backup file.
