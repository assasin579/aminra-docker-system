from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile

from auth import document_router

pytestmark = pytest.mark.asyncio


class RecordingDb:
    def __init__(self, *, fail_insert: bool = False):
        self.fail_insert = fail_insert
        self.fetchrow_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetchrow(self, sql: str, *args):
        self.fetchrow_calls.append((sql, args))
        if self.fail_insert:
            raise RuntimeError("synthetic insert failure")
        return {"id": uuid4(), "uploaded_at": "2026-09-25T00:00:00Z"}


def _upload_file(filename: str = "halal-policy.pdf") -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(b"%PDF-1.4\nminimal\n"))


async def test_document_upload_persists_canonical_aminra_user_id(monkeypatch, tmp_path):
    canonical_user_id = uuid4()
    canonical_tenant_id = uuid4()
    keycloak_sub = uuid4()
    db = RecordingDb()

    monkeypatch.setattr(document_router, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(document_router, "validate_upload", lambda file: file.read())
    async def fake_check_permission(user, permission):
        return None

    monkeypatch.setattr(document_router, "check_permission_db", fake_check_permission)

    async def fake_resolve_user(user, db_arg):
        assert user["sub"] == str(keycloak_sub)
        return canonical_user_id

    async def fake_resolve_tenant(user, db_arg):
        return canonical_tenant_id

    monkeypatch.setattr(document_router, "resolve_canonical_user_id", fake_resolve_user)
    monkeypatch.setattr(document_router, "resolve_canonical_tenant_id", fake_resolve_tenant)

    result = await document_router.upload_document(
        file=_upload_file(),
        doc_type="halal_policy",
        user={"role": "business", "sub": str(keycloak_sub)},
        db=db,
    )

    assert result["filename"] == "halal-policy.pdf"
    assert db.fetchrow_calls, "upload must insert a documents row"
    _, args = db.fetchrow_calls[0]
    assert args[5] == canonical_user_id
    assert args[5] != keycloak_sub
    assert args[6] == canonical_tenant_id


async def test_document_upload_cleans_saved_file_when_db_insert_fails(monkeypatch, tmp_path):
    canonical_user_id = uuid4()
    canonical_tenant_id = uuid4()
    db = RecordingDb(fail_insert=True)

    monkeypatch.setattr(document_router, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(document_router, "validate_upload", lambda file: file.read())
    async def fake_check_permission(user, permission):
        return None

    monkeypatch.setattr(document_router, "check_permission_db", fake_check_permission)
    async def fake_resolve_user(user, db_arg):
        return canonical_user_id

    async def fake_resolve_tenant(user, db_arg):
        return canonical_tenant_id

    monkeypatch.setattr(document_router, "resolve_canonical_user_id", fake_resolve_user)
    monkeypatch.setattr(document_router, "resolve_canonical_tenant_id", fake_resolve_tenant)

    with pytest.raises(HTTPException) as excinfo:
        await document_router.upload_document(
            file=_upload_file("cleanup-check.pdf"),
            doc_type="halal_policy",
            user={"role": "business", "sub": str(uuid4())},
            db=db,
        )

    assert excinfo.value.status_code == 500
    tenant_dir = tmp_path / str(canonical_tenant_id)
    assert list(tenant_dir.glob("*cleanup-check.pdf")) == []
