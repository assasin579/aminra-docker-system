from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord
from tests.test_certification_decision_router import OverrideDB


def test_complaints_router_registered_in_app():
    from app import app

    paths = set(app.openapi()["paths"])
    assert "/api/complaints" in paths
    assert "/api/complaints/{case_id}" in paths
    assert "/api/complaints/{case_id}/assign" in paths
    assert "/api/complaints/{case_id}/transition" in paths
    assert "/api/complaints/{case_id}/events" in paths


def test_business_can_create_and_list_own_complaints(monkeypatch):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import complaints_router as router
    from services import complaints_appeals as svc

    business_tenant = uuid4()
    actor_id = uuid4()
    provider_id = uuid4()
    case_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("INSERT INTO complaint_cases", FakeRecord(id=case_id, provider_id=provider_id, business_tenant=business_tenant, status="received", case_type="complaint_service")),
        ("INSERT INTO complaint_case_events", FakeRecord(id=uuid4(), case_id=case_id, event_type="case.created")),
    ]
    db.fetch_responses = [("FROM complaint_cases", [FakeRecord(id=case_id, provider_id=provider_id, business_tenant=business_tenant, status="received")])]

    async def fake_user_id(user, db):
        return actor_id

    async def fake_tenant_id(user, db):
        return business_tenant

    async def fake_log_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(router, "resolve_canonical_user_id", fake_user_id)
    monkeypatch.setattr(router, "resolve_canonical_tenant_id", fake_tenant_id)
    monkeypatch.setattr(svc, "log_audit", fake_log_audit)

    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: {"role": "business", "is_owner": True, "sub": str(actor_id), "tenant_id": str(business_tenant)}
    try:
        client = TestClient(app)
        create_res = client.post(
            "/api/complaints",
            json={
                "provider_id": str(provider_id),
                "business_tenant": str(business_tenant),
                "case_type": "complaint_service",
                "source": "business",
                "title": "Service issue",
                "description": "Complaint body",
            },
        )
        list_res = client.get("/api/complaints")
    finally:
        app.dependency_overrides.clear()

    assert create_res.status_code == 200, create_res.text
    assert list_res.status_code == 200, list_res.text
    assert list_res.json()["cases"][0]["id"] == str(case_id)
    list_call = next(call for call in db.calls if call[0] == "fetch" and "FROM complaint_cases" in call[1][0])
    assert "business_tenant=$1" in list_call[1][0]


