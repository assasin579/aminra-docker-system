from __future__ import annotations

from pathlib import Path


def test_certification_decision_migration_contract():
    migration = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "047_cert_decisions.py"
    text = migration.read_text()

    assert 'revision = "047_cert_decisions"' in text
    assert len("047_cert_decisions") <= 32
    assert 'down_revision = "046_module_activation_escal"' in text
    assert "CREATE TABLE IF NOT EXISTS certification_decisions" in text
    assert "submission_id UUID NOT NULL REFERENCES submissions(id)" in text
    assert "business_tenant UUID NOT NULL" in text
    assert "provider_id UUID NOT NULL" in text
    assert "audit_visit_id UUID REFERENCES audit_visits(id)" in text
    assert "reviewer_id UUID REFERENCES users(id)" in text
    assert "decision_maker_id UUID REFERENCES users(id)" in text
    assert "created_by UUID NOT NULL REFERENCES users(id)" in text
    assert "status TEXT NOT NULL" in text
    assert "pending_review" in text and "approved" in text and "rejected" in text and "cancelled" in text
    assert "decision_maker_id IS NOT NULL" in text
    assert "btrim(decision_reason) <> ''" in text
    assert "decided_at IS NOT NULL" in text
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_certification_decisions_submission_active" in text
    assert "WHERE status IN ('pending_review','approved')" in text
    assert "WHERE status <> 'cancelled'" not in text
    assert "CREATE INDEX IF NOT EXISTS idx_certification_decisions_provider_status" in text
    assert "CREATE INDEX IF NOT EXISTS idx_certification_decisions_submission" in text
    assert "CREATE INDEX IF NOT EXISTS idx_certification_decisions_business" in text
    assert "DROP TABLE IF EXISTS certification_decision_events" in text
    assert "DROP TABLE IF EXISTS certification_decisions" in text
