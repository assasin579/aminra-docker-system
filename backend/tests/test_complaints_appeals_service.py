from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord

pytestmark = pytest.mark.asyncio


async def test_appeal_requires_original_decision():
    from services import complaints_appeals as svc

    with pytest.raises(HTTPException) as exc:
        await svc.create_case(
            FakeConn(),
            provider_id=str(uuid4()),
            case_type="appeal_decision",
            source="business",
            title="Appeal",
            description="Appeal rejected decision",
            submitted_by_user_id=str(uuid4()),
        )
    assert exc.value.status_code == 400
    assert "original_decision_id" in str(exc.value.detail)


async def test_business_cannot_create_appeal_for_other_business_decision():
    from services import complaints_appeals as svc

    provider_id = uuid4()
    business_tenant = uuid4()
    other_business = uuid4()
    decision_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        (
            "FROM certification_decisions",
            FakeRecord(id=decision_id, provider_id=provider_id, business_tenant=other_business, submission_id=uuid4()),
        ),
    ]

    with pytest.raises(HTTPException) as exc:
        await svc.create_case(
            db,
            provider_id=str(provider_id),
            business_tenant=str(business_tenant),
            case_type="appeal_decision",
            source="business",
            title="Appeal",
            description="wrong business",
            submitted_by_user_id=str(uuid4()),
            original_decision_id=str(decision_id),
        )
    assert exc.value.status_code == 403
    assert not any(call[0] == "fetchrow" and "INSERT INTO complaint_cases" in call[1][0] for call in db.calls)


async def test_provider_cannot_create_inconsistent_appeal_submission():
    from services import complaints_appeals as svc

    provider_id = uuid4()
    business_tenant = uuid4()
    decision_submission = uuid4()
    supplied_submission = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        (
            "FROM certification_decisions",
            FakeRecord(id=uuid4(), provider_id=provider_id, business_tenant=business_tenant, submission_id=decision_submission),
        ),
    ]

    with pytest.raises(HTTPException) as exc:
        await svc.create_case(
            db,
            provider_id=str(provider_id),
            business_tenant=str(business_tenant),
            submission_id=str(supplied_submission),
            case_type="appeal_decision",
            source="provider",
            title="Appeal",
            description="inconsistent submission",
            submitted_by_user_id=str(uuid4()),
            original_decision_id=str(uuid4()),
        )
    assert exc.value.status_code == 400
    assert "submission_id" in str(exc.value.detail)


async def test_valid_same_business_appeal_creates_case(monkeypatch):
    from services import complaints_appeals as svc

    provider_id = uuid4()
    business_tenant = uuid4()
    submission_id = uuid4()
    decision_id = uuid4()
    case_id = uuid4()

    async def fake_log_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM certification_decisions", FakeRecord(id=decision_id, provider_id=provider_id, business_tenant=business_tenant, submission_id=submission_id)),
        ("FROM submissions", FakeRecord(id=submission_id, provider_id=provider_id, business_tenant=business_tenant)),
        ("INSERT INTO complaint_cases", FakeRecord(id=case_id, provider_id=provider_id, business_tenant=business_tenant, submission_id=submission_id, case_type="appeal_decision")),
        ("INSERT INTO complaint_case_events", FakeRecord(id=uuid4(), case_id=case_id, event_type="case.created")),
    ]

    result = await svc.create_case(
        db,
        provider_id=str(provider_id),
        business_tenant=str(business_tenant),
        case_type="appeal_decision",
        source="business",
        title="Appeal",
        description="same business",
        submitted_by_user_id=str(uuid4()),
        original_decision_id=str(decision_id),
    )
    assert result["id"] == str(case_id)
    insert_call = next(call for call in db.calls if call[0] == "fetchrow" and "INSERT INTO complaint_cases" in call[1][0])
    assert insert_call[1][1][1] == str(business_tenant)
    assert insert_call[1][1][3] == str(submission_id)


async def test_business_complaint_rejects_nonexistent_submission():
    from services import complaints_appeals as svc

    db = FakeConn()
    db.fetchrow_responses = [("FROM submissions", None)]

    with pytest.raises(HTTPException) as exc:
        await svc.create_case(
            db,
            provider_id=str(uuid4()),
            business_tenant=str(uuid4()),
            submission_id=str(uuid4()),
            case_type="complaint_service",
            source="business",
            title="Service issue",
            description="bad submission",
            submitted_by_user_id=str(uuid4()),
        )
    assert exc.value.status_code == 404
    assert "submission" in str(exc.value.detail).lower()
    assert not any(call[0] == "fetchrow" and "INSERT INTO complaint_cases" in call[1][0] for call in db.calls)


