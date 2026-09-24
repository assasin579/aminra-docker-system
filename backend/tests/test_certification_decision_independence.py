from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord

pytestmark = pytest.mark.asyncio


async def test_certificate_issue_requires_approved_decision():
    from services.certification_decisions import assert_certificate_issue_allowed

    db = FakeConn()
    db.fetchrow_responses = [("FROM certification_decisions", None)]

    with pytest.raises(HTTPException) as exc:
        await assert_certificate_issue_allowed(db, submission_id=str(uuid4()), provider_id=str(uuid4()))
    assert exc.value.status_code == 409
    assert "approved certification decision" in str(exc.value.detail).lower()


async def test_rejected_decision_blocks_certificate_issue():
    from services.certification_decisions import assert_certificate_issue_allowed

    provider_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("FROM certification_decisions", FakeRecord(status="rejected", provider_id=provider_id))]

    with pytest.raises(HTTPException) as exc:
        await assert_certificate_issue_allowed(db, submission_id=str(uuid4()), provider_id=str(provider_id))
    assert exc.value.status_code == 409
    assert "rejected" in str(exc.value.detail).lower()
    select_call = next(call for call in db.calls if call[0] == "fetchrow" and "FROM certification_decisions" in call[1][0])
    assert "ORDER BY created_at DESC, decided_at DESC NULLS LAST, id DESC" in select_call[1][0]


async def test_approved_decision_allows_certificate_issue_for_same_provider():
    from services.certification_decisions import assert_certificate_issue_allowed

    provider_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("FROM certification_decisions", FakeRecord(status="approved", provider_id=provider_id))]

    await assert_certificate_issue_allowed(db, submission_id=str(uuid4()), provider_id=str(provider_id))


async def test_later_approved_decision_after_rejected_allows_certificate_issue():
    from services.certification_decisions import assert_certificate_issue_allowed

    provider_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("FROM certification_decisions", FakeRecord(status="approved", provider_id=provider_id))]

    await assert_certificate_issue_allowed(db, submission_id=str(uuid4()), provider_id=str(provider_id))
    select_call = next(call for call in db.calls if call[0] == "fetchrow" and "FROM certification_decisions" in call[1][0])
    assert "status <> 'cancelled'" in select_call[1][0]
    assert "ORDER BY created_at DESC, decided_at DESC NULLS LAST, id DESC" in select_call[1][0]


async def test_create_decision_case_persists_canonical_fields_and_audit(monkeypatch):
    from services import certification_decisions as svc

    submission_id = uuid4()
    business_tenant = uuid4()
    provider_id = uuid4()
    audit_visit_id = uuid4()
    actor_id = uuid4()
    decision_id = uuid4()
    audit_calls = []

    async def fake_log_audit(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM submissions", FakeRecord(id=submission_id, business_tenant=business_tenant, provider_id=provider_id, auditor_id=uuid4())),
        ("SELECT id\n        FROM certification_decisions", None),
        ("FROM audit_visits", FakeRecord(id=audit_visit_id)),
        ("INSERT INTO certification_decisions", FakeRecord(id=decision_id, status="pending_review")),
    ]

    result = await svc.create_decision_case(
        db,
        submission_id=str(submission_id),
        created_by=str(actor_id),
        audit_visit_id=str(audit_visit_id),
        user={"role": "provider", "sub": str(actor_id)},
        provider_id=str(provider_id),
    )

    assert result["id"] == decision_id
    insert_call = next(call for call in db.calls if call[0] == "fetchrow" and "INSERT INTO certification_decisions" in call[1][0])
    assert insert_call[1][1][0:5] == (str(submission_id), business_tenant, provider_id, str(audit_visit_id), str(actor_id))
    assert audit_calls and audit_calls[0][1]["action"] == "certification_decision.create"


async def test_create_decision_case_scopes_submission_to_provider():
    from services import certification_decisions as svc

    provider_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("FROM submissions", None)]

    with pytest.raises(HTTPException) as exc:
        await svc.create_decision_case(db, submission_id=str(uuid4()), created_by=str(uuid4()), provider_id=str(provider_id))
    assert exc.value.status_code == 404
    submission_select = next(call for call in db.calls if call[0] == "fetchrow" and "FROM submissions" in call[1][0])
    assert "provider_id=$2" in submission_select[1][0]
    assert submission_select[1][1][1] == str(provider_id)


async def test_create_decision_case_validates_audit_visit_scope():
    from services import certification_decisions as svc

    provider_id = uuid4()
    business_tenant = uuid4()
    audit_visit_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM submissions", FakeRecord(id=uuid4(), business_tenant=business_tenant, provider_id=provider_id, auditor_id=uuid4())),
        ("SELECT id\n        FROM certification_decisions", None),
        ("FROM audit_visits", None),
    ]

    with pytest.raises(HTTPException) as exc:
        await svc.create_decision_case(
            db,
            submission_id=str(uuid4()),
            created_by=str(uuid4()),
            provider_id=str(provider_id),
            audit_visit_id=str(audit_visit_id),
        )
    assert exc.value.status_code == 404
    visit_select = next(call for call in db.calls if call[0] == "fetchrow" and "FROM audit_visits" in call[1][0])
    assert "provider_id=$2" in visit_select[1][0]
    assert "business_tenant=$3" in visit_select[1][0]


