from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord
from tests.test_certification_decision_router import OverrideDB


def test_conflict_router_registered_in_app():
    from app import app

    paths = set(app.openapi()["paths"])
    assert "/api/conflicts" in paths
    assert "/api/conflicts/{conflict_id}" in paths
    assert "/api/conflicts/{conflict_id}/review" in paths
    assert "/api/conflicts/{conflict_id}/override" in paths


def test_conflict_routes_declare_list_review_override(monkeypatch):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import conflict_router as router
    from services import conflict_interest as svc

    provider_id = uuid4()
    actor_id = uuid4()
    business_tenant = uuid4()
    person_user_id = uuid4()
    conflict_id = uuid4()
    db = FakeConn()
    db.fetch_responses = [("FROM conflict_declarations", [FakeRecord(id=conflict_id, provider_id=provider_id, business_tenant=business_tenant, person_user_id=person_user_id, status="declared")])]
    db.fetchrow_responses = [
        ("INSERT INTO conflict_declarations", FakeRecord(id=conflict_id, provider_id=provider_id, business_tenant=business_tenant, person_user_id=person_user_id, status="declared")),
        ("SET status='overridden'", FakeRecord(id=conflict_id, provider_id=provider_id, status="overridden")),
        ("UPDATE conflict_declarations", FakeRecord(id=conflict_id, provider_id=provider_id, status="cleared")),
        ("SELECT * FROM conflict_declarations", FakeRecord(id=conflict_id, provider_id=provider_id, status="blocked")),
        ("INSERT INTO conflict_overrides", FakeRecord(id=uuid4(), declaration_id=conflict_id)),
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
        declare_res = client.post(
            "/api/conflicts",
            json={
                "business_tenant": str(business_tenant),
                "person_user_id": str(person_user_id),
                "person_role": "auditor",
                "conflict_type": "consultancy",
                "description": "Prior paid consulting",
            },
        )
        list_res = client.get("/api/conflicts", params={"business_tenant": str(business_tenant), "status": "declared"})
        review_res = client.post(f"/api/conflicts/{conflict_id}/review", json={"status": "cleared", "review_reason": "No active conflict"})
        override_res = client.post(f"/api/conflicts/{conflict_id}/override", json={"override_reason": "committee mitigation"})
    finally:
        app.dependency_overrides.clear()

    assert declare_res.status_code == 200, declare_res.text
    assert list_res.status_code == 200, list_res.text
    assert list_res.json()["conflicts"][0]["id"] == str(conflict_id)
    assert review_res.status_code == 200, review_res.text
    assert override_res.status_code == 200, override_res.text


def test_conflict_override_requires_reason_ui_contract_at_api(monkeypatch):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import conflict_router as router

    provider_id = uuid4()
    actor_id = uuid4()
    db = FakeConn()

    async def fake_user_id(user, db):
        return actor_id

    async def fake_tenant_id(user, db):
        return provider_id

    monkeypatch.setattr(router, "resolve_canonical_user_id", fake_user_id)
    monkeypatch.setattr(router, "resolve_canonical_tenant_id", fake_tenant_id)

    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: {"role": "provider", "is_owner": True, "sub": str(actor_id), "tenant_id": str(provider_id)}
    try:
        res = TestClient(app).post(f"/api/conflicts/{uuid4()}/override", json={"override_reason": " "})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 400
    assert "override_reason" in res.text


def test_conflict_routes_deny_business_user(monkeypatch):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user

    app.dependency_overrides[get_db] = OverrideDB(FakeConn())
    app.dependency_overrides[get_current_user] = lambda: {"role": "business", "is_owner": True, "sub": str(uuid4()), "tenant_id": str(uuid4())}
    try:
        res = TestClient(app).get("/api/conflicts")
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 403
