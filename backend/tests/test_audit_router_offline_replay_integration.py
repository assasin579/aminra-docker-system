from __future__ import annotations

import re
from pathlib import Path

AUDIT_ROUTER = Path("auth/audit_router.py")
SOURCE = AUDIT_ROUTER.read_text()


def _function_body(function_name: str) -> str:
    marker = f"async def {function_name}"
    assert marker in SOURCE, f"Missing {function_name}"
    start = SOURCE.index(marker)
    next_route = SOURCE.find("\n@router.", start + len(marker))
    if next_route == -1:
        next_route = len(SOURCE)
    return SOURCE[start:next_route]


def test_photo_append_routes_use_shared_replay_guard_before_filesystem_and_db_mutation() -> None:
    for function_name, operation_type, resource_prefix in (
        ("upload_item_photo", "evidence_photo_upload:item_photo", "item:"),
        ("upload_ncr_photo", "evidence_photo_upload:ncr_photo", "ncr:"),
    ):
        body = _function_body(function_name)
        assert "request: Request" in body
        assert "assert_audit_visit_mutation_scope" in body
        assert "extract_required_idempotency_key" in body
        assert operation_type in body
        assert resource_prefix in body
        assert "Form(None)" in body
        assert "client_operation_id" in body
        assert "_safe_upload_filename" in body
        assert "SELECT id FROM" in body
        assert "not found for audit visit" in body
        assert "stable_request_hash" in body
        assert "_execute_mobile_replay_operation" in body

        guard_pos = body.index("assert_audit_visit_mutation_scope")
        key_pos = body.index("extract_required_idempotency_key")
        hash_pos = body.index("stable_request_hash")
        mutate_pos = body.index("async def mutate")
        execute_pos = body.rindex("_execute_mobile_replay_operation")
        write_pos = body.index("write_bytes")
        update_pos = body.index("UPDATE")
        assert guard_pos < mutate_pos < write_pos
        assert key_pos < mutate_pos < write_pos
        assert hash_pos < mutate_pos < write_pos
        assert execute_pos > write_pos
        assert execute_pos > update_pos


def test_create_ncr_uses_shared_replay_guard_before_insert() -> None:
    body = _function_body("create_ncr")
    assert "request: Request" in body
    assert "assert_audit_visit_mutation_scope" in body
    assert "extract_required_idempotency_key" in body
    assert "ncr_create" in body
    assert "resource_key=f\"visit:{vid}:ncr" in body
    assert "stable_request_hash" in body
    assert "_execute_mobile_replay_operation" in body

    guard_pos = body.index("assert_audit_visit_mutation_scope")
    key_pos = body.index("extract_required_idempotency_key")
    hash_pos = body.index("stable_request_hash")
    mutate_pos = body.index("async def mutate")
    execute_pos = body.rindex("_execute_mobile_replay_operation")
    insert_pos = body.index("INSERT INTO audit_ncr")
    assert guard_pos < mutate_pos < insert_pos
    assert key_pos < mutate_pos < insert_pos
    assert hash_pos < mutate_pos < insert_pos
    assert execute_pos > insert_pos


def test_shared_replay_executor_reserves_unique_scope_and_conflicts_on_hash_mismatch() -> None:
    body = _function_body("_execute_mobile_replay_operation")
    assert "async with db.transaction()" in body
    assert "INSERT INTO mobile_offline_replay_operations" in body
    assert "ON CONFLICT" in body
    assert "uq_mobile_offline_replay_scope_key" in body or "DO NOTHING" in body
    assert "classify_duplicate_replay" in body
    assert "ExistingReplayRecord" in body
    assert re.search(r"HTTPException\(\s*409", body)
    assert "UPDATE mobile_offline_replay_operations" in body
    assert "response_status" in body
    assert "response_body" in body