async def test_business_complaint_rejects_another_business_submission():
    from services import complaints_appeals as svc

    provider_id = uuid4()
    business_tenant = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM submissions", FakeRecord(id=uuid4(), provider_id=provider_id, business_tenant=uuid4())),
    ]

    with pytest.raises(HTTPException) as exc:
        await svc.create_case(
            db,
            provider_id=str(provider_id),
            business_tenant=str(business_tenant),
            submission_id=str(uuid4()),
            case_type="complaint_service",
            source="business",
            title="Service issue",
            description="wrong business submission",
            submitted_by_user_id=str(uuid4()),
        )
    assert exc.value.status_code == 400
    assert "business_tenant" in str(exc.value.detail)
    assert not any(call[0] == "fetchrow" and "INSERT INTO complaint_cases" in call[1][0] for call in db.calls)


async def test_business_complaint_rejects_another_provider_submission_as_not_found():
    from services import complaints_appeals as svc

    provider_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("FROM submissions", None)]

    with pytest.raises(HTTPException) as exc:
        await svc.create_case(
            db,
            provider_id=str(provider_id),
            business_tenant=str(uuid4()),
            submission_id=str(uuid4()),
            case_type="complaint_service",
            source="business",
            title="Service issue",
            description="cross provider submission",
            submitted_by_user_id=str(uuid4()),
        )
    assert exc.value.status_code == 404
    submission_select = next(call for call in db.calls if call[0] == "fetchrow" and "FROM submissions" in call[1][0])
    assert "provider_id=$2" in submission_select[1][0]
    assert submission_select[1][1][1] == str(provider_id)
    assert not any(call[0] == "fetchrow" and "INSERT INTO complaint_cases" in call[1][0] for call in db.calls)


async def test_business_complaint_accepts_own_submission(monkeypatch):
    from services import complaints_appeals as svc

    provider_id = uuid4()
    business_tenant = uuid4()
    submission_id = uuid4()
    case_id = uuid4()

    async def fake_log_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM submissions", FakeRecord(id=submission_id, provider_id=provider_id, business_tenant=business_tenant)),
        ("INSERT INTO complaint_cases", FakeRecord(id=case_id, provider_id=provider_id, business_tenant=business_tenant, submission_id=submission_id, case_type="complaint_service")),
        ("INSERT INTO complaint_case_events", FakeRecord(id=uuid4(), case_id=case_id, event_type="case.created")),
    ]

    result = await svc.create_case(
        db,
        provider_id=str(provider_id),
        business_tenant=str(business_tenant),
        submission_id=str(submission_id),
        case_type="complaint_service",
        source="business",
        title="Service issue",
        description="own submission",
        submitted_by_user_id=str(uuid4()),
    )
    assert result["id"] == str(case_id)
    submission_select = next(call for call in db.calls if call[0] == "fetchrow" and "FROM submissions" in call[1][0])
    assert "provider_id=$2" in submission_select[1][0]
    insert_call = next(call for call in db.calls if call[0] == "fetchrow" and "INSERT INTO complaint_cases" in call[1][0])
    assert insert_call[1][1][3] == str(submission_id)


async def test_complaint_rejects_cross_scope_certificate_id():
    from services import complaints_appeals as svc

    provider_id = uuid4()
    business_tenant = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM halal_certificates", FakeRecord(id=uuid4(), issued_by=provider_id, business_tenant=uuid4(), submission_id=uuid4())),
    ]

    with pytest.raises(HTTPException) as exc:
        await svc.create_case(
            db,
            provider_id=str(provider_id),
            business_tenant=str(business_tenant),
            certificate_id=str(uuid4()),
            case_type="complaint_certified_client",
            source="business",
            title="Certificate issue",
            description="wrong cert",
            submitted_by_user_id=str(uuid4()),
        )
    assert exc.value.status_code == 400
    assert "certificate business_tenant" in str(exc.value.detail).lower()
    assert not any(call[0] == "fetchrow" and "INSERT INTO complaint_cases" in call[1][0] for call in db.calls)


