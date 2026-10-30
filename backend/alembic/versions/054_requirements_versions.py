"""Add immutable, publishable requirements versions for dossier and round binding.

Revision ID: 054_requirements_versions
Revises: 051_official_artifacts

This is intentionally a branch from the last committed migration baseline.
The isolated checkout contains separate uncommitted 052/053 audit WIP; do not
include or rewrite those paths here. A merge revision is required when branches
are integrated into a single release migration head.
"""
from alembic import op

revision = "054_requirements_versions"
down_revision = "051_official_artifacts"
branch_labels = ("requirements_versions",)
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE standard_requirement_versions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            standard_type_id UUID NOT NULL REFERENCES standard_types(id) ON DELETE RESTRICT,
            version_number INTEGER NOT NULL CHECK (version_number > 0),
            state TEXT NOT NULL CHECK (state IN ('draft', 'published')),
            content_sha256 CHAR(64) NOT NULL,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            published_by UUID REFERENCES users(id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            published_at TIMESTAMPTZ,
            UNIQUE (standard_type_id, version_number),
            UNIQUE (id, standard_type_id),
            CHECK ((state = 'published' AND published_by IS NOT NULL AND published_at IS NOT NULL) OR (state = 'draft' AND published_by IS NULL AND published_at IS NULL))
        )
    """)
    op.execute("""
        CREATE TABLE standard_requirement_version_slots (
            requirements_version_id UUID NOT NULL,
            standard_type_id UUID NOT NULL,
            doc_type VARCHAR(100) NOT NULL,
            required BOOLEAN NOT NULL,
            display_order INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (requirements_version_id, doc_type),
            FOREIGN KEY (requirements_version_id, standard_type_id)
                REFERENCES standard_requirement_versions(id, standard_type_id) ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE TABLE standard_requirement_current_versions (
            standard_type_id UUID PRIMARY KEY REFERENCES standard_types(id) ON DELETE RESTRICT,
            requirements_version_id UUID NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            FOREIGN KEY (requirements_version_id, standard_type_id)
                REFERENCES standard_requirement_versions(id, standard_type_id) ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE FUNCTION prevent_published_requirement_slot_mutation() RETURNS trigger AS $$
        BEGIN
            IF TG_OP <> 'INSERT' AND EXISTS (
                SELECT 1 FROM standard_requirement_versions WHERE id=OLD.requirements_version_id AND state='published'
            ) THEN RAISE EXCEPTION 'Published requirements version slots are immutable'; END IF;
            IF TG_OP <> 'DELETE' AND EXISTS (
                SELECT 1 FROM standard_requirement_versions WHERE id=NEW.requirements_version_id AND state='published'
            ) THEN RAISE EXCEPTION 'Published requirements version slots are immutable'; END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_immutable_published_requirement_slots
        BEFORE INSERT OR UPDATE OR DELETE ON standard_requirement_version_slots
        FOR EACH ROW EXECUTE FUNCTION prevent_published_requirement_slot_mutation()
    """)
    op.execute("""
        CREATE FUNCTION protect_requirement_versions() RETURNS trigger AS $$
        BEGIN
            IF OLD.state = 'published' THEN
                RAISE EXCEPTION 'Published requirements versions are immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            IF NEW.id <> OLD.id OR NEW.standard_type_id <> OLD.standard_type_id
               OR NEW.version_number <> OLD.version_number OR NEW.content_sha256 <> OLD.content_sha256
               OR NEW.created_by IS DISTINCT FROM OLD.created_by OR NEW.created_at <> OLD.created_at
               OR NEW.state <> 'published' OR NEW.published_by IS NULL OR NEW.published_at IS NULL THEN
                RAISE EXCEPTION 'Draft version may only transition once to published';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_protect_requirement_versions
        BEFORE UPDATE OR DELETE ON standard_requirement_versions
        FOR EACH ROW EXECUTE FUNCTION protect_requirement_versions()
    """)
    op.execute("""
        CREATE FUNCTION require_published_current_requirements() RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM standard_requirement_versions
                WHERE id=NEW.requirements_version_id AND standard_type_id=NEW.standard_type_id AND state='published'
            ) THEN RAISE EXCEPTION 'Current requirements pointer must reference a published version'; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_current_requirements_published_only
        BEFORE INSERT OR UPDATE ON standard_requirement_current_versions
        FOR EACH ROW EXECUTE FUNCTION require_published_current_requirements()
    """)
    op.execute("ALTER TABLE dossiers ADD COLUMN requirements_version_id UUID")
    op.execute("ALTER TABLE dossiers ADD COLUMN requirements_binding_status TEXT NOT NULL DEFAULT 'unknown' CHECK (requirements_binding_status IN ('bound', 'unconfigured', 'unknown'))")
    op.execute("ALTER TABLE dossiers ADD CONSTRAINT fk_dossiers_requirements_version FOREIGN KEY (requirements_version_id, standard_type_id) REFERENCES standard_requirement_versions(id, standard_type_id) ON DELETE RESTRICT")
    op.execute("ALTER TABLE dossiers ADD CONSTRAINT ck_dossiers_requirements_binding CHECK ((requirements_binding_status = 'bound' AND requirements_version_id IS NOT NULL AND standard_type_id IS NOT NULL) OR (requirements_binding_status <> 'bound' AND requirements_version_id IS NULL))")
    op.execute("ALTER TABLE submissions ADD COLUMN requirements_version_id UUID")
    op.execute("ALTER TABLE submissions ADD COLUMN requirements_binding_status TEXT NOT NULL DEFAULT 'unknown' CHECK (requirements_binding_status IN ('bound', 'unconfigured', 'unknown'))")
    op.execute("ALTER TABLE submissions ADD CONSTRAINT fk_submissions_requirements_version FOREIGN KEY (requirements_version_id) REFERENCES standard_requirement_versions(id) ON DELETE RESTRICT")
    op.execute("ALTER TABLE submissions ADD CONSTRAINT ck_submissions_requirements_binding CHECK ((requirements_binding_status = 'bound' AND requirements_version_id IS NOT NULL) OR (requirements_binding_status IN ('unknown', 'unconfigured') AND requirements_version_id IS NULL))")
    op.execute("ALTER TABLE certification_decisions ADD COLUMN requirements_version_id UUID REFERENCES standard_requirement_versions(id) ON DELETE RESTRICT")
    op.execute("ALTER TABLE certification_decisions ADD COLUMN submitted_round INTEGER")
    op.execute("ALTER TABLE certification_decisions ADD CONSTRAINT ck_decision_requirement_round CHECK (submitted_round IS NULL OR submitted_round > 0)")
    op.execute("ALTER TABLE submission_revision_requests ADD COLUMN requirements_version_id UUID REFERENCES standard_requirement_versions(id) ON DELETE RESTRICT")
    op.execute("ALTER TABLE submission_revision_requests ADD COLUMN submitted_document_ids UUID[] NOT NULL DEFAULT '{}'::uuid[]")
    op.execute("ALTER TABLE submission_revision_requests ADD COLUMN submitted_round INTEGER")
    op.execute("ALTER TABLE submission_revision_requests ADD CONSTRAINT ck_revision_requirement_round CHECK (submitted_round IS NULL OR submitted_round > 0)")
    op.execute("""
        CREATE FUNCTION prevent_submission_requirements_rebinding() RETURNS trigger AS $$
        BEGIN
            IF OLD.requirements_version_id IS DISTINCT FROM NEW.requirements_version_id
               OR OLD.requirements_binding_status IS DISTINCT FROM NEW.requirements_binding_status THEN
                RAISE EXCEPTION 'Requirements binding is immutable; use explicit audited migration';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_dossier_requirements_immutable BEFORE UPDATE OF requirements_version_id, requirements_binding_status ON dossiers FOR EACH ROW EXECUTE FUNCTION prevent_submission_requirements_rebinding()")
    op.execute("CREATE TRIGGER trg_submission_requirements_immutable BEFORE UPDATE OF requirements_version_id, requirements_binding_status ON submissions FOR EACH ROW EXECUTE FUNCTION prevent_submission_requirements_rebinding()")
    op.execute("""
        CREATE FUNCTION protect_revision_context() RETURNS trigger AS $$
        BEGIN
            IF OLD.requirements_version_id IS DISTINCT FROM NEW.requirements_version_id
               OR OLD.submitted_document_ids IS DISTINCT FROM NEW.submitted_document_ids
               OR OLD.submitted_round IS DISTINCT FROM NEW.submitted_round THEN
                RAISE EXCEPTION 'Submitted round evidence is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_revision_context_immutable BEFORE UPDATE ON submission_revision_requests FOR EACH ROW EXECUTE FUNCTION protect_revision_context()")


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM standard_requirement_versions WHERE state = 'published')
               OR EXISTS (SELECT 1 FROM dossiers WHERE requirements_version_id IS NOT NULL)
               OR EXISTS (SELECT 1 FROM submissions WHERE requirements_version_id IS NOT NULL)
               OR EXISTS (SELECT 1 FROM certification_decisions WHERE requirements_version_id IS NOT NULL OR submitted_round IS NOT NULL)
               OR EXISTS (SELECT 1 FROM submission_revision_requests WHERE requirements_version_id IS NOT NULL OR submitted_round IS NOT NULL) THEN
                RAISE EXCEPTION 'Cannot downgrade: published requirements or submitted-round snapshots are durable evidence';
            END IF;
        END $$
    """)
    op.execute("DROP TRIGGER trg_revision_context_immutable ON submission_revision_requests")
    op.execute("DROP FUNCTION protect_revision_context()")
    op.execute("ALTER TABLE submission_revision_requests DROP CONSTRAINT ck_revision_requirement_round")
    op.execute("ALTER TABLE submission_revision_requests DROP COLUMN submitted_round")
    op.execute("ALTER TABLE submission_revision_requests DROP COLUMN submitted_document_ids")
    op.execute("ALTER TABLE submission_revision_requests DROP COLUMN requirements_version_id")
    op.execute("ALTER TABLE certification_decisions DROP CONSTRAINT ck_decision_requirement_round")
    op.execute("ALTER TABLE certification_decisions DROP COLUMN submitted_round")
    op.execute("ALTER TABLE certification_decisions DROP COLUMN requirements_version_id")
    op.execute("DROP TRIGGER trg_dossier_requirements_immutable ON dossiers")
    op.execute("DROP TRIGGER trg_submission_requirements_immutable ON submissions")
    op.execute("DROP FUNCTION prevent_submission_requirements_rebinding()")
    op.execute("ALTER TABLE submissions DROP CONSTRAINT ck_submissions_requirements_binding")
    op.execute("ALTER TABLE submissions DROP CONSTRAINT fk_submissions_requirements_version")
    op.execute("ALTER TABLE submissions DROP COLUMN requirements_binding_status")
    op.execute("ALTER TABLE submissions DROP COLUMN requirements_version_id")
    op.execute("ALTER TABLE dossiers DROP CONSTRAINT ck_dossiers_requirements_binding")
    op.execute("ALTER TABLE dossiers DROP CONSTRAINT fk_dossiers_requirements_version")
    op.execute("ALTER TABLE dossiers DROP COLUMN requirements_binding_status")
    op.execute("ALTER TABLE dossiers DROP COLUMN requirements_version_id")
    op.execute("DROP TRIGGER trg_current_requirements_published_only ON standard_requirement_current_versions")
    op.execute("DROP FUNCTION require_published_current_requirements()")
    op.execute("DROP TRIGGER trg_protect_requirement_versions ON standard_requirement_versions")
    op.execute("DROP FUNCTION protect_requirement_versions()")
    op.execute("DROP TRIGGER trg_immutable_published_requirement_slots ON standard_requirement_version_slots")
    op.execute("DROP FUNCTION prevent_published_requirement_slot_mutation()")
    op.execute("DROP TABLE standard_requirement_current_versions")
    op.execute("DROP TABLE standard_requirement_version_slots")
    op.execute("DROP TABLE standard_requirement_versions")
