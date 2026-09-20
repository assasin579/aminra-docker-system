from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException

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


@pytest.mark.asyncio
async def test_selective_reference_cleanup_requires_deleted_keycloak_projection():
    from app import _cleanup_selected_user_references

    db = FakeConn()
    user_id = str(uuid4())

    with pytest.raises(HTTPException) as exc:
        await _cleanup_selected_user_references(
            db,
            user_id,
            identity_status="linked",
            selected_references=["notifications"],
        )

    assert exc.value.status_code == 409
    assert "missing_in_keycloak" in str(exc.value.detail)
    assert not any(kind == "execute" for kind, _ in db.calls)


@pytest.mark.asyncio
async def test_selective_reference_cleanup_deletes_only_checked_ephemeral_references():
    from app import _cleanup_selected_user_references

    db = FakeConn()
    user_id = str(uuid4())

    result = await _cleanup_selected_user_references(
        db,
        user_id,
        identity_status="missing_in_keycloak",
        selected_references=["notifications"],
    )

    assert result["selected_references"] == ["notifications"]
    assert result["users_projection_deleted"] is False
    assert result["documents_db_rows_deleted"] is False
    assert result["cleanup"]["notifications"]["action"] == "delete_rows"

    executed_sql = "\n".join(sql for kind, (sql, _args) in db.calls if kind == "execute")
    assert "DELETE FROM notifications WHERE user_id = $1" in executed_sql
    assert "DELETE FROM push_subscriptions" not in executed_sql
    assert "DELETE FROM users" not in executed_sql


@pytest.mark.asyncio
async def test_deletion_case_policy_keeps_audit_logs_and_detaches_nullable_actor_refs():
    from app import _build_account_deletion_case_items

    items = _build_account_deletion_case_items(
        {
            "audit_logs": 2,
            "documents_approved": 1,
            "notifications": 3,
            "tenant_members": 1,
        },
        identity_status="missing_in_keycloak",
    )

    by_key = {item["reference_key"]: item for item in items}
    assert by_key["notifications"]["action"] == "hard_delete"
    assert by_key["documents_approved"]["action"] == "detach_user_reference"
    assert by_key["documents_approved"]["risk_level"] == "medium"
    assert by_key["audit_logs"]["action"] == "retain_append_only_audit"
    assert by_key["audit_logs"]["status"] == "skipped"
    assert by_key["tenant_members"]["action"] == "blocked"
    assert by_key["tenant_members"]["risk_level"] == "blocker"


@pytest.mark.asyncio
async def test_execute_deletion_case_detaches_safe_refs_and_marks_projection_cleaned():
    from app import _execute_account_deletion_case_items

    db = FakeConn()
    user_id = str(uuid4())
    case_id = str(uuid4())
    items = [
        {
            "reference_key": "documents_approved",
            "table_name": "documents",
            "column_name": "approver_id",
            "record_count": 1,
            "action": "detach_user_reference",
            "status": "pending",
        },
        {
            "reference_key": "audit_logs",
            "table_name": "audit_logs",
            "column_name": "user_id",
            "record_count": 2,
            "action": "retain_append_only_audit",
            "status": "skipped",
        },
    ]

    result = await _execute_account_deletion_case_items(
        db,
        user_id,
        case_id=case_id,
        identity_status="missing_in_keycloak",
        items=items,
    )

    assert result["case_status"] == "completed"
    assert result["completed_items"] == 1
    assert result["skipped_items"] == 1
    executed_sql = "\n".join(sql for kind, (sql, _args) in db.calls if kind == "execute")
    assert "UPDATE documents SET approver_id = NULL WHERE approver_id = $1" in executed_sql
    assert "UPDATE audit_logs" not in executed_sql, "append-only audit logs must not be mutated"
    assert "UPDATE users" in executed_sql
    assert "account_cleanup_status = 'cleaned'" in executed_sql


def test_account_deletion_case_routes_and_migration_contract_exist():
    app_src = Path("app.py").read_text()
    assert '@app.post("/admin/users/{user_id}/deletion-case")' in app_src
    assert '@app.get("/admin/account-deletion-cases/{case_id}")' in app_src
    assert '@app.post("/admin/account-deletion-cases/{case_id}/run")' in app_src
    assert "DELETE FROM users" not in app_src[app_src.index('deletion-case') : app_src.index('@app.post("/admin/users")')]

    migration_src = Path("alembic/versions/043_account_deletion_cases.py").read_text()
    assert "CREATE TABLE IF NOT EXISTS account_deletion_cases" in migration_src
    assert "CREATE TABLE IF NOT EXISTS account_deletion_case_items" in migration_src
    assert "account_cleanup_status" in migration_src
    assert "status = $2::varchar" in app_src
    assert "CASE WHEN $2::varchar IN" in app_src
    run_route = app_src[app_src.index('async def admin_run_account_deletion_case') : app_src.index('@app.get("/admin/account-deletion-cases/{case_id}")')]
    assert '"items": updated_items' in run_route
    assert "account_deletion_case_items" in run_route
