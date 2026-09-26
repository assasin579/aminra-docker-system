from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException

from auth import document_router

pytestmark = pytest.mark.asyncio


class BoundaryDb:
    def __init__(self, *, rows_by_op: dict[str, object] | None = None):
        self.rows_by_op = rows_by_op or {}
        self.fetchrow_calls: list[tuple[str, tuple[object, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetchrow(self, sql: str, *args):
        self.fetchrow_calls.append((sql, args))
        normalized = " ".join(sql.lower().split())
        if "count(*) from latest" in normalized:
            return {"count": self.rows_by_op.get("list_count", 0)}
        if "select id, doc_type from documents" in normalized:
            return self.rows_by_op.get("promote")
        if "select d.id, d.original_filename" in normalized:
            return self.rows_by_op.get("detail")
        if "select file_path, original_filename, mime_type from documents" in normalized:
            return self.rows_by_op.get("file_business")
        if "select d.file_path, d.original_filename, d.mime_type" in normalized:
            return self.rows_by_op.get("file_provider")
        if "select file_path, original_filename, doc_type, status" in normalized:
            return self.rows_by_op.get("evaluate")
        if "select id, file_path from documents" in normalized:
            return self.rows_by_op.get("delete")
        return self.rows_by_op.get("default_fetchrow")

    async def fetch(self, sql: str, *args):
        self.fetch_calls.append((sql, args))
        return self.rows_by_op.get("list_rows", [])

    async def execute(self, sql: str, *args):
        self.execute_calls.append((sql, args))
        return "OK"


def business_user(tenant_id):
    return {"role": "business", "sub": str(uuid4()), "tenant_id": str(tenant_id), "email": "biz@example.test"}


def provider_user():
    return {"role": "provider", "sub": str(uuid4()), "email": "provider@example.test"}


async def _noop_permission(user, permission):
    return None


async def _feature_off(db, tenant_id, flag):
    return False


def _canonical_tenant(tenant_id):
    async def _resolve(user, db_arg):
        return tenant_id

    return _resolve


def _detail_row(doc_id, tenant_id):
    now = datetime.now(timezone.utc)
    return {
        "id": doc_id,
        "original_filename": "tenant-owned.pdf",
        "doc_type": "halal_policy",
        "compliance_score": None,
        "file_size": 12,
        "mime_type": "application/pdf",
        "uploaded_at": now,
        "evaluation_result": {"overall_status": "uploaded", "summary": "ok"},
        "approval_status": None,
        "version_number": None,
        "version_parent_id": None,
        "approver_id": None,
        "approved_at": None,
        "effective_date": None,
        "next_review_date": None,
        "retention_period_days": None,
        "retention_expires_at": None,
        "superseded_by_id": None,
        "uploaded_by_name": "Tenant Owner",
        "tenant_id": tenant_id,
    }


def _file_row(path: Path):
    return {"file_path": str(path), "original_filename": path.name, "mime_type": "application/pdf"}


async def test_business_list_uses_only_canonical_tenant_scope(monkeypatch):
    tenant_a = uuid4()
    keycloak_claim_tenant = uuid4()
    db = BoundaryDb()
    monkeypatch.setattr(document_router, "resolve_canonical_tenant_id", _canonical_tenant(tenant_a))
    monkeypatch.setattr(document_router, "is_feature_enabled", _feature_off)

    result = await document_router.list_documents(page=1, page_size=20, user=business_user(keycloak_claim_tenant), db=db)

    assert result.total == 0
    all_calls = db.fetchrow_calls + db.fetch_calls
    assert all_calls, "list must query through tenant-scoped SQL"
    assert all(args[0] == tenant_a for _sql, args in all_calls)
    assert all(args[0] != keycloak_claim_tenant for _sql, args in all_calls)
    assert all("tenant_id = $1" in sql for sql, _args in all_calls)


async def test_business_detail_returns_404_for_cross_tenant_document(monkeypatch):
    tenant_a = uuid4()
    db = BoundaryDb(rows_by_op={"detail": None})
    doc_id = str(uuid4())
    monkeypatch.setattr(document_router, "resolve_canonical_tenant_id", _canonical_tenant(tenant_a))

    with pytest.raises(HTTPException) as excinfo:
        await document_router.get_document(doc_id, user=business_user(tenant_a), db=db)

    assert excinfo.value.status_code == 404
    sql, args = db.fetchrow_calls[-1]
    assert "WHERE d.id = $1 AND d.tenant_id = $2" in sql
    assert args == (doc_id, tenant_a)


async def test_business_detail_returns_owned_document_when_tenant_matches(monkeypatch):
    tenant_a = uuid4()
    doc_id = uuid4()
    db = BoundaryDb(rows_by_op={"detail": _detail_row(doc_id, tenant_a)})
    monkeypatch.setattr(document_router, "resolve_canonical_tenant_id", _canonical_tenant(tenant_a))
    monkeypatch.setattr(document_router, "is_feature_enabled", _feature_off)

    result = await document_router.get_document(str(doc_id), user=business_user(tenant_a), db=db)

    assert result.id == str(doc_id)
    assert result.original_filename == "tenant-owned.pdf"


@pytest.mark.parametrize("handler", [document_router.get_document_file, document_router.preview_document])
async def test_business_file_and_preview_return_404_for_cross_tenant_doc(monkeypatch, handler):
    tenant_a = uuid4()
    doc_id = str(uuid4())
    db = BoundaryDb(rows_by_op={"file_business": None})

    async def fake_user(request, token):
        return business_user(tenant_a)

    monkeypatch.setattr(document_router, "_get_user_from_header_or_query", fake_user)

    with pytest.raises(HTTPException) as excinfo:
        await handler(doc_id, request=object(), token=None, db=db)

    assert excinfo.value.status_code == 404
    sql, args = db.fetchrow_calls[-1]
    assert "WHERE id = $1 AND tenant_id = $2" in sql
    assert args == (doc_id, str(tenant_a))


@pytest.mark.parametrize("handler", [document_router.get_document_file, document_router.preview_document])
async def test_provider_file_and_preview_only_allow_submission_bound_documents(monkeypatch, tmp_path, handler):
    provider_id = uuid4()
    doc_id = str(uuid4())
    owned_file = tmp_path / "submission-bound.pdf"
    owned_file.write_bytes(b"%PDF-1.4\n")
    db = BoundaryDb(rows_by_op={"file_provider": _file_row(owned_file)})

    async def fake_user(request, token):
        return provider_user()

    async def fake_resolve_user(user, db_arg):
        return provider_id

    monkeypatch.setattr(document_router, "_get_user_from_header_or_query", fake_user)
    monkeypatch.setattr(document_router, "resolve_canonical_user_id", fake_resolve_user)

    result = await handler(doc_id, request=object(), token=None, db=db)

    assert str(owned_file) in str(result.path)
    sql, args = db.fetchrow_calls[-1]
    assert "EXISTS" in sql
    assert "s.provider_id = $2 OR s.auditor_id = $2" in sql
    assert "$1 = ANY(s.document_ids)" in sql
    assert args == (doc_id, provider_id)


@pytest.mark.parametrize("handler", [document_router.get_document_file, document_router.preview_document])
async def test_provider_file_and_preview_return_404_for_unbound_documents(monkeypatch, handler):
    provider_id = uuid4()
    doc_id = str(uuid4())
    db = BoundaryDb(rows_by_op={"file_provider": None})

    async def fake_user(request, token):
        return provider_user()

    async def fake_resolve_user(user, db_arg):
        return provider_id

    monkeypatch.setattr(document_router, "_get_user_from_header_or_query", fake_user)
    monkeypatch.setattr(document_router, "resolve_canonical_user_id", fake_resolve_user)

    with pytest.raises(HTTPException) as excinfo:
        await handler(doc_id, request=object(), token=None, db=db)

    assert excinfo.value.status_code == 404


async def test_evaluate_rejects_cross_tenant_document_without_mutating(monkeypatch):
    tenant_a = uuid4()
    db = BoundaryDb(rows_by_op={"evaluate": None})
    doc_id = str(uuid4())
    monkeypatch.setattr(document_router, "resolve_canonical_tenant_id", _canonical_tenant(tenant_a))

    with pytest.raises(HTTPException) as excinfo:
        await document_router.evaluate_existing_document(doc_id, user=business_user(tenant_a), db=db)

    assert excinfo.value.status_code == 404
    assert db.execute_calls == []
    sql, args = db.fetchrow_calls[-1]
    assert "WHERE id = $1 AND tenant_id = $2" in sql
    assert args == (doc_id, tenant_a)


async def test_promote_rejects_cross_tenant_document_without_mutating(monkeypatch):
    tenant_a = uuid4()
    db = BoundaryDb(rows_by_op={"promote": None})
    doc_id = str(uuid4())
    monkeypatch.setattr(document_router, "resolve_canonical_tenant_id", _canonical_tenant(tenant_a))

    with pytest.raises(HTTPException) as excinfo:
        await document_router.promote_document(doc_id, user=business_user(tenant_a), db=db)

    assert excinfo.value.status_code == 404
    assert db.execute_calls == []
    sql, args = db.fetchrow_calls[-1]
    assert "WHERE id = $1 AND tenant_id = $2" in sql
    assert args == (doc_id, tenant_a)


async def test_delete_rejects_cross_tenant_document_without_file_or_db_mutation(monkeypatch):
    tenant_a = uuid4()
    db = BoundaryDb(rows_by_op={"delete": None})
    doc_id = str(uuid4())
    monkeypatch.setattr(document_router, "resolve_canonical_tenant_id", _canonical_tenant(tenant_a))
    monkeypatch.setattr(document_router, "check_permission_db", _noop_permission)

    with pytest.raises(HTTPException) as excinfo:
        await document_router.delete_document(doc_id, user=business_user(tenant_a), db=db)

    assert excinfo.value.status_code == 404
    assert db.execute_calls == []
    sql, args = db.fetchrow_calls[-1]
    assert "WHERE id = $1 AND tenant_id = $2" in sql
    assert args == (doc_id, tenant_a)


async def test_delete_refuses_to_unlink_document_file_outside_upload_root(monkeypatch, tmp_path):
    tenant_a = uuid4()
    doc_id = str(uuid4())
    outside_file = tmp_path / "outside-storage.pdf"
    outside_file.write_bytes(b"must-not-delete")
    upload_root = tmp_path / "upload-root"
    upload_root.mkdir()
    db = BoundaryDb(rows_by_op={"delete": {"id": doc_id, "file_path": str(outside_file)}})
    monkeypatch.setattr(document_router, "UPLOAD_DIR", upload_root)
    monkeypatch.setattr(document_router, "resolve_canonical_tenant_id", _canonical_tenant(tenant_a))
    monkeypatch.setattr(document_router, "check_permission_db", _noop_permission)

    with pytest.raises(HTTPException) as excinfo:
        await document_router.delete_document(doc_id, user=business_user(tenant_a), db=db)

    assert excinfo.value.status_code == 500
    assert outside_file.exists(), "delete must not unlink paths outside configured upload root"
    assert db.execute_calls == [], "metadata row must remain when file cleanup is unsafe"