async def test_complaint_accepts_valid_certificate(monkeypatch):
    from services import complaints_appeals as svc

    provider_id = uuid4()
    business_tenant = uuid4()
    submission_id = uuid4()
    certificate_id = uuid4()
    case_id = uuid4()

    async def fake_log_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM submissions", FakeRecord(id=submission_id, provider_id=provider_id, business_tenant=business_tenant)),
        ("FROM halal_certificates", FakeRecord(id=certificate_id, issued_by=provider_id, business_tenant=business_tenant, submission_id=submission_id)),
        ("INSERT INTO complaint_cases", FakeRecord(id=case_id, provider_id=provider_id, business_tenant=business_tenant, certificate_id=certificate_id, submission_id=submission_id, case_type="complaint_certified_client")),
        ("INSERT INTO complaint_case_events", FakeRecord(id=uuid4(), case_id=case_id, event_type="case.created")),
    ]

    result = await svc.create_case(
        db,
        provider_id=str(provider_id),
        business_tenant=str(business_tenant),
        certificate_id=str(certificate_id),
        submission_id=str(submission_id),
        case_type="complaint_certified_client",
        source="business",
        title="Certificate issue",
        description="valid cert",
        submitted_by_user_id=str(uuid4()),
    )
    assert result["id"] == str(case_id)
    cert_select = next(call for call in db.calls if call[0] == "fetchrow" and "FROM halal_certificates" in call[1][0])
    assert "issued_by=$2" in cert_select[1][0]
    insert_call = next(call for call in db.calls if call[0] == "fetchrow" and "INSERT INTO complaint_cases" in call[1][0])
    assert insert_call[1][1][2:4] == (str(certificate_id), str(submission_id))


async def test_assigning_appeal_to_original_decision_maker_fails():
    from services import complaints_appeals as svc

    provider_id = uuid4()
    owner_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM users", FakeRecord(id=owner_id, tenant_id=provider_id, role="provider", status="active")),
        (
            "FROM complaint_cases cc",
            FakeRecord(
                id=uuid4(),
                case_type="appeal_decision",
                original_decision_id=uuid4(),
                original_decision_maker_id=owner_id,
                audit_visit_auditor_id=uuid4(),
                business_tenant=uuid4(),
            ),
        ),
    ]

    with pytest.raises(HTTPException) as exc:
        await svc.assign_case_owner(db, case_id=str(uuid4()), provider_id=str(provider_id), owner_id=str(owner_id), actor_user_id=str(uuid4()))
    assert exc.value.status_code == 403
    assert "original decision maker" in str(exc.value.detail).lower()


async def test_assigning_appeal_to_linked_audit_auditor_fails():
    from services import complaints_appeals as svc

    provider_id = uuid4()
    auditor_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM users", FakeRecord(id=auditor_id, tenant_id=provider_id, role="provider", status="active")),
        (
            "FROM complaint_cases cc",
            FakeRecord(
                id=uuid4(),
                case_type="appeal_decision",
                original_decision_id=uuid4(),
                original_decision_maker_id=uuid4(),
                audit_visit_auditor_id=auditor_id,
                business_tenant=uuid4(),
            ),
        ),
    ]

    with pytest.raises(HTTPException) as exc:
        await svc.assign_case_owner(db, case_id=str(uuid4()), provider_id=str(provider_id), owner_id=str(auditor_id), actor_user_id=str(uuid4()))
    assert exc.value.status_code == 403
    assert "audit auditor" in str(exc.value.detail).lower()


async def test_unresolved_coi_blocks_assignment():
    from services import complaints_appeals as svc

    provider_id = uuid4()
    owner_id = uuid4()
    business_tenant = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM users", FakeRecord(id=owner_id, tenant_id=provider_id, role="provider", status="active")),
        (
            "FROM complaint_cases cc",
            FakeRecord(
                id=uuid4(),
                case_type="complaint_service",
                original_decision_id=None,
                original_decision_maker_id=None,
                audit_visit_auditor_id=None,
                business_tenant=business_tenant,
            ),
        ),
        ("FROM conflict_declarations", FakeRecord(id=uuid4(), status="declared", provider_id=provider_id)),
    ]

    with pytest.raises(HTTPException) as exc:
        await svc.assign_case_owner(db, case_id=str(uuid4()), provider_id=str(provider_id), owner_id=str(owner_id), actor_user_id=str(uuid4()))
    assert exc.value.status_code == 409
    assert "conflict" in str(exc.value.detail).lower()
    assert not any(call[0] == "fetchrow" and "UPDATE complaint_cases" in call[1][0] for call in db.calls)


async def test_assign_owner_rejects_arbitrary_or_out_of_provider_user():
    from services import complaints_appeals as svc

    db = FakeConn()
    db.fetchrow_responses = [("FROM users", None)]

    with pytest.raises(HTTPException) as exc:
        await svc.assign_case_owner(db, case_id=str(uuid4()), provider_id=str(uuid4()), owner_id=str(uuid4()), actor_user_id=str(uuid4()))
    assert exc.value.status_code == 404
    assert not any(call[0] == "fetchrow" and "FROM complaint_cases cc" in call[1][0] for call in db.calls)


