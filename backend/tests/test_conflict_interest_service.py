from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord

pytestmark = pytest.mark.asyncio


async def test_declare_conflict_persists_canonical_fields_and_audit(monkeypatch):
    from services import conflict_interest as svc

    provider_id = uuid4()
    business_tenant = uuid4()
    person_user_id = uuid4()
    declared_by = uuid4()
    conflict_id = uuid4()
    audit_calls = []

    async def fake_log_audit(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    db = FakeConn()
    db.fetchrow_responses = [
        ("INSERT INTO conflict_declarations", FakeRecord(id=conflict_id, provider_id=provider_id, business_tenant=business_tenant, person_user_id=person_user_id, status="declared")),
    ]

    result = await svc.declare_conflict(
        db,
        provider_id=str(provider_id),
        business_tenant=str(business_tenant),
        person_user_id=str(person_user_id),
        person_role="auditor",
        conflict_type="financial_interest",
        description="Owns shares in applicant",
        declared_by=str(declared_by),
        user={"sub": str(declared_by), "role": "provider"},
    )

    assert result["id"] == str(conflict_id)
    insert_call = next(call for call in db.calls if call[0] == "fetchrow" and "INSERT INTO conflict_declarations" in call[1][0])
    assert insert_call[1][1][0:7] == (str(provider_id), str(business_tenant), str(person_user_id), "auditor", "financial_interest", "Owns shares in applicant", str(declared_by))
    assert audit_calls and audit_calls[0][1]["action"] == "conflict.declare"


async def test_assert_unresolved_conflict_blocks_and_scopes_provider_business_person():
    from services.conflict_interest import assert_no_unresolved_conflict

    provider_id = uuid4()
    business_tenant = uuid4()
    person_user_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("FROM conflict_declarations", FakeRecord(id=uuid4(), status="declared", provider_id=provider_id))]

    with pytest.raises(HTTPException) as exc:
        await assert_no_unresolved_conflict(
            db,
            provider_id=str(provider_id),
            business_tenant=str(business_tenant),
            person_user_id=str(person_user_id),
            action="audit.assign",
        )
    assert exc.value.status_code == 409
    select_call = next(call for call in db.calls if call[0] == "fetchrow" and "FROM conflict_declarations" in call[1][0])
    assert "provider_id=$1" in select_call[1][0]
    assert "business_tenant=$2" in select_call[1][0]
    assert "person_user_id=$3" in select_call[1][0]
    assert "valid_until IS NULL OR valid_until >= CURRENT_DATE" in select_call[1][0]
    assert select_call[1][1] == (str(provider_id), str(business_tenant), str(person_user_id))


async def test_cleared_overridden_expired_or_cross_provider_conflicts_do_not_block():
    from services.conflict_interest import assert_no_unresolved_conflict

    db = FakeConn()
    db.fetchrow_responses = [("FROM conflict_declarations", None)]
    await assert_no_unresolved_conflict(
        db,
        provider_id=str(uuid4()),
        business_tenant=str(uuid4()),
        person_user_id=str(uuid4()),
        action="audit.assign",
    )
    select_sql = db.calls[0][1][0]
    assert "status IN ('declared','under_review','blocked')" in select_sql
    assert "provider_id=$1" in select_sql


async def test_review_conflict_requires_reason_and_updates_scoped_row(monkeypatch):
    from services import conflict_interest as svc

    provider_id = uuid4()
    conflict_id = uuid4()
    reviewer_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("UPDATE conflict_declarations", FakeRecord(id=conflict_id, provider_id=provider_id, status="cleared"))]

    async def fake_log_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    result = await svc.review_conflict(
        db,
        conflict_id=str(conflict_id),
        provider_id=str(provider_id),
        reviewed_by=str(reviewer_id),
        status="cleared",
        review_reason="No current relationship",
        user={},
    )
    assert result["status"] == "cleared"
    update_call = next(call for call in db.calls if call[0] == "fetchrow" and "UPDATE conflict_declarations" in call[1][0])
    assert "WHERE id=$1 AND provider_id=$2" in update_call[1][0]

    with pytest.raises(HTTPException) as exc:
        await svc.review_conflict(db, conflict_id=str(conflict_id), provider_id=str(provider_id), reviewed_by=str(reviewer_id), status="cleared", review_reason=" ")
    assert exc.value.status_code == 400


async def test_override_requires_owner_or_admin_and_reason(monkeypatch):
    from services import conflict_interest as svc

    provider_id = uuid4()
    conflict_id = uuid4()
    actor_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("SELECT * FROM conflict_declarations", FakeRecord(id=conflict_id, provider_id=provider_id, status="blocked")),
        ("INSERT INTO conflict_overrides", FakeRecord(id=uuid4(), declaration_id=conflict_id)),
        ("UPDATE conflict_declarations", FakeRecord(id=conflict_id, provider_id=provider_id, status="overridden")),
    ]

    async def fake_log_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    result = await svc.override_conflict(
        db,
        conflict_id=str(conflict_id),
        provider_id=str(provider_id),
        overridden_by=str(actor_id),
        override_reason="Committee documented mitigation",
        caller={"role": "provider", "is_owner": True, "sub": str(actor_id)},
    )
    assert result["status"] == "overridden"

    with pytest.raises(HTTPException) as exc:
        await svc.override_conflict(db, conflict_id=str(conflict_id), provider_id=str(provider_id), overridden_by=str(actor_id), override_reason="ok", caller={"role": "provider", "is_owner": False})
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc2:
        await svc.override_conflict(db, conflict_id=str(conflict_id), provider_id=str(provider_id), overridden_by=str(actor_id), override_reason=" ", caller={"role": "provider", "is_owner": True})
    assert exc2.value.status_code == 400
