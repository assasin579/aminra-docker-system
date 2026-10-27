"""Reference attachments between Dossiers and reusable document versions.

Revision ID: 055_dossier_document_attachments
Revises: 054_requirements_versions
"""
from alembic import op

revision = "055_dossier_document_attachments"
down_revision = "054_requirements_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE submissions ADD COLUMN dossier_id UUID REFERENCES dossiers(id) ON DELETE RESTRICT")
    op.execute("CREATE INDEX idx_submissions_dossier_round ON submissions(dossier_id, revision_round) WHERE dossier_id IS NOT NULL")
    op.execute("""
        CREATE TABLE dossier_document_attachments (
            dossier_id UUID NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
            requirements_version_id UUID NOT NULL,
            doc_type VARCHAR(100) NOT NULL,
            document_version_number INTEGER NOT NULL,
            document_file_path TEXT NOT NULL,
            document_file_size BIGINT NOT NULL,
            attached_by UUID REFERENCES users(id) ON DELETE SET NULL,
            idempotency_key UUID NOT NULL,
            request_sha256 CHAR(64) NOT NULL,
            attached_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (dossier_id, document_id),
            FOREIGN KEY (requirements_version_id, doc_type)
                REFERENCES standard_requirement_version_slots(requirements_version_id, doc_type)
                ON DELETE RESTRICT
        )
    """)
    op.execute("CREATE INDEX idx_dossier_document_attachments_document ON dossier_document_attachments(document_id)")
    op.execute("CREATE UNIQUE INDEX uq_dossier_attachment_idempotency ON dossier_document_attachments(dossier_id, idempotency_key)")
    op.execute("""
        CREATE FUNCTION validate_dossier_document_attachment() RETURNS trigger AS $$
        DECLARE
            dossier_tenant UUID;
            dossier_version UUID;
            dossier_binding TEXT;
            dossier_status TEXT;
            document_tenant UUID;
            document_type VARCHAR(100);
            document_version INTEGER;
            document_path TEXT;
            document_size BIGINT;
            requirements_state TEXT;
        BEGIN
            SELECT tenant_id, requirements_version_id, requirements_binding_status, status
              INTO dossier_tenant, dossier_version, dossier_binding, dossier_status
              FROM dossiers WHERE id = NEW.dossier_id FOR KEY SHARE;
            IF dossier_tenant IS NULL OR dossier_binding <> 'bound'
               OR dossier_version IS DISTINCT FROM NEW.requirements_version_id
               OR dossier_status = 'cancelled' THEN
                RAISE EXCEPTION 'Dossier requirements binding is unavailable';
            END IF;
            SELECT tenant_id, doc_type, version_number, file_path, file_size
              INTO document_tenant, document_type, document_version, document_path, document_size
              FROM documents WHERE id = NEW.document_id FOR KEY SHARE;
            IF document_tenant IS DISTINCT FROM dossier_tenant OR document_type IS DISTINCT FROM NEW.doc_type
               OR document_path IS NULL OR document_size IS NULL OR document_version IS NULL THEN
                RAISE EXCEPTION 'Document tenant, type, or immutable version metadata is unavailable';
            END IF;
            NEW.document_version_number := document_version;
            NEW.document_file_path := document_path;
            NEW.document_file_size := document_size;
            SELECT state INTO requirements_state FROM standard_requirement_versions
              WHERE id = NEW.requirements_version_id;
            IF requirements_state IS DISTINCT FROM 'published' THEN
                RAISE EXCEPTION 'Dossier requirements version is not published';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_validate_dossier_document_attachment
        BEFORE INSERT OR UPDATE ON dossier_document_attachments
        FOR EACH ROW EXECUTE FUNCTION validate_dossier_document_attachment()
    """)
    op.execute("""
        CREATE FUNCTION prevent_dossier_attachment_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Dossier attachment evidence is immutable';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_prevent_dossier_attachment_mutation
        BEFORE UPDATE ON dossier_document_attachments
        FOR EACH ROW EXECUTE FUNCTION prevent_dossier_attachment_mutation()
    """)
    op.execute("""
        CREATE FUNCTION prevent_attached_document_version_mutation() RETURNS trigger AS $$
        BEGIN
            IF (NEW.tenant_id, NEW.doc_type, NEW.file_path, NEW.file_size, NEW.version_number, NEW.version_parent_id)
               IS DISTINCT FROM
               (OLD.tenant_id, OLD.doc_type, OLD.file_path, OLD.file_size, OLD.version_number, OLD.version_parent_id)
               AND EXISTS (SELECT 1 FROM dossier_document_attachments WHERE document_id=OLD.id) THEN
                RAISE EXCEPTION 'Attached document version identity is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_prevent_attached_document_version_mutation
        BEFORE UPDATE ON documents
        FOR EACH ROW EXECUTE FUNCTION prevent_attached_document_version_mutation()
    """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM dossier_document_attachments)
               OR EXISTS (SELECT 1 FROM submissions WHERE dossier_id IS NOT NULL) THEN
                RAISE EXCEPTION 'Cannot downgrade after durable dossier attachment/submission evidence exists';
            END IF;
        END $$
    """)
    op.execute("DROP TRIGGER trg_prevent_attached_document_version_mutation ON documents")
    op.execute("DROP FUNCTION prevent_attached_document_version_mutation()")
    op.execute("DROP TRIGGER trg_prevent_dossier_attachment_mutation ON dossier_document_attachments")
    op.execute("DROP FUNCTION prevent_dossier_attachment_mutation()")
    op.execute("DROP TRIGGER trg_validate_dossier_document_attachment ON dossier_document_attachments")
    op.execute("DROP FUNCTION validate_dossier_document_attachment()")
    op.execute("DROP INDEX uq_dossier_attachment_idempotency")
    op.execute("DROP INDEX idx_dossier_document_attachments_document")
    op.execute("DROP TABLE dossier_document_attachments")
    op.execute("DROP INDEX idx_submissions_dossier_round")
    op.execute("ALTER TABLE submissions DROP COLUMN dossier_id")
