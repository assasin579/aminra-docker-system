-- Run as migration administrator after creating aminra_app LOGIN with a secret
-- supplied through Vault. Application must never own schema objects or roles.
ALTER ROLE aminra_app NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
GRANT CONNECT ON DATABASE aminra TO aminra_app;
GRANT USAGE ON SCHEMA public TO aminra_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aminra_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO aminra_app;
REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM aminra_app;
REVOKE UPDATE, DELETE ON dossier_document_attachments FROM aminra_app;
ALTER DEFAULT PRIVILEGES FOR ROLE aminra_user IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aminra_app;
ALTER DEFAULT PRIVILEGES FOR ROLE aminra_user IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO aminra_app;
