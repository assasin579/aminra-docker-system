from __future__ import annotations

from pathlib import Path


def test_complaints_appeals_migration_contract():
    migration = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "050_complaints_appeals.py"
    text = migration.read_text()

    assert 'revision = "050_complaints_appeals"' in text
    assert len("050_complaints_appeals") <= 32
    assert 'down_revision = "048_conflicts_interest"' in text
    assert "CREATE TABLE IF NOT EXISTS complaint_cases" in text
    assert "provider_id UUID NOT NULL" in text
    assert "business_tenant UUID" in text
    assert "certificate_id UUID REFERENCES halal_certificates(id)" in text
    assert "submission_id UUID REFERENCES submissions(id)" in text
    assert "case_type TEXT NOT NULL" in text
    assert "complaint_service" in text and "complaint_certified_client" in text and "appeal_decision" in text
    assert "source TEXT NOT NULL" in text
    assert "business" in text and "provider" in text and "public" in text and "internal" in text
    assert "status TEXT NOT NULL" in text
    assert "received" in text and "acknowledged" in text and "under_investigation" in text
    assert "decision_made" in text and "closed" in text and "rejected" in text
    assert "submitted_by_user_id UUID REFERENCES users(id)" in text
    assert "assigned_owner_id UUID REFERENCES users(id)" in text
    assert "original_decision_id UUID REFERENCES certification_decisions(id)" in text
    assert "case_type <> 'appeal_decision' OR original_decision_id IS NOT NULL" in text
    assert "status <> 'closed'" in text and "closure_reason" in text
    assert "status <> 'decision_made'" in text and "decision_summary" in text
    assert "CREATE TABLE IF NOT EXISTS complaint_case_events" in text
    assert "metadata JSONB NOT NULL DEFAULT '{}'::jsonb" in text
    assert "DROP TABLE IF EXISTS complaint_case_events" in text
    assert "DROP TABLE IF EXISTS complaint_cases" in text
