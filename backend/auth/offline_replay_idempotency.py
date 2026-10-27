from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Literal
from uuid import UUID

SensitiveJSON = dict[str, Any] | list[Any] | str | int | float | bool | None

_IDEMPOTENCY_HEADER = "idempotency-key"
_IDEMPOTENCY_BODY_KEYS = ("idempotency_key", "client_operation_id")
_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "authorization",
        "client_secret",
        "id_token",
        "password",
        "refresh_token",
        "secret",
        "token",
    }
)


@dataclass(frozen=True)
class ExistingReplayRecord:
    request_hash: str
    response_status: int
    response_body: dict[str, Any]


@dataclass(frozen=True)
class DuplicateReplayClassification:
    outcome: Literal["stable_success", "conflict_409"]
    response_status: int
    response_body: dict[str, Any]
    conflict_reason: str | None


def extract_required_idempotency_key(
    *,
    headers: Mapping[str, Any] | None,
    body: Mapping[str, Any] | None,
    payload: Mapping[str, Any] | None,
) -> str:
    """Return an explicit mobile replay idempotency key or raise.

    Precedence is HTTP Idempotency-Key header, then body idempotency fields,
    then replay payload idempotency fields. Create/append operations must not
    fabricate a default key because that would make duplicate side effects
    indistinguishable from distinct client operations.
    """

    header_value = _get_case_insensitive(headers or {}, _IDEMPOTENCY_HEADER)
    key = _first_non_blank(header_value)
    if key is not None:
        return key

    key = _first_mapping_value(body or {}, _IDEMPOTENCY_BODY_KEYS)
    if key is not None:
        return key

    key = _first_mapping_value(payload or {}, _IDEMPOTENCY_BODY_KEYS)
    if key is not None:
        return key

    raise ValueError("Idempotency-Key header or client_operation_id/idempotency_key is required")


def build_operation_scope(
    *,
    tenant_id: UUID | str,
    user_id: UUID | str | None,
    visit_id: UUID | str | None,
    operation_type: str,
    route_key: str,
    resource_key: str,
    idempotency_key: str,
) -> dict[str, str | None]:
    """Build the immutable scope used by persistence and request hashing."""

    values = {
        "tenant_id": _required_text(tenant_id, "tenant_id"),
        "user_id": _optional_text(user_id),
        "visit_id": _optional_text(visit_id),
        "operation_type": _required_text(operation_type, "operation_type"),
        "route_key": _required_text(route_key, "route_key"),
        "resource_key": _required_text(resource_key, "resource_key"),
        "idempotency_key": _required_text(idempotency_key, "idempotency_key"),
    }
    return values


def stable_request_hash(*, payload: Mapping[str, Any], resource_identity: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 for replay comparison.

    JSON keys are sorted and compacted. Known token/secret fields are removed
    recursively before hashing so raw credentials cannot become hash material.
    """

    canonical = {
        "payload": _redact_sensitive(payload),
        "resource_identity": _redact_sensitive(resource_identity),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(encoded.encode("utf-8")).hexdigest()


def classify_duplicate_replay(
    *,
    existing: ExistingReplayRecord,
    incoming_request_hash: str,
) -> DuplicateReplayClassification:
    if existing.request_hash == incoming_request_hash:
        return DuplicateReplayClassification(
            outcome="stable_success",
            response_status=existing.response_status,
            response_body=existing.response_body,
            conflict_reason=None,
        )

    return DuplicateReplayClassification(
        outcome="conflict_409",
        response_status=409,
        response_body={
            "error": "idempotency_key_conflict",
            "message": "Idempotency key was already used with a different request payload or resource identity.",
        },
        conflict_reason="request_hash_mismatch",
    )


def _get_case_insensitive(mapping: Mapping[str, Any], wanted_lower: str) -> Any:
    for key, value in mapping.items():
        if str(key).lower() == wanted_lower:
            return value
    return None


def _first_mapping_value(mapping: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _first_non_blank(mapping.get(key))
        if value is not None:
            return value
    return None


def _first_non_blank(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_text(value: UUID | str, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _optional_text(value: UUID | str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _redact_sensitive(value: Any) -> SensitiveJSON:
    if isinstance(value, Mapping):
        redacted: dict[str, SensitiveJSON] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in _SENSITIVE_KEYS:
                continue
            redacted[key_text] = _redact_sensitive(item)
        return redacted
    if isinstance(value, list | tuple):
        return [_redact_sensitive(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)
