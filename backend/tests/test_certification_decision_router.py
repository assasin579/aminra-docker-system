from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


class OverrideDB:
    def __init__(self, db):
        self.db = db

    async def __call__(self):
        return self.db


def _client(monkeypatch, db, user):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user

    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_router_registered_in_app():
    from app import app

    paths = set(app.openapi()["paths"])
    assert "/api/certification-decisions" in paths
    assert "/api/certification-decisions/{decision_id}/approve" in paths
    assert "/api/certification-decisions/submission/{submission_id}" in paths


def test_create_decision_route_denies_business(monkeypatch):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import certification_decision_router as router

    async def fake_user_id(user, db):
        return uuid4()

    async def fake_tenant_id(user, db):
        return uuid4()

    monkeypatch.setattr(router, "resolve_canonical_user_id", fake_user_id)
    monkeypatch.setattr(router, "resolve_canonical_tenant_id", fake_tenant_id)

    db = FakeConn()
    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: {"role": "business", "is_owner": True, "sub": str(uuid4()), "tenant_id": str(uuid4())}
    try:
        res = TestClient(app).post("/api/certification-decisions", json={"submission_id": str(uuid4())})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 403


def test_create_and_approve_decision_routes(monkeypatch):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import certification_decision_router as router

    provider_id = uuid4()
    actor_id = uuid4()
    decision_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM submissions", FakeRecord(id=uuid4(), business_tenant=uuid4(), provider_id=provider_id, auditor_id=uuid4())),
        ("SELECT id\n        FROM certification_decisions", None),
        ("INSERT INTO certification_decisions", FakeRecord(id=decision_id, status="pending_review")),
        ("FROM certification_decisions cd", FakeRecord(id=decision_id, status="pending_review", provider_id=provider_id, assigned_auditor_id=uuid4(), business_tenant=uuid4())),
        ("FROM conflict_declarations", None),
        ("UPDATE certification_decisions", FakeRecord(id=decision_id, status="approved")),
    ]
    async def fake_user_id(user, db):
        return actor_id

    async def fake_tenant_id(user, db):
        return provider_id

    monkeypatch.setattr(router, "resolve_canonical_user_id", fake_user_id)
    monkeypatch.setattr(router, "resolve_canonical_tenant_id", fake_tenant_id)

    async def fake_log_audit(*args, **kwargs):
        return None
    from services import certification_decisions as svc
    monkeypatch.setattr(svc, "log_audit", fake_log_audit)

    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: {"role": "provider", "is_owner": True, "sub": str(actor_id), "tenant_id": str(provider_id)}
    try:
        client = TestClient(app)
        create_res = client.post("/api/certification-decisions", json={"submission_id": str(uuid4())})
        approve_res = client.post(f"/api/certification-decisions/{decision_id}/approve", json={"reason": "independent reviewer approval"})
    finally:
        app.dependency_overrides.clear()

    assert create_res.status_code == 200
    assert approve_res.status_code == 200


def test_business_get_decision_scopes_to_business_tenant(monkeypatch):
    from app import app
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import certification_decision_router as router

    business_tenant = uuid4()
    actor_id = uuid4()
    submission_id = uuid4()
    decision_id = uuid4()
    provider_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM certification_decisions", FakeRecord(id=decision_id, submission_id=submission_id, provider_id=provider_id, business_tenant=business_tenant, status="approved")),
    ]

    async def fake_user_id(user, db):
        return actor_id

    async def fake_tenant_id(user, db):
        return business_tenant

    monkeypatch.setattr(router, "resolve_canonical_user_id", fake_user_id)
    monkeypatch.setattr(router, "resolve_canonical_tenant_id", fake_tenant_id)

    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: {"role": "business", "is_owner": True, "sub": str(actor_id), "tenant_id": str(business_tenant)}
    try:
        res = TestClient(app).get(f"/api/certification-decisions/submission/{submission_id}")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    select_call = next(call for call in db.calls if call[0] == "fetchrow" and "FROM certification_decisions" in call[1][0])
    assert "business_tenant=$2" in select_call[1][0]
    assert select_call[1][1] == (str(submission_id), str(business_tenant))
