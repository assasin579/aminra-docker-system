-- AMINRA Auth Database Schema
-- PostgreSQL 15

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE user_role   AS ENUM ('business', 'provider');
CREATE TYPE user_status AS ENUM ('pending', 'active', 'suspended');
CREATE TYPE document_status AS ENUM ('uploaded', 'reviewing', 'approved', 'rejected');

-- Users table (both business users and provider users)
CREATE TABLE users (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email            VARCHAR(255) UNIQUE NOT NULL,
    password_hash    VARCHAR(255) NOT NULL,
    role             user_role NOT NULL,
    company_name     VARCHAR(255) NOT NULL,
    company_code     VARCHAR(100),                        -- Tax ID / Accreditation number
    status           user_status DEFAULT 'pending',
    -- Multi-tenant support (business users only)
    tenant_id        UUID,                                -- NULL for providers; = owner's id for members
    is_owner         BOOLEAN DEFAULT true,                -- false for invited members
    invited_by       UUID REFERENCES users(id) ON DELETE SET NULL,
    -- IHC (Internal Halal Committee) role for invited members
    ihc_role         VARCHAR(100),                        -- Chairman, Halal Executive, Dept Head, etc.
    department       VARCHAR(255),                        -- Bộ phận / phòng ban
    -- Provider approval
    approved_by      UUID REFERENCES users(id),
    approved_at      TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Documents table
CREATE TABLE documents (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename          VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path         TEXT,
    file_size         BIGINT,
    mime_type         VARCHAR(100),
    user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
    tenant_id         UUID,                               -- denormalised for fast tenant queries
    doc_type          VARCHAR(100),
    status            document_status DEFAULT 'uploaded',
    compliance_score  INTEGER CHECK (compliance_score >= 0 AND compliance_score <= 100),
    evaluation_result JSONB,
    uploaded_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_by       UUID REFERENCES users(id),
    reviewed_at       TIMESTAMP WITH TIME ZONE,
    review_notes      TEXT
);

-- Password reset tokens (for future use)
CREATE TABLE password_reset_tokens (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    token      VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used       BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Audit logs
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

-- Indexes
CREATE INDEX idx_users_email      ON users(email);
CREATE INDEX idx_users_role       ON users(role);
CREATE INDEX idx_users_status     ON users(status);
CREATE INDEX idx_users_tenant_id  ON users(tenant_id);
CREATE INDEX idx_documents_user_id    ON documents(user_id);
CREATE INDEX idx_documents_tenant_id  ON documents(tenant_id);
CREATE INDEX idx_documents_status     ON documents(status);
CREATE INDEX idx_audit_logs_user_id   ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created   ON audit_logs(created_at);
CREATE INDEX idx_prt_token            ON password_reset_tokens(token);

-- Submissions: business sends documents to provider for review
CREATE TABLE submissions (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_tenant  UUID NOT NULL,                       -- tenant_id of business
    provider_id      UUID NOT NULL REFERENCES users(id),  -- provider user receiving
    auditor_id       UUID REFERENCES users(id),           -- assigned auditor (provider's team)
    document_ids     UUID[] NOT NULL DEFAULT '{}',        -- array of document IDs included
    status           VARCHAR(50) DEFAULT 'pending',       -- pending, reviewing, returned, approved
    notes            TEXT,                                 -- business notes when submitting
    auditor_notes    TEXT,                                 -- auditor/provider feedback
    submitted_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    company_name     VARCHAR(255)                          -- cached for quick display
);

CREATE INDEX idx_submissions_business ON submissions(business_tenant);
CREATE INDEX idx_submissions_provider ON submissions(provider_id);
CREATE INDEX idx_submissions_status   ON submissions(status);

CREATE TRIGGER update_submissions_updated_at
    BEFORE UPDATE ON submissions FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Seed admin (password: admin123!)
INSERT INTO users (email, password_hash, role, company_name, status, is_owner, tenant_id)
VALUES (
    'admin@aminra.com',
    '$2b$12$UU6EFPdvEmajmujCPJzK6.AP/o8Ugio0Dkb4TiNTUj14SYTabUFxi',
    'provider',
    'AMINRA Admin',
    'active',
    true,
    NULL
);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO aminra_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO aminra_user;
GRANT EXECUTE ON ALL FUNCTIONS        IN SCHEMA public TO aminra_user;
