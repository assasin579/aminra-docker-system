from __future__ import annotations

from pathlib import Path


def test_conflict_interest_migration_contract():
    migration = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "048_conflicts_interest.py"
    text = migration.read_text()

    assert 'revision = "048_conflicts_interest"' in text
    assert len("048_conflicts_interest") <= 32
    assert 'down_revision = "047_cert_decisions"' in text
    assert "CREATE TABLE IF NOT EXISTS conflict_declarations" in text
    assert "person_user_id UUID NOT NULL REFERENCES users(id)" in text
    assert "person_role TEXT NOT NULL CHECK" in text
    assert "auditor" in text and "reviewer" in text and "decision_maker" in text and "cb_admin" in text
    assert "conflict_type TEXT NOT NULL CHECK" in text
    assert "prior_employment" in text and "financial_interest" in text and "other" in text
    assert "status TEXT NOT NULL CHECK" in text
    assert "declared" in text and "cleared" in text and "blocked" in text and "overridden" in text
    assert "CREATE TABLE IF NOT EXISTS conflict_overrides" in text
    assert "idx_conflict_decl_provider" in text
    assert "idx_conflict_decl_business" in text
    assert "idx_conflict_decl_person" in text
    assert "idx_conflict_decl_status" in text
    assert "idx_conflict_decl_unresolved" in text
    assert "WHERE status IN ('declared','under_review','blocked')" in text
    assert "DROP TABLE IF EXISTS conflict_overrides" in text
    assert "DROP TABLE IF EXISTS conflict_declarations" in text
