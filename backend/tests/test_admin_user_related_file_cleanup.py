from pathlib import Path
from uuid import uuid4

import pytest

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


@pytest.mark.asyncio
async def test_cleanup_uploaded_document_files_deletes_only_files_under_upload_root(tmp_path: Path):
    from app import _cleanup_user_uploaded_document_files

    upload_root = tmp_path / "uploads"
    tenant_dir = upload_root / "tenant-1"
    tenant_dir.mkdir(parents=True)
    owned_file = tenant_dir / "doc.pdf"
    owned_file.write_bytes(b"owned")
    outside_file = tmp_path / "outside.pdf"
    outside_file.write_bytes(b"outside")

    owned_doc_id = uuid4()
    outside_doc_id = uuid4()
    missing_doc_id = uuid4()
    db = FakeConn()
    db.fetch_responses = [
        (
            "FROM documents WHERE user_id = $1 AND file_path IS NOT NULL",
            [
                FakeRecord(id=owned_doc_id, file_path=str(owned_file)),
                FakeRecord(id=outside_doc_id, file_path=str(outside_file)),
                FakeRecord(id=missing_doc_id, file_path=str(tenant_dir / "missing.pdf")),
            ],
        )
    ]

    result = await _cleanup_user_uploaded_document_files(db, str(uuid4()), upload_root=upload_root)

    assert result["deleted_files"] == 1
    assert result["skipped_files"] == 1
    assert result["missing_files"] == 1
    assert result["cleared_document_rows"] == 1
    assert not owned_file.exists()
    assert outside_file.exists(), "cleanup must not delete paths outside UPLOAD_DIR"

    updates = [args for kind, (sql, args) in db.calls if kind == "execute" and "UPDATE documents" in sql]
    assert len(updates) == 1
    assert updates[0][0] == [owned_doc_id]


def test_admin_related_file_cleanup_route_is_admin_only_and_does_not_delete_users():
    src = Path("app.py").read_text()
    assert '@app.post("/admin/users/{user_id}/related-files/cleanup")' in src
    start = src.index("async def admin_cleanup_user_related_files")
    end = src.find("\n\n@app.", start + 1)
    body = src[start:end if end != -1 else len(src)]

    guard_pos = body.index("_require_admin(request)")
    cleanup_pos = body.index("_cleanup_user_uploaded_document_files")
    assert guard_pos < cleanup_pos
    assert "DELETE FROM users" not in body
    assert "keycloak_admin." not in body
