from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from auth.audit_router import _execute_mobile_replay_operation
from auth.offline_replay_idempotency import build_operation_scope

pytestmark = pytest.mark.asyncio


async def _require_replay_table(db_tx) -> None:
    table_exists = await db_tx.fetchval(
        """
        SELECT EXISTS (
          SELECT 1
          FROM information_schema.tables
          WHERE table_schema = 'public'
            AND table_name = 'mobile_offline_replay_operations'
        )
        """
    )
    if not table_exists:
        pytest.skip("mobile_offline_replay_operations table is not migrated in this DB")


async def test_db_backed_replay_executor_returns_stored_response_for_same_audit_route_replay(db_tx) -> None:
    """A same-scope/same-hash mobile audit route replay must not run mutation twice."""
    await _require_replay_table(db_tx)
    calls = 0
    tenant_id = uuid4()
    visit_id = uuid4()
    scope = build_operation_scope(
        tenant_id=tenant_id,
        user_id=None,
        visit_id=visit_id,
        operation_type="ncr_create",
        route_key="POST /api/audits/{vid}/ncr",
        resource_key=f"visit:{visit_id}:ncr:client-draft-1",
        idempotency_key="offline-route-replay-key-1",
    )

    async def mutate() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"id": "server-ncr-1", "message": "Đã tạo NCR"}

    first = await _execute_mobile_replay_operation(
        db=db_tx,
        scope=scope,
        request_hash="a" * 64,
        mutate=mutate,
    )
    second = await _execute_mobile_replay_operation(
        db=db_tx,
        scope=scope,
        request_hash="a" * 64,
        mutate=mutate,
    )

    assert first == {"id": "server-ncr-1", "message": "Đã tạo NCR"}
    assert second == first
    assert calls == 1
    persisted_count = await db_tx.fetchval(
        """
        SELECT COUNT(*)
        FROM mobile_offline_replay_operations
        WHERE tenant_id=$1 AND operation_type=$2 AND route_key=$3 AND resource_key=$4 AND idempotency_key=$5
        """,
        tenant_id,
        scope["operation_type"],
        scope["route_key"],
        scope["resource_key"],
        scope["idempotency_key"],
    )
    assert persisted_count == 1


async def test_db_backed_replay_executor_conflicts_when_same_route_key_reuses_idempotency_with_different_hash(db_tx) -> None:
    """A reused idempotency key with a different audit route payload is a 409, not a duplicate mutation."""
    await _require_replay_table(db_tx)
    calls = 0
    tenant_id = uuid4()
    visit_id = uuid4()
    scope = build_operation_scope(
        tenant_id=tenant_id,
        user_id=None,
        visit_id=visit_id,
        operation_type="evidence_photo_upload:item_photo",
        route_key="POST /api/audits/{vid}/items/{item_id}/photo",
        resource_key=f"item:{uuid4()}",
        idempotency_key="offline-route-replay-key-2",
    )

    async def mutate() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"message": "Đã upload ảnh", "path": "docs/audit/photo.jpg"}

    await _execute_mobile_replay_operation(
        db=db_tx,
        scope=scope,
        request_hash="b" * 64,
        mutate=mutate,
    )

    with pytest.raises(HTTPException) as exc_info:
        await _execute_mobile_replay_operation(
            db=db_tx,
            scope=scope,
            request_hash="c" * 64,
            mutate=mutate,
        )

    assert calls == 1
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"] == "idempotency_key_conflict"
