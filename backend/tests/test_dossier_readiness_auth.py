from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

def _valid_readiness_payload(dossier_id="dossier-1", tenant_id="tenant-1"):
    return {
        "dossier_id": dossier_id,
        "tenant_id": tenant_id,
        "status": "in_progress",
        "title": "Dossier",
        "state": "ready_for_decision",
        "readiness_percent": 75,
        "certificate_issue_blocked": False,
        "safe_public_trace_available": False,
        "next_action": "finalize_certification_decision",
        "next_actor_role": "decision_maker",
        "next_action_owner_role": "decision_maker",
        "due_date": None,
        "required_documents": ["policy"],
        "missing_required_documents": [],
        "unreviewed_documents": [],
        "rejected_documents": [],
        "open_ncrs": [],
        "blocking_ncrs": [],
        "certification_decision": {"id": None, "status": None, "reason": None},
        "certificate": {"id": None, "cert_number": None, "status": None},
        "blocking_reasons": [],
    }


class FakeConn:
    def __init__(self):
        self.calls = []


class OverrideDB:
    def __init__(self, db):
        self.db = db

    async def __call__(self):
        return self.db


def _isolated_app():
    """Mount only the production dossier router, avoiding unrelated app startup."""
    from fastapi import FastAPI
    from auth.dossier_router import router

    app = FastAPI()
    app.include_router(router, prefix="/api/dossiers")
    return app


def _request(monkeypatch, *, user, canonical_tenant=None, readiness_result=None):
    app = _isolated_app()
    from auth import dossier_router
    from auth.db import get_db
    from auth.jwt_utils import get_current_user

    db = FakeConn()
    db.fetchrow_responses = [("FROM dossiers", None)]
    resolved = []

    async def resolve(_db, identity):
        resolved.append(identity)
        return canonical_tenant

    async def compute(_db, *, dossier_id, tenant_id):
        return readiness_result or _valid_readiness_payload(dossier_id, tenant_id)

    monkeypatch.setattr(dossier_router, "_resolve_tenant_id", resolve)
    monkeypatch.setattr(dossier_router, "compute_dossier_readiness", compute)
    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = TestClient(app).get(f"/api/dossiers/{uuid4()}/readiness")
    finally:
        app.dependency_overrides.clear()
    return response, resolved, db


def test_readiness_response_contract_rejects_invalid_percent_and_nested_items():
    from pydantic import ValidationError
    from auth.dossier_router import DossierReadinessResponse

    invalid_percent = {**_valid_readiness_payload(), "readiness_percent": 101}
    with pytest.raises(ValidationError):
        DossierReadinessResponse.model_validate(invalid_percent)

    invalid_item = {**_valid_readiness_payload(), "open_ncrs": [None]}
    with pytest.raises(ValidationError):
        DossierReadinessResponse.model_validate(invalid_item)


def test_readiness_rejects_provider_role(monkeypatch):
    response, _, _ = _request(
        monkeypatch,
        user={"role": "provider", "tenant_id": str(uuid4())},
        canonical_tenant=uuid4(),
    )
    assert response.status_code == 403


def test_business_readiness_uses_resolved_canonical_tenant_not_identity_claim(monkeypatch):
    canonical_tenant = uuid4()
    claimed_tenant = uuid4()
    dossier_id = uuid4()
    app = _isolated_app()
    from auth import dossier_router
    from auth.db import get_db
    from auth.jwt_utils import get_current_user

    db = FakeConn()
    passed = []

    async def resolve(_db, identity):
        return canonical_tenant

    async def compute(_db, *, dossier_id, tenant_id):
        passed.append((dossier_id, tenant_id))
        return _valid_readiness_payload(dossier_id, tenant_id)

    monkeypatch.setattr(dossier_router, "_resolve_tenant_id", resolve)
    monkeypatch.setattr(dossier_router, "compute_dossier_readiness", compute)
    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: {
        "role": "business", "tenant_id": str(claimed_tenant), "email": "biz@example.test"
    }
    try:
        response = TestClient(app).get(f"/api/dossiers/{dossier_id}/readiness?tenant_id={claimed_tenant}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert passed == [(str(dossier_id), str(canonical_tenant))]


def test_business_without_resolvable_tenant_is_denied(monkeypatch):
    response, _, db = _request(
        monkeypatch, user={"role": "business", "tenant_id": str(uuid4())}, canonical_tenant=None
    )
    assert response.status_code == 404
    assert not db.calls


def test_malformed_dossier_id_is_rejected_before_readiness_computation(monkeypatch):
    app = _isolated_app()
    from auth import dossier_router
    from auth.db import get_db
    from auth.jwt_utils import get_current_user

    called = []
    async def resolve(_db, _identity):
        return uuid4()
    async def compute(*args, **kwargs):
        called.append(True)
    monkeypatch.setattr(dossier_router, "_resolve_tenant_id", resolve)
    monkeypatch.setattr(dossier_router, "compute_dossier_readiness", compute)
    app.dependency_overrides[get_db] = OverrideDB(FakeConn())
    app.dependency_overrides[get_current_user] = lambda: {"role": "business"}
    try:
        response = TestClient(app).get("/api/dossiers/not-a-uuid/readiness")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert not called