async def test_create_decision_case_rejects_invalid_reviewer():
    from services import certification_decisions as svc

    provider_id = uuid4()
    reviewer_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("FROM users", None)]

    with pytest.raises(HTTPException) as exc:
        await svc.create_decision_case(
            db,
            submission_id=str(uuid4()),
            created_by=str(uuid4()),
            provider_id=str(provider_id),
            reviewer_id=str(reviewer_id),
        )
    assert exc.value.status_code == 404
    assert not any(call[0] == "fetchrow" and "FROM submissions" in call[1][0] for call in db.calls)


async def test_create_decision_case_rejects_reviewer_who_is_audit_visit_auditor():
    from services import certification_decisions as svc

    provider_id = uuid4()
    business_tenant = uuid4()
    submission_auditor_id = uuid4()
    visit_auditor_id = uuid4()
    audit_visit_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM users", FakeRecord(id=visit_auditor_id, tenant_id=provider_id, role="provider", status="active")),
        ("FROM submissions", FakeRecord(id=uuid4(), business_tenant=business_tenant, provider_id=provider_id, auditor_id=submission_auditor_id)),
        ("FROM conflict_declarations", None),
        ("SELECT id\n        FROM certification_decisions", None),
        ("FROM audit_visits", FakeRecord(id=audit_visit_id, auditor_id=visit_auditor_id)),
    ]

    with pytest.raises(HTTPException) as exc:
        await svc.create_decision_case(
            db,
            submission_id=str(uuid4()),
            created_by=str(uuid4()),
            provider_id=str(provider_id),
            audit_visit_id=str(audit_visit_id),
            reviewer_id=str(visit_auditor_id),
        )
    assert exc.value.status_code == 403
    assert "audit visit auditor" in str(exc.value.detail).lower()
    assert not any(call[0] == "fetchrow" and "INSERT INTO certification_decisions" in call[1][0] for call in db.calls)


async def test_create_decision_case_accepts_same_provider_staff_reviewer(monkeypatch):
    from services import certification_decisions as svc

    provider_id = uuid4()
    business_tenant = uuid4()
    reviewer_id = uuid4()
    actor_id = uuid4()
    decision_id = uuid4()

    async def fake_log_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM users", FakeRecord(id=reviewer_id, tenant_id=provider_id, role="provider", status="active")),
        ("FROM submissions", FakeRecord(id=uuid4(), business_tenant=business_tenant, provider_id=provider_id, auditor_id=uuid4())),
        ("FROM conflict_declarations", None),
        ("SELECT id\n        FROM certification_decisions", None),
        ("INSERT INTO certification_decisions", FakeRecord(id=decision_id, status="pending_review", reviewer_id=reviewer_id)),
    ]

    result = await svc.create_decision_case(
        db,
        submission_id=str(uuid4()),
        created_by=str(actor_id),
        provider_id=str(provider_id),
        reviewer_id=str(reviewer_id),
    )
    assert result["id"] == decision_id
    user_select = next(call for call in db.calls if call[0] == "fetchrow" and "FROM users" in call[1][0])
    assert "role='provider'" in user_select[1][0]
    insert_call = next(call for call in db.calls if call[0] == "fetchrow" and "INSERT INTO certification_decisions" in call[1][0])
    assert insert_call[1][1][5] == str(reviewer_id)


async def test_duplicate_active_decision_returns_conflict():
    from services import certification_decisions as svc

    provider_id = uuid4()
    business_tenant = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM submissions", FakeRecord(id=uuid4(), business_tenant=business_tenant, provider_id=provider_id, auditor_id=uuid4())),
        ("FROM certification_decisions", FakeRecord(id=uuid4())),
    ]

    with pytest.raises(HTTPException) as exc:
        await svc.create_decision_case(db, submission_id=str(uuid4()), created_by=str(uuid4()), provider_id=str(provider_id))
    assert exc.value.status_code == 409
    duplicate_select = next(call for call in db.calls if call[0] == "fetchrow" and "FROM certification_decisions" in call[1][0])
    assert "status IN ('pending_review','approved')" in duplicate_select[1][0]


async def test_rejected_decision_does_not_block_new_pending_review_case(monkeypatch):
    from services import certification_decisions as svc

    submission_id = uuid4()
    business_tenant = uuid4()
    provider_id = uuid4()
    actor_id = uuid4()
    decision_id = uuid4()

    async def fake_log_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM submissions", FakeRecord(id=submission_id, business_tenant=business_tenant, provider_id=provider_id, auditor_id=uuid4())),
        ("SELECT id\n        FROM certification_decisions", None),
        ("INSERT INTO certification_decisions", FakeRecord(id=decision_id, status="pending_review")),
    ]

    result = await svc.create_decision_case(db, submission_id=str(submission_id), created_by=str(actor_id), provider_id=str(provider_id))

    assert result["id"] == decision_id
    duplicate_select = next(call for call in db.calls if call[0] == "fetchrow" and "FROM certification_decisions" in call[1][0])
    assert "status IN ('pending_review','approved')" in duplicate_select[1][0]
    assert "status <> 'cancelled'" not in duplicate_select[1][0]


