from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord

pytestmark = pytest.mark.asyncio


async def test_issue_certificate_calls_certification_decision_gate_before_insert(monkeypatch):
    from auth import certificate_router

    provider_id = uuid4()
    business_tenant = uuid4()
    submission_id = uuid4()
    gate_calls = []

    async def fake_gate(db, *, submission_id, provider_id):
        gate_calls.append((submission_id, provider_id))
        raise HTTPException(409, "approved certification decision required")

    monkeypatch.setattr(certificate_router, "assert_certificate_issue_allowed", fake_gate)

    async def fake_tenant_id(user, db):
        return provider_id

    monkeypatch.setattr(certificate_router, "resolve_canonical_tenant_id", fake_tenant_id)

    db = FakeConn()
    db.fetch_responses = [("FROM submissions", [FakeRecord(id=submission_id, status="approved")])]
    user = {"role": "provider", "is_owner": True, "sub": str(uuid4()), "tenant_id": str(provider_id)}

    with pytest.raises(HTTPException) as exc:
        await certificate_router.issue_certificate_for_company(
            str(business_tenant),
            certificate_router.IssueCertRequest(expiry_months=12, notes=""),
            user,
            db,
        )

    assert exc.value.status_code == 409
    assert gate_calls == [(str(submission_id), str(provider_id))]
    assert not any(call[0] == "fetchrow" and "INSERT INTO halal_certificates" in call[1][0] for call in db.calls)


async def test_company_certificate_gate_checks_every_active_approved_submission(monkeypatch):
    from auth import certificate_router

    provider_id = uuid4()
    business_tenant = uuid4()
    first_submission = uuid4()
    second_submission = uuid4()
    gate_calls = []

    async def fake_gate(db, *, submission_id, provider_id):
        gate_calls.append((submission_id, provider_id))
        if submission_id == str(second_submission):
            raise HTTPException(409, "approved certification decision required")

    monkeypatch.setattr(certificate_router, "assert_certificate_issue_allowed", fake_gate)

    async def fake_tenant_id(user, db):
        return provider_id

    monkeypatch.setattr(certificate_router, "resolve_canonical_tenant_id", fake_tenant_id)

    db = FakeConn()
    db.fetch_responses = [("FROM submissions", [FakeRecord(id=first_submission, status="approved"), FakeRecord(id=second_submission, status="approved")])]
    user = {"role": "provider", "is_owner": True, "sub": str(uuid4()), "tenant_id": str(provider_id)}

    with pytest.raises(HTTPException) as exc:
        await certificate_router.issue_certificate_for_company(str(business_tenant), certificate_router.IssueCertRequest(), user, db)

    assert exc.value.status_code == 409
    assert gate_calls == [(str(first_submission), str(provider_id)), (str(second_submission), str(provider_id))]
    assert not any(call[0] == "fetchrow" and "INSERT INTO halal_certificates" in call[1][0] for call in db.calls)