def test_business_create_rejects_nonexistent_submission_id(monkeypatch):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import complaints_router as router

    business_tenant = uuid4()
    actor_id = uuid4()
    provider_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("FROM submissions", None)]

    async def fake_user_id(user, db):
        return actor_id

    async def fake_tenant_id(user, db):
        return business_tenant

    monkeypatch.setattr(router, "resolve_canonical_user_id", fake_user_id)
    monkeypatch.setattr(router, "resolve_canonical_tenant_id", fake_tenant_id)

    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: {"role": "business", "is_owner": True, "sub": str(actor_id), "tenant_id": str(business_tenant)}
    try:
        res = TestClient(app).post(
            "/api/complaints",
            json={
                "provider_id": str(provider_id),
                "case_type": "complaint_service",
                "source": "business",
                "title": "Service issue",
                "description": "Complaint body",
                "submission_id": str(uuid4()),
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 404
    assert "submission" in res.text.lower()
    assert not any(call[0] == "fetchrow" and "INSERT INTO complaint_cases" in call[1][0] for call in db.calls)


def test_business_cannot_create_for_other_tenant(monkeypatch):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import complaints_router as router

    business_tenant = uuid4()
    actor_id = uuid4()

    async def fake_user_id(user, db):
        return actor_id

    async def fake_tenant_id(user, db):
        return business_tenant

    monkeypatch.setattr(router, "resolve_canonical_user_id", fake_user_id)
    monkeypatch.setattr(router, "resolve_canonical_tenant_id", fake_tenant_id)

    app.dependency_overrides[get_db] = OverrideDB(FakeConn())
    app.dependency_overrides[get_current_user] = lambda: {"role": "business", "is_owner": True, "sub": str(actor_id), "tenant_id": str(business_tenant)}
    try:
        res = TestClient(app).post(
            "/api/complaints",
            json={
                "provider_id": str(uuid4()),
                "business_tenant": str(uuid4()),
                "case_type": "complaint_service",
                "source": "business",
                "title": "Service issue",
                "description": "Complaint body",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 403


def test_provider_owner_can_assign_transition_and_add_event(monkeypatch):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import complaints_router as router
    from services import complaints_appeals as svc

    provider_id = uuid4()
    actor_id = uuid4()
    owner_id = uuid4()
    case_id = uuid4()
    business_tenant = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM users", FakeRecord(id=owner_id, tenant_id=provider_id, role="provider", status="active")),
        ("FROM complaint_cases cc", FakeRecord(id=case_id, provider_id=provider_id, business_tenant=business_tenant, case_type="complaint_service")),
        ("FROM conflict_declarations", None),
        ("UPDATE complaint_cases", FakeRecord(id=case_id, provider_id=provider_id, status="received", assigned_owner_id=owner_id)),
        ("INSERT INTO complaint_case_events", FakeRecord(id=uuid4(), case_id=case_id, event_type="case.assigned")),
        ("SELECT * FROM complaint_cases WHERE id=$1 AND provider_id=$2", FakeRecord(id=case_id, provider_id=provider_id, status="received")),
        ("SELECT * FROM complaint_cases", FakeRecord(id=case_id, provider_id=provider_id, status="received")),
    ]

    async def fake_user_id(user, db):
        return actor_id

    async def fake_tenant_id(user, db):
        return provider_id

    async def fake_log_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(router, "resolve_canonical_user_id", fake_user_id)
    monkeypatch.setattr(router, "resolve_canonical_tenant_id", fake_tenant_id)
    monkeypatch.setattr(svc, "log_audit", fake_log_audit)

    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: {"role": "provider", "is_owner": True, "sub": str(actor_id), "tenant_id": str(provider_id)}
    try:
        client = TestClient(app)
        assign_res = client.post(f"/api/complaints/{case_id}/assign", json={"owner_id": str(owner_id), "notes": "independent owner"})
        transition_res = client.post(f"/api/complaints/{case_id}/transition", json={"to_status": "acknowledged", "notes": "ack"})
        event_res = client.post(f"/api/complaints/{case_id}/events", json={"event_type": "note.added", "notes": "called"})
    finally:
        app.dependency_overrides.clear()

    assert assign_res.status_code == 200, assign_res.text
    assert transition_res.status_code == 200, transition_res.text
    assert event_res.status_code == 200, event_res.text


def test_provider_auditor_cannot_list_all_provider_cases(monkeypatch):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import complaints_router as router

    async def fake_user_id(user, db):
        return uuid4()

    async def fake_tenant_id(user, db):
        return uuid4()

    monkeypatch.setattr(router, "resolve_canonical_user_id", fake_user_id)
    monkeypatch.setattr(router, "resolve_canonical_tenant_id", fake_tenant_id)

    app.dependency_overrides[get_db] = OverrideDB(FakeConn())
    app.dependency_overrides[get_current_user] = lambda: {"role": "provider", "is_owner": False, "sub": str(uuid4()), "tenant_id": str(uuid4())}
    try:
        res = TestClient(app).get("/api/complaints")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 403


def test_close_without_reason_rejected_at_api(monkeypatch):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import complaints_router as router

    provider_id = uuid4()
    actor_id = uuid4()
    case_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("SELECT * FROM complaint_cases", FakeRecord(id=case_id, provider_id=provider_id, status="decision_made"))]

    async def fake_user_id(user, db):
        return actor_id

    async def fake_tenant_id(user, db):
        return provider_id

    monkeypatch.setattr(router, "resolve_canonical_user_id", fake_user_id)
    monkeypatch.setattr(router, "resolve_canonical_tenant_id", fake_tenant_id)

    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: {"role": "provider", "is_owner": True, "sub": str(actor_id), "tenant_id": str(provider_id)}
    try:
        res = TestClient(app).post(f"/api/complaints/{case_id}/transition", json={"to_status": "closed"})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 400
    assert "closure_reason" in res.text