async def test_assigned_auditor_cannot_approve_and_reason_required(monkeypatch):
    from services import certification_decisions as svc

    decision_id = uuid4()
    auditor_id = uuid4()
    provider_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM certification_decisions cd", FakeRecord(id=decision_id, status="pending_review", provider_id=provider_id, assigned_auditor_id=auditor_id, business_tenant=uuid4())),
    ]

    with pytest.raises(HTTPException) as exc:
        await svc.approve_decision(db, decision_id=str(decision_id), decision_maker_id=str(auditor_id), reason="ok", user={}, provider_id=str(provider_id))
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc2:
        await svc.reject_decision(db, decision_id=str(decision_id), decision_maker_id=str(uuid4()), provider_id=str(provider_id), reason=" ", user={})
    assert exc2.value.status_code == 400


async def test_provider_owner_assigned_as_auditor_cannot_self_approve():
    from services.certification_decisions import approve_decision

    owner_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM certification_decisions cd", FakeRecord(id=uuid4(), status="pending_review", provider_id=uuid4(), assigned_auditor_id=owner_id, business_tenant=uuid4())),
    ]

    with pytest.raises(HTTPException) as exc:
        await approve_decision(db, decision_id=str(uuid4()), decision_maker_id=str(owner_id), reason="independent decision", user={}, provider_id=str(uuid4()))
    assert exc.value.status_code == 403


async def test_approve_decision_scopes_select_and_update_to_provider(monkeypatch):
    from services import certification_decisions as svc

    decision_id = uuid4()
    provider_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM certification_decisions cd", FakeRecord(id=decision_id, status="pending_review", provider_id=provider_id, assigned_auditor_id=uuid4(), visit_auditor_id=None, business_tenant=uuid4())),
        ("FROM conflict_declarations", None),
        ("UPDATE certification_decisions", FakeRecord(id=decision_id, status="approved")),
    ]

    async def fake_log_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    await svc.approve_decision(db, decision_id=str(decision_id), decision_maker_id=str(uuid4()), reason="ok", user={}, provider_id=str(provider_id))
    select_call = next(call for call in db.calls if call[0] == "fetchrow" and "FROM certification_decisions cd" in call[1][0])
    update_call = next(call for call in db.calls if call[0] == "fetchrow" and "UPDATE certification_decisions" in call[1][0])
    assert "cd.provider_id=$2" in select_call[1][0]
    assert "provider_id=$6" in update_call[1][0]
    assert "status='pending_review'" in update_call[1][0]


async def test_stale_finalize_update_returns_conflict(monkeypatch):
    from services import certification_decisions as svc

    decision_id = uuid4()
    provider_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM certification_decisions cd", FakeRecord(id=decision_id, status="pending_review", provider_id=provider_id, assigned_auditor_id=uuid4(), visit_auditor_id=None, business_tenant=uuid4())),
        ("FROM conflict_declarations", None),
        ("UPDATE certification_decisions", None),
    ]

    async def fake_log_audit(*args, **kwargs):
        raise AssertionError("stale finalize must not write audit")

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    with pytest.raises(HTTPException) as exc:
        await svc.approve_decision(db, decision_id=str(decision_id), decision_maker_id=str(uuid4()), reason="ok", user={}, provider_id=str(provider_id))
    assert exc.value.status_code == 409


async def test_unresolved_conflict_blocks_decision_approval(monkeypatch):
    from services import certification_decisions as svc

    decision_id = uuid4()
    provider_id = uuid4()
    business_tenant = uuid4()
    decision_maker_id = uuid4()
    conflict_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM certification_decisions cd", FakeRecord(id=decision_id, status="pending_review", provider_id=provider_id, assigned_auditor_id=uuid4(), visit_auditor_id=None, business_tenant=business_tenant)),
        ("FROM conflict_declarations", FakeRecord(id=conflict_id, status="declared", provider_id=provider_id)),
    ]

    async def fake_log_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    with pytest.raises(HTTPException) as exc:
        await svc.approve_decision(
            db,
            decision_id=str(decision_id),
            decision_maker_id=str(decision_maker_id),
            reason="independent decision",
            user={},
            provider_id=str(provider_id),
        )
    assert exc.value.status_code == 409
    assert not any(call[0] == "fetchrow" and "UPDATE certification_decisions" in call[1][0] for call in db.calls)


async def test_audit_visit_auditor_cannot_finalize_decision():
    from services.certification_decisions import reject_decision

    auditor_id = uuid4()
    provider_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM certification_decisions cd", FakeRecord(id=uuid4(), status="pending_review", provider_id=provider_id, assigned_auditor_id=uuid4(), visit_auditor_id=auditor_id)),
    ]

    with pytest.raises(HTTPException) as exc:
        await reject_decision(db, decision_id=str(uuid4()), decision_maker_id=str(auditor_id), reason="independent decision", user={}, provider_id=str(provider_id))
    assert exc.value.status_code == 403