async def test_assign_owner_accepts_provider_staff(monkeypatch):
    from services import complaints_appeals as svc

    provider_id = uuid4()
    owner_id = uuid4()
    case_id = uuid4()

    async def fake_log_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM users", FakeRecord(id=owner_id, tenant_id=provider_id, role="provider", status="active")),
        ("FROM complaint_cases cc", FakeRecord(id=case_id, case_type="complaint_service", original_decision_id=None, business_tenant=None)),
        ("UPDATE complaint_cases", FakeRecord(id=case_id, assigned_owner_id=owner_id, status="received")),
        ("INSERT INTO complaint_case_events", FakeRecord(id=uuid4(), case_id=case_id, event_type="case.assigned")),
    ]

    result = await svc.assign_case_owner(db, case_id=str(case_id), provider_id=str(provider_id), owner_id=str(owner_id), actor_user_id=str(uuid4()))
    assert result["assigned_owner_id"] == str(owner_id)
    user_select = next(call for call in db.calls if call[0] == "fetchrow" and "FROM users" in call[1][0])
    assert "role='provider'" in user_select[1][0]
    assert "tenant_id=$2 OR id=$2" in user_select[1][0]


async def test_valid_lifecycle_writes_transition_events_and_audit(monkeypatch):
    from services import complaints_appeals as svc

    provider_id = uuid4()
    case_id = uuid4()
    actor_id = uuid4()
    audit_calls = []

    async def fake_log_audit(*args, **kwargs):
        audit_calls.append((args, kwargs))

    monkeypatch.setattr(svc, "log_audit", fake_log_audit)

    async def one_transition(from_status: str, to_status: str, **kwargs):
        db = FakeConn()
        db.fetchrow_responses = [
            ("SELECT * FROM complaint_cases", FakeRecord(id=case_id, provider_id=provider_id, status=from_status)),
            ("UPDATE complaint_cases", FakeRecord(id=case_id, provider_id=provider_id, status=to_status, **kwargs)),
            ("INSERT INTO complaint_case_events", FakeRecord(id=uuid4(), case_id=case_id, event_type="case.transition", from_status=from_status, to_status=to_status)),
        ]
        result = await svc.transition_case(
            db,
            case_id=str(case_id),
            provider_id=str(provider_id),
            actor_user_id=str(actor_id),
            to_status=to_status,
            decision_summary=kwargs.get("decision_summary"),
            closure_reason=kwargs.get("closure_reason"),
        )
        event_call = next(call for call in db.calls if call[0] == "fetchrow" and "INSERT INTO complaint_case_events" in call[1][0])
        assert event_call[1][1][3:5] == (from_status, to_status)
        return result

    await one_transition("received", "acknowledged")
    await one_transition("acknowledged", "under_investigation")
    await one_transition("under_investigation", "decision_made", decision_summary="appeal upheld")
    result = await one_transition("decision_made", "closed", closure_reason="notified parties")

    assert result["status"] == "closed"
    assert len([call for call in audit_calls if call[1]["action"] == "complaint.transition"]) == 4


async def test_close_without_reason_rejected():
    from services import complaints_appeals as svc

    db = FakeConn()
    db.fetchrow_responses = [("SELECT * FROM complaint_cases", FakeRecord(id=uuid4(), status="decision_made"))]

    with pytest.raises(HTTPException) as exc:
        await svc.transition_case(db, case_id=str(uuid4()), provider_id=str(uuid4()), actor_user_id=str(uuid4()), to_status="closed")
    assert exc.value.status_code == 400
    assert "closure_reason" in str(exc.value.detail)


async def test_decision_made_without_summary_rejected():
    from services import complaints_appeals as svc

    db = FakeConn()
    db.fetchrow_responses = [("SELECT * FROM complaint_cases", FakeRecord(id=uuid4(), status="under_investigation"))]

    with pytest.raises(HTTPException) as exc:
        await svc.transition_case(db, case_id=str(uuid4()), provider_id=str(uuid4()), actor_user_id=str(uuid4()), to_status="decision_made")
    assert exc.value.status_code == 400
    assert "decision_summary" in str(exc.value.detail)


async def test_add_case_event_appends():
    from services import complaints_appeals as svc

    case_id = uuid4()
    actor_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("INSERT INTO complaint_case_events", FakeRecord(id=uuid4(), case_id=case_id, event_type="note.added"))]

    result = await svc.add_case_event(db, case_id=str(case_id), actor_user_id=str(actor_id), event_type="note.added", notes="called complainant", metadata={"channel": "phone"})

    assert result["event_type"] == "note.added"
    insert_call = next(call for call in db.calls if call[0] == "fetchrow" and "INSERT INTO complaint_case_events" in call[1][0])
    assert insert_call[1][1][0] == str(case_id)
    assert insert_call[1][1][2] == "note.added"
    assert '\"channel\": \"phone\"' in insert_call[1][1][6]
