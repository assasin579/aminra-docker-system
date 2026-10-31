from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import dossier_router
from auth.db import get_db
from auth.jwt_utils import get_current_user

TENANT = "11111111-1111-4111-8111-111111111111"
DOSSIER = "22222222-2222-4222-8222-222222222222"
VERSION = "33333333-3333-4333-8333-333333333333"
DOCUMENT = "44444444-4444-4444-8444-444444444444"
ACTOR = "55555555-5555-4555-8555-555555555555"


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


class _DB:
    def __init__(self, *, dossier_binding="bound", document_tenant=TENANT, document_type="policy"):
        self.calls = []
        self.dossier_binding = dossier_binding
        self.document_tenant = document_tenant
        self.document_type = document_type
        self.associations = set()
        self.saved_attachment = None

    def transaction(self):
        return _Transaction()

    async def fetchrow(self, query, *args):
        self.calls.append(("fetchrow", query, args))
        if "FROM dossiers d" in query and "FOR UPDATE" in query:
            if str(args[0]) != DOSSIER or str(args[1]) != TENANT:
                return None
            return {
                "id": DOSSIER,
                "tenant_id": TENANT,
                "requirements_version_id": VERSION if self.dossier_binding == "bound" else None,
                "requirements_binding_status": self.dossier_binding,
                "requirements_state": "published",
                "status": "in_progress",
            }
        if "FROM standard_requirement_version_slots" in query:
            return {"doc_type": "policy"} if (str(args[0]), args[1]) == (VERSION, "policy") else None
        if "FROM documents" in query and "tenant_id" in query:
            if str(args[0]) != DOCUMENT or str(args[1]) != TENANT:
                return None
            return {"id": DOCUMENT, "tenant_id": self.document_tenant, "doc_type": self.document_type}
        if "FROM dossier_document_attachments a" in query and "JOIN documents d" in query:
            return self.saved_attachment
        if "INSERT INTO dossier_document_attachments" in query:
            self.saved_attachment = {
                "dossier_id": DOSSIER, "document_id": DOCUMENT, "doc_type": "policy",
                "requirements_version_id": VERSION, "request_sha256": args[6],
                "attached_by": ACTOR, "id": DOCUMENT, "tenant_id": TENANT,
                "filename": "file.pdf", "original_filename": "file.pdf", "status": "pending",
                "compliance_score": None, "version_number": 1, "uploaded_at": "2026-10-26T00:00:00+00:00",
            }
            key = tuple(str(value) for value in args[:4])
            self.associations.add(key)
            return {"dossier_id": DOSSIER, "document_id": DOCUMENT, "doc_type": "policy"}
        if "FROM dossier_document_attachments" in query:
            return {"dossier_id": DOSSIER, "document_id": DOCUMENT, "doc_type": "policy"} if self.associations else None
        return None

    async def execute(self, query, *args):
        self.calls.append(("execute", query, args))


def _client(monkeypatch, db, *, role="business"):
    app = FastAPI()
    app.include_router(dossier_router.router, prefix="/api/dossiers")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {
        "role": role,
        "tenant_id": "untrusted-client-tenant",
        "app_user_id": ACTOR,
    }
    monkeypatch.setattr(dossier_router, "_resolve_tenant_id", lambda *_args: _resolved_tenant())
    async def allow_upload(*_args):
        return None
    async def resolve_actor(*_args):
        return ACTOR
    monkeypatch.setattr(dossier_router, "check_permission_db", allow_upload)
    monkeypatch.setattr(dossier_router, "resolve_canonical_user_id", resolve_actor)
    return TestClient(app)


async def _resolved_tenant():
    return TENANT


def test_existing_document_attachment_is_reference_idempotent_and_uses_server_binding(monkeypatch):
    db = _DB()
    client = _client(monkeypatch, db)
    data = {"document_id": DOCUMENT, "doc_type": "policy", "requirements_version_id": str(uuid4()), "tenant_id": str(uuid4())}
    key = str(uuid4())
    first = client.post(f"/api/dossiers/{DOSSIER}/documents", data=data, headers={"Idempotency-Key": key})
    second = client.post(f"/api/dossiers/{DOSSIER}/documents", data=data, headers={"Idempotency-Key": key})

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["document_id"] == DOCUMENT
    assert second.json()["document_id"] == DOCUMENT
    assert second.json()["created_attachment"] is False
    inserts = [query for _, query, _ in db.calls if "INSERT INTO dossier_document_attachments" in query]
    assert len(inserts) == 1
    conflict = client.post(
        f"/api/dossiers/{DOSSIER}/documents",
        data={"document_id": str(uuid4()), "doc_type": "policy"},
        headers={"Idempotency-Key": key},
    )
    assert conflict.status_code == 409
    dossier_query = next(query for kind, query, _ in db.calls if kind == "fetchrow" and "FROM dossiers d" in query)
    assert "tenant_id=$2" in dossier_query and "requirements_version_id" in dossier_query


def test_attachment_fails_closed_for_unknown_binding_wrong_slot_wrong_type_and_wrong_tenant(monkeypatch):
    unknown_db = _DB(dossier_binding="unknown")
    response = _client(monkeypatch, unknown_db).post(
        f"/api/dossiers/{DOSSIER}/documents", data={"document_id": DOCUMENT, "doc_type": "policy"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert response.status_code == 409
    assert not any("INSERT INTO dossier_document_attachments" in query for _, query, _ in unknown_db.calls)

    wrong_tenant_db = _DB(document_tenant="99999999-9999-4999-8999-999999999999")
    response = _client(monkeypatch, wrong_tenant_db).post(
        f"/api/dossiers/{DOSSIER}/documents", data={"document_id": DOCUMENT, "doc_type": "policy"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert response.status_code == 404
    assert not any("INSERT INTO dossier_document_attachments" in query for _, query, _ in wrong_tenant_db.calls)

    wrong_type_db = _DB(document_type="certificate")
    response = _client(monkeypatch, wrong_type_db).post(
        f"/api/dossiers/{DOSSIER}/documents", data={"document_id": DOCUMENT, "doc_type": "policy"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert response.status_code == 409
    assert not any("INSERT INTO dossier_document_attachments" in query for _, query, _ in wrong_type_db.calls)

    wrong_slot_db = _DB()
    response = _client(monkeypatch, wrong_slot_db).post(
        f"/api/dossiers/{DOSSIER}/documents", data={"document_id": DOCUMENT, "doc_type": "unknown-slot"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert response.status_code == 422
    assert not any("INSERT INTO dossier_document_attachments" in query for _, query, _ in wrong_slot_db.calls)


def test_nonbusiness_actor_is_denied_before_database_access(monkeypatch):
    db = _DB()
    response = _client(monkeypatch, db, role="provider").post(
        f"/api/dossiers/{DOSSIER}/documents", data={"document_id": DOCUMENT, "doc_type": "policy"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert response.status_code == 403
    assert db.calls == []


def test_certified_dossier_rejects_attachment_without_writes(monkeypatch):
    db = _DB()
    original_fetchrow = db.fetchrow

    async def certified(query, *args):
        row = await original_fetchrow(query, *args)
        if row and 'FROM dossiers d' in query:
            row['status'] = 'cert_issued'
        return row

    db.fetchrow = certified
    response = _client(monkeypatch, db).post(
        f'/api/dossiers/{DOSSIER}/documents',
        data={'document_id': DOCUMENT, 'doc_type': 'policy'},
        headers={'Idempotency-Key': str(uuid4())},
    )
    assert response.status_code == 409
    assert not any('INSERT INTO' in query for _, query, _ in db.calls)
