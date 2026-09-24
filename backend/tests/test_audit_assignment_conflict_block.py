from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord

pytestmark = pytest.mark.asyncio


async def test_audit_assignment_unresolved_conflict_blocks_before_update(monkeypatch):
    from auth import audit_router

    provider_id = uuid4()
    visit_id = uuid4()
    business_tenant = uuid4()
    auditor_id = uuid4()
    conflict_calls = []

    async def fake_tenant_id(user, db):
        return provider_id

    async def fake_conflict_gate(db, *, provider_id, business_tenant, person_user_id, action):
        conflict_calls.append((provider_id, business_tenant, person_user_id, action))
        raise HTTPException(409, "Unresolved conflict of interest blocks audit.assign")

    monkeypatch.setattr(audit_router, "resolve_canonical_tenant_id", fake_tenant_id)
    monkeypatch.setattr(audit_router, "assert_no_unresolved_conflict", fake_conflict_gate)

    db = FakeConn()
    db.fetchrow_responses = [
        ("SELECT id, company_name FROM users", FakeRecord(id=auditor_id, company_name="Auditor A")),
        ("SELECT business_tenant FROM audit_visits", FakeRecord(business_tenant=business_tenant)),
    ]
    user = {"role": "provider", "is_owner": True, "sub": str(uuid4()), "tenant_id": str(provider_id)}

    with pytest.raises(HTTPException) as exc:
        await audit_router.assign_visit_auditor(str(visit_id), {"auditor_id": str(auditor_id)}, user, db)

    assert exc.value.status_code == 409
    assert conflict_calls == [(str(provider_id), str(business_tenant), str(auditor_id), "audit.assign")]
    assert not any(call[0] == "execute" and "UPDATE audit_visits SET auditor_id" in call[1][0] for call in db.calls)


async def test_audit_assignment_cleared_or_overridden_conflict_allows_update(monkeypatch):
    from auth import audit_router

    provider_id = uuid4()
    visit_id = uuid4()
    business_tenant = uuid4()
    auditor_id = uuid4()

    async def fake_tenant_id(user, db):
        return provider_id

    async def fake_conflict_gate(*args, **kwargs):
        return None

    async def fake_notify(*args, **kwargs):
        return None

    monkeypatch.setattr(audit_router, "resolve_canonical_tenant_id", fake_tenant_id)
    monkeypatch.setattr(audit_router, "assert_no_unresolved_conflict", fake_conflict_gate)
    monkeypatch.setattr(audit_router, "notify", fake_notify)

    db = FakeConn()
    db.fetchrow_responses = [
        ("SELECT id, company_name FROM users", FakeRecord(id=auditor_id, company_name="Auditor A")),
        ("SELECT business_tenant FROM audit_visits WHERE id=$1 AND provider_id=$2", FakeRecord(business_tenant=business_tenant)),
        ("SELECT business_tenant, scheduled_date FROM audit_visits", None),
    ]
    user = {"role": "provider", "is_owner": True, "sub": str(uuid4()), "tenant_id": str(provider_id)}

    result = await audit_router.assign_visit_auditor(str(visit_id), {"auditor_id": str(auditor_id)}, user, db)

    assert "Đã gán" in result["message"]
    update_call = next(call for call in db.calls if call[0] == "execute" and "UPDATE audit_visits SET auditor_id" in call[1][0])
    assert update_call[1][1] == (str(auditor_id), str(visit_id), provider_id)


async def test_cross_provider_conflict_does_not_leak_into_assignment_gate():
    from services.conflict_interest import assert_no_unresolved_conflict

    provider_id = uuid4()
    business_tenant = uuid4()
    auditor_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("FROM conflict_declarations", None)]

    await assert_no_unresolved_conflict(db, provider_id=str(provider_id), business_tenant=str(business_tenant), person_user_id=str(auditor_id), action="audit.assign")
    select_call = next(call for call in db.calls if call[0] == "fetchrow" and "FROM conflict_declarations" in call[1][0])
    assert "provider_id=$1" in select_call[1][0]
    assert select_call[1][1][0] == str(provider_id)
