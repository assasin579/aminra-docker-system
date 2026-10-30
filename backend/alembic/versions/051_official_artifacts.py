"""official artifact separation

Revision ID: 051_official_artifacts
Revises: 050_complaints_appeals
Create Date: 2026-09-26
"""

from alembic import op

revision = "051_official_artifacts"
down_revision = "050_complaints_appeals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS official_artifacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            source_document_id UUID NOT NULL REFERENCES documents(id),
            artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('approved_document')),
            original_filename TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            file_size BIGINT NOT NULL CHECK (file_size >= 0),
            mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
            sha256 TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            approved_by_user_id UUID REFERENCES users(id),
            approved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            effective_date DATE,
            next_review_date DATE,
            retention_expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_official_artifacts_source_kind ON official_artifacts(source_document_id, artifact_kind)",
        "CREATE INDEX IF NOT EXISTS idx_official_artifacts_tenant_created ON official_artifacts(tenant_id, created_at DESC)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_official_artifacts_storage_path ON official_artifacts(storage_path)",
        """
        CREATE OR REPLACE FUNCTION block_document_delete_with_official_artifacts()
        RETURNS trigger AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM official_artifacts WHERE source_document_id = OLD.id) THEN
                RAISE EXCEPTION 'Cannot delete document with official immutable artifact reference'
                    USING ERRCODE = '23503',
                          HINT = 'Official artifacts are immutable records; supersede instead of deleting the source document.';
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql
        """,
        "DROP TRIGGER IF EXISTS documents_block_delete_with_official_artifacts ON documents",
        """
        CREATE TRIGGER documents_block_delete_with_official_artifacts
          BEFORE DELETE ON documents
          FOR EACH ROW EXECUTE FUNCTION block_document_delete_with_official_artifacts()
        """,
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    statements = [
        "DROP TRIGGER IF EXISTS documents_block_delete_with_official_artifacts ON documents",
        "DROP FUNCTION IF EXISTS block_document_delete_with_official_artifacts()",
        "DROP INDEX IF EXISTS idx_official_artifacts_storage_path",
        "DROP INDEX IF EXISTS idx_official_artifacts_tenant_created",
        "DROP INDEX IF EXISTS idx_official_artifacts_source_kind",
        "DROP TABLE IF EXISTS official_artifacts",
    ]
    for statement in statements:
        op.execute(statement)
