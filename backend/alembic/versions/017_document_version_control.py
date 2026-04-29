"""document version control hardening — Tier-1 #24 (Phase 1)

Adds 10 columns to documents (all additive, nullable defaults), 2 triggers,
5 partial indexes, and backfills existing rows per spec §4. Reversible.

Spec:        docs/features/document-version-control/spec.md
Threat:      docs/features/document-version-control/threat-model.md
Schema doc:  docs/features/document-version-control/schema.md
Feature flag: document_versioning_v1 (seeded disabled in migration 016)

Revision ID: 017_document_version_control
Revises: 016_feature_flags
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "017_document_version_control"
down_revision: Union[str, None] = "016_feature_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Add columns (all additive, nullable defaults) ───────────────
    op.execute("""
        ALTER TABLE documents
          ADD COLUMN version_number       INT  NOT NULL DEFAULT 1,
          ADD COLUMN version_parent_id    UUID REFERENCES documents(id) ON DELETE SET NULL,
          ADD COLUMN approver_id          UUID REFERENCES users(id)     ON DELETE SET NULL,
          ADD COLUMN approved_at          TIMESTAMPTZ,
          ADD COLUMN effective_date       DATE,
          ADD COLUMN next_review_date     DATE,
          ADD COLUMN retention_period_days INT NOT NULL DEFAULT 1825
                     CHECK (retention_period_days >= 1825),
          ADD COLUMN retention_expires_at TIMESTAMPTZ,
          ADD COLUMN superseded_by_id     UUID REFERENCES documents(id) ON DELETE SET NULL,
          ADD COLUMN approval_status      VARCHAR(20) NOT NULL DEFAULT 'draft'
                     CHECK (approval_status IN ('draft','pending_approval','approved','obsolete'));
    """)

    # ── 2. Backfill: map legacy `status` → new `approval_status` ───────
    # Rule 1: 'approved' rows → carry over reviewer + timestamps
    op.execute("""
        UPDATE documents
           SET approval_status = 'approved',
               approver_id     = reviewed_by,
               approved_at     = reviewed_at,
               version_number  = 1
         WHERE status = 'approved';
    """)
    # Rule 2 + 3: 'uploaded'/'reviewing'/'rejected' → draft
    op.execute("""
        UPDATE documents
           SET approval_status = 'draft',
               version_number  = 1
         WHERE status IN ('uploaded', 'reviewing', 'rejected');
    """)

    # ── 3. Tenant-integrity trigger (R2 critical mitigation) ───────────
    op.execute("""
        CREATE OR REPLACE FUNCTION enforce_documents_chain_tenant()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.version_parent_id IS NOT NULL THEN
            IF NOT EXISTS (
              SELECT 1 FROM documents
              WHERE id = NEW.version_parent_id AND tenant_id = NEW.tenant_id
            ) THEN
              RAISE EXCEPTION
                'version_parent_id (%) must reference document in same tenant (%)',
                NEW.version_parent_id, NEW.tenant_id
                USING ERRCODE = '23514';
            END IF;
          END IF;

          IF NEW.superseded_by_id IS NOT NULL THEN
            IF NOT EXISTS (
              SELECT 1 FROM documents
              WHERE id = NEW.superseded_by_id AND tenant_id = NEW.tenant_id
            ) THEN
              RAISE EXCEPTION
                'superseded_by_id (%) must reference document in same tenant (%)',
                NEW.superseded_by_id, NEW.tenant_id
                USING ERRCODE = '23514';
            END IF;
          END IF;

          IF NEW.approval_status = 'approved' AND NEW.approved_at IS NOT NULL
             AND (TG_OP = 'INSERT' OR OLD.approval_status IS DISTINCT FROM 'approved') THEN
            NEW.retention_expires_at := COALESCE(NEW.effective_date::TIMESTAMPTZ, NEW.approved_at)
                                      + (NEW.retention_period_days || ' days')::INTERVAL;
          END IF;

          IF NEW.superseded_by_id IS NOT NULL
             AND (TG_OP = 'INSERT' OR OLD.superseded_by_id IS NULL) THEN
            NEW.approval_status := 'obsolete';
          END IF;

          RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER documents_chain_tenant_check
          BEFORE INSERT OR UPDATE ON documents
          FOR EACH ROW EXECUTE FUNCTION enforce_documents_chain_tenant();
    """)

    # ── 4. Delete-block trigger (Stage 2 Q1 decision) ──────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION block_delete_with_children()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        DECLARE
          child_count INT;
        BEGIN
          SELECT COUNT(*) INTO child_count
            FROM documents WHERE version_parent_id = OLD.id;
          IF child_count > 0 THEN
            RAISE EXCEPTION
              'Cannot delete document % — has % child version(s). Use supersede or delete children first',
              OLD.id, child_count
              USING ERRCODE = '23503',
                    HINT    = 'POST /api/documents/{id}/supersede';
          END IF;
          RETURN OLD;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER documents_block_delete_with_children
          BEFORE DELETE ON documents
          FOR EACH ROW EXECUTE FUNCTION block_delete_with_children();
    """)

    # ── 5. Indexes (5 partial — bounded size on legacy NULL-heavy table) ─
    op.execute("CREATE INDEX idx_documents_tenant_approval ON documents(tenant_id, approval_status);")
    op.execute("""
        CREATE INDEX idx_documents_tenant_next_review
          ON documents(tenant_id, next_review_date)
          WHERE next_review_date IS NOT NULL;
    """)
    op.execute("""
        CREATE INDEX idx_documents_version_parent
          ON documents(version_parent_id)
          WHERE version_parent_id IS NOT NULL;
    """)
    op.execute("""
        CREATE INDEX idx_documents_superseded_by
          ON documents(superseded_by_id)
          WHERE superseded_by_id IS NOT NULL;
    """)
    op.execute("""
        CREATE INDEX idx_documents_tenant_retention
          ON documents(tenant_id, retention_expires_at)
          WHERE retention_expires_at IS NOT NULL;
    """)


def downgrade() -> None:
    """Reverse Stage 3 schema changes. Destructive — drops approval data.
    Only run with explicit operator approval + recent backup.
    """
    op.execute("DROP TRIGGER IF EXISTS documents_block_delete_with_children ON documents;")
    op.execute("DROP TRIGGER IF EXISTS documents_chain_tenant_check ON documents;")
    op.execute("DROP FUNCTION IF EXISTS block_delete_with_children();")
    op.execute("DROP FUNCTION IF EXISTS enforce_documents_chain_tenant();")

    op.execute("DROP INDEX IF EXISTS idx_documents_tenant_retention;")
    op.execute("DROP INDEX IF EXISTS idx_documents_superseded_by;")
    op.execute("DROP INDEX IF EXISTS idx_documents_version_parent;")
    op.execute("DROP INDEX IF EXISTS idx_documents_tenant_next_review;")
    op.execute("DROP INDEX IF EXISTS idx_documents_tenant_approval;")

    op.execute("""
        ALTER TABLE documents
          DROP COLUMN IF EXISTS approval_status,
          DROP COLUMN IF EXISTS superseded_by_id,
          DROP COLUMN IF EXISTS retention_expires_at,
          DROP COLUMN IF EXISTS retention_period_days,
          DROP COLUMN IF EXISTS next_review_date,
          DROP COLUMN IF EXISTS effective_date,
          DROP COLUMN IF EXISTS approved_at,
          DROP COLUMN IF EXISTS approver_id,
          DROP COLUMN IF EXISTS version_parent_id,
          DROP COLUMN IF EXISTS version_number;
    """)
