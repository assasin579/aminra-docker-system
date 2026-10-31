"""Select a library current version without changing upload or approval history."""
from alembic import op

revision = "057_document_current_versions"
down_revision = "056_j1j2_lineage_merge"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE document_current_versions (
            tenant_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            root_document_id UUID NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
            current_document_id UUID NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
            selected_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            selected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, root_document_id),
            UNIQUE (tenant_id, current_document_id)
        )
    """)
    op.execute("""
        CREATE FUNCTION validate_document_current_version() RETURNS trigger AS $$
        DECLARE root_tenant UUID; current_tenant UUID; actor_tenant UUID;
                cursor_id UUID; parent_id UUID; seen UUID[] := ARRAY[]::UUID[]; depth integer := 0;
        BEGIN
            SELECT tenant_id INTO root_tenant FROM documents WHERE id=NEW.root_document_id;
            SELECT tenant_id INTO current_tenant FROM documents WHERE id=NEW.current_document_id;
            SELECT COALESCE(tenant_id,id) INTO actor_tenant FROM users WHERE id=NEW.selected_by;
            IF root_tenant IS DISTINCT FROM NEW.tenant_id
               OR current_tenant IS DISTINCT FROM NEW.tenant_id
               OR actor_tenant IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION 'Current version must stay in its business tenant' USING ERRCODE='23514';
            END IF;
            cursor_id := NEW.current_document_id;
            LOOP
                IF cursor_id = ANY(seen) OR depth > 10 THEN
                    RAISE EXCEPTION 'Invalid document version chain' USING ERRCODE='23514';
                END IF;
                seen := array_append(seen,cursor_id);
                SELECT version_parent_id INTO parent_id FROM documents
                  WHERE id=cursor_id AND tenant_id=NEW.tenant_id;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'Version ancestor outside tenant' USING ERRCODE='23514';
                END IF;
                IF parent_id IS NULL THEN
                    IF cursor_id IS DISTINCT FROM NEW.root_document_id THEN
                        RAISE EXCEPTION 'Current document must belong to its root chain' USING ERRCODE='23514';
                    END IF;
                    EXIT;
                END IF;
                cursor_id := parent_id;
                depth := depth+1;
            END LOOP;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """)
    op.execute("""CREATE TRIGGER document_current_version_tenant_check
        BEFORE INSERT OR UPDATE ON document_current_versions
        FOR EACH ROW EXECUTE FUNCTION validate_document_current_version()""")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='aminra_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON document_current_versions TO aminra_app;
        END IF;
    END $$""")


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM document_current_versions) THEN
            RAISE EXCEPTION 'Current-version selections exist; recover forward instead of dropping them';
        END IF;
    END $$""")
    op.execute("DROP TABLE document_current_versions")
    op.execute("DROP FUNCTION validate_document_current_version()")
