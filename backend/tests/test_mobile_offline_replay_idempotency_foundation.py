from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from auth.offline_replay_idempotency import (
    DuplicateReplayClassification,
    ExistingReplayRecord,
    build_operation_scope,
    classify_duplicate_replay,
    extract_required_idempotency_key,
    stable_request_hash,
)


_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "052_mobile_offline_replay_idempotency.py"
)


def test_migration_creates_mobile_offline_replay_operations_contract() -> None:
    text = _MIGRATION_PATH.read_text()

    assert 'revision = "052_mobile_replay_idem"' in text
    assert 'down_revision = "051_official_artifacts"' in text
    assert "CREATE TABLE IF NOT EXISTS mobile_offline_replay_operations" in text
    assert "id UUID PRIMARY KEY DEFAULT gen_random_uuid()" in text
    assert "tenant_id UUID NOT NULL" in text
    assert "user_id UUID" in text
    assert "visit_id UUID" in text
    assert "operation_type TEXT NOT NULL" in text
    assert "route_key TEXT NOT NULL" in text
    assert "resource_key TEXT NOT NULL" in text
    assert "idempotency_key TEXT NOT NULL" in text
    assert "request_hash TEXT NOT NULL" in text
    assert "response_status INTEGER NOT NULL" in text
    assert "response_body JSONB NOT NULL" in text
    assert "conflict_reason TEXT" in text
    assert "created_at TIMESTAMPTZ NOT NULL DEFAULT now()" in text
    assert "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()" in text
    assert "uq_mobile_offline_replay_scope_key" in text
    assert "tenant_id, operation_type, route_key, resource_key, idempotency_key" in text
    assert "DROP INDEX IF EXISTS uq_mobile_offline_replay_scope_key" in text
    assert "DROP TABLE IF EXISTS mobile_offline_replay_operations" in text


def test_extract_required_idempotency_key_precedence_and_no_silent_default() -> None:
    assert (
        extract_required_idempotency_key(
            headers={"Idempotency-Key": " header-key "},
            body={"idempotency_key": "body-key"},
            payload={"client_operation_id": "payload-key"},
        )
        == "header-key"
    )
    assert (
        extract_required_idempotency_key(
            headers={},
            body={"client_operation_id": "body-client-op"},
            payload={"idempotency_key": "payload-key"},
        )
        == "body-client-op"
    )
    assert (
        extract_required_idempotency_key(
            headers={},
            body={},
            payload={"idempotency_key": "payload-key"},
        )
        == "payload-key"
    )

    with pytest.raises(ValueError, match="Idempotency-Key"):
        extract_required_idempotency_key(headers={}, body={}, payload={})

    with pytest.raises(ValueError, match="Idempotency-Key"):
        extract_required_idempotency_key(headers={"Idempotency-Key": "   "}, body={}, payload={})


def test_build_operation_scope_contains_route_resource_identity_and_actor_ids() -> None:
    tenant_id = uuid4()
    user_id = uuid4()
    visit_id = uuid4()

    scope = build_operation_scope(
        tenant_id=tenant_id,
        user_id=user_id,
        visit_id=visit_id,
        operation_type="append",
        route_key="/api/audits/{visit_id}/findings",
        resource_key="finding:draft-7",
        idempotency_key="idem-123",
    )

    assert scope == {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "visit_id": str(visit_id),
        "operation_type": "append",
        "route_key": "/api/audits/{visit_id}/findings",
        "resource_key": "finding:draft-7",
        "idempotency_key": "idem-123",
    }


def test_stable_request_hash_is_deterministic_and_excludes_raw_secrets() -> None:
    payload_a = {
        "z": [3, 2, 1],
        "nested": {"b": True, "a": None},
        "authorization": "Bearer super-secret-token",
        "access_token": "raw-access-token",
        "client_secret": "raw-client-secret",
    }
    payload_b = {
        "client_secret": "different-secret-is-still-ignored",
        "access_token": "different-token-is-still-ignored",
        "authorization": "Bearer different-auth-is-still-ignored",
        "nested": {"a": None, "b": True},
        "z": [3, 2, 1],
    }
    scope = build_operation_scope(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        user_id=None,
        visit_id=UUID("00000000-0000-0000-0000-000000000002"),
        operation_type="create",
        route_key="/api/audits/offline/create",
        resource_key="visit:client-abc",
        idempotency_key="idem-abc",
    )

    digest_a = stable_request_hash(payload=payload_a, resource_identity=scope)
    digest_b = stable_request_hash(payload=payload_b, resource_identity=dict(reversed(scope.items())))

    assert digest_a == digest_b
    assert len(digest_a) == 64
    assert "super-secret-token" not in digest_a
    assert "raw-access-token" not in digest_a
    assert "raw-client-secret" not in digest_a


def test_classify_duplicate_replay_same_hash_success_different_hash_conflict() -> None:
    existing = ExistingReplayRecord(
        request_hash="a" * 64,
        response_status=201,
        response_body={"id": "visit-123", "status": "created"},
    )

    same = classify_duplicate_replay(existing=existing, incoming_request_hash="a" * 64)
    assert same == DuplicateReplayClassification(
        outcome="stable_success",
        response_status=201,
        response_body={"id": "visit-123", "status": "created"},
        conflict_reason=None,
    )

    different = classify_duplicate_replay(existing=existing, incoming_request_hash="b" * 64)
    assert different.outcome == "conflict_409"
    assert different.response_status == 409
    assert different.response_body["error"] == "idempotency_key_conflict"
    assert different.conflict_reason == "request_hash_mismatch"
