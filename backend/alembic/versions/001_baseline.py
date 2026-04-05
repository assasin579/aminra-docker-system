"""baseline schema from init.sql

Revision ID: 001_baseline
Revises:
Create Date: 2026-04-05
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic
revision: str = "001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Extensions ---
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    # --- Enum types ---
    op.execute("CREATE TYPE user_role   AS ENUM ('business', 'provider');")
    op.execute("CREATE TYPE user_status AS ENUM ('pending', 'active', 'suspended');")
    op.execute(
        "CREATE TYPE document_status AS ENUM ('uploaded', 'reviewing', 'approved', 'rejected');"
    )

    # --- Function (must be created before triggers that reference it) ---
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ LANGUAGE plpgsql;
    """)

    # --- Tables ---
    op.execute("""
        CREATE TABLE users (
            id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            email            VARCHAR(255) UNIQUE NOT NULL,
            password_hash    VARCHAR(255) NOT NULL,
            role             user_role NOT NULL,
            company_name     VARCHAR(255) NOT NULL,
            company_code     VARCHAR(100),
            status           user_status DEFAULT 'pending',
            tenant_id        UUID,
            is_owner         BOOLEAN DEFAULT true,
            invited_by       UUID REFERENCES users(id) ON DELETE SET NULL,
            ihc_role         VARCHAR(100),
            department       VARCHAR(255),
            approved_by      UUID REFERENCES users(id),
            approved_at      TIMESTAMP WITH TIME ZONE,
            rejection_reason TEXT,
            created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE TABLE documents (
            id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            filename          VARCHAR(255) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            file_path         TEXT,
            file_size         BIGINT,
            mime_type         VARCHAR(100),
            user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
            tenant_id         UUID,
            doc_type          VARCHAR(100),
            status            document_status DEFAULT 'uploaded',
            compliance_score  INTEGER CHECK (compliance_score >= 0 AND compliance_score <= 100),
            evaluation_result JSONB,
            uploaded_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            reviewed_by       UUID REFERENCES users(id),
            reviewed_at       TIMESTAMP WITH TIME ZONE,
            review_notes      TEXT
        );
    """)

    op.execute("""
        CREATE TABLE password_reset_tokens (
            id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
            token      VARCHAR(255) UNIQUE NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            used       BOOLEAN DEFAULT false,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE TABLE audit_logs (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id     UUID REFERENCES users(id),
            action      VARCHAR(100) NOT NULL,
            entity_type VARCHAR(50),
            entity_id   UUID,
            details     JSONB,
            ip_address  INET,
            created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE TABLE submissions (
            id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            business_tenant  UUID NOT NULL,
            provider_id      UUID NOT NULL REFERENCES users(id),
            auditor_id       UUID REFERENCES users(id),
            document_ids     UUID[] NOT NULL DEFAULT '{}',
            status           VARCHAR(50) DEFAULT 'pending',
            notes            TEXT,
            auditor_notes    TEXT,
            submitted_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            company_name     VARCHAR(255)
        );
    """)

    # --- Indexes ---
    op.execute("CREATE INDEX idx_users_email      ON users(email);")
    op.execute("CREATE INDEX idx_users_role       ON users(role);")
    op.execute("CREATE INDEX idx_users_status     ON users(status);")
    op.execute("CREATE INDEX idx_users_tenant_id  ON users(tenant_id);")
    op.execute("CREATE INDEX idx_documents_user_id    ON documents(user_id);")
    op.execute("CREATE INDEX idx_documents_tenant_id  ON documents(tenant_id);")
    op.execute("CREATE INDEX idx_documents_status     ON documents(status);")
    op.execute("CREATE INDEX idx_audit_logs_user_id   ON audit_logs(user_id);")
    op.execute("CREATE INDEX idx_audit_logs_created   ON audit_logs(created_at);")
    op.execute("CREATE INDEX idx_prt_token            ON password_reset_tokens(token);")
    op.execute("CREATE INDEX idx_submissions_business ON submissions(business_tenant);")
    op.execute("CREATE INDEX idx_submissions_provider ON submissions(provider_id);")
    op.execute("CREATE INDEX idx_submissions_status   ON submissions(status);")

    # --- Triggers ---
    op.execute("""
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    op.execute("""
        CREATE TRIGGER update_submissions_updated_at
            BEFORE UPDATE ON submissions FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # --- Triggers ---
    op.execute("DROP TRIGGER IF EXISTS update_submissions_updated_at ON submissions;")
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users;")

    # --- Tables (reverse order of creation) ---
    op.execute("DROP TABLE IF EXISTS submissions;")
    op.execute("DROP TABLE IF EXISTS audit_logs;")
    op.execute("DROP TABLE IF EXISTS password_reset_tokens;")
    op.execute("DROP TABLE IF EXISTS documents;")
    op.execute("DROP TABLE IF EXISTS users;")

    # --- Function ---
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    # --- Enum types ---
    op.execute("DROP TYPE IF EXISTS document_status;")
    op.execute("DROP TYPE IF EXISTS user_status;")
    op.execute("DROP TYPE IF EXISTS user_role;")
