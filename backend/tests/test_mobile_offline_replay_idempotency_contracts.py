"""Source contracts for mobile offline replay idempotency.

These tests intentionally inspect the onsite audit router source instead of driving a
live DB. The mobile auditor app may replay queued operations after reconnect; every
mutable replay endpoint must therefore have an explicit idempotency/dedupe contract
(or be a proven set/overwrite operation) while preserving tenant/user scoping.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


AUDIT_ROUTER = Path("auth/audit_router.py")
SOURCE = AUDIT_ROUTER.read_text()


@dataclass(frozen=True)
class ReplayOperation:
    op_type: str
    route: str
    method: str
    function_name: str
    action: str
    idempotency_kind: str


REPLAY_OPERATIONS = (
    ReplayOperation(
        op_type="checklist_item_update",
        route='/{vid}/items/{item_id}',
        method="put",
        function_name="update_item",
        action="Set checklist result/note/evidence/corrective fields for one existing item",
        idempotency_kind="set_update",
    ),
    ReplayOperation(
        op_type="evidence_photo_upload:item_photo",
        route='/{vid}/items/{item_id}/photo',
        method="post",
        function_name="upload_item_photo",
        action="Attach an evidence photo to one checklist item",
        idempotency_kind="create_or_append",
    ),
    ReplayOperation(
        op_type="evidence_photo_upload:ncr_photo",
        route='/{vid}/ncr/{ncr_id}/photo',
        method="post",
        function_name="upload_ncr_photo",
        action="Attach a photo to one NCR",
        idempotency_kind="create_or_append",
    ),
    ReplayOperation(
        op_type="ncr_create",
        route='/{vid}/ncr',
        method="post",
        function_name="create_ncr",
        action="Create one non-conformance record for a visit/item",
        idempotency_kind="create_or_append",
    ),
    ReplayOperation(
        op_type="ncr_update",
        route='/{vid}/ncr/{ncr_id}',
        method="put",
        function_name="update_ncr",
        action="Set NCR description/severity/corrective/status/deadline fields",
        idempotency_kind="set_update",
    ),
    ReplayOperation(
        op_type="signature_upload",
        route='/{vid}/signature',
        method="post",
        function_name="upload_signature",
        action="Store auditor/business signature for a visit",
        idempotency_kind="deterministic_overwrite",
    ),
    ReplayOperation(
        op_type="visit_submit:status",
        route='/{vid}/status',
        method="put",
        function_name="update_visit_status",
        action="Set visit status to completed/report_submitted during mobile submit",
        idempotency_kind="set_update",
    ),
    ReplayOperation(
        op_type="visit_submit:report",
        route='/{vid}/generate-report',
        method="post",
        function_name="generate_report",
        action="Generate/overwrite final onsite audit report and mark submitted",
        idempotency_kind="deterministic_overwrite",
    ),
)


def _route_fragment(op: ReplayOperation) -> str:
    return f'@router.{op.method}("{op.route}")'


def _function_body(function_name: str) -> str:
    marker = f"async def {function_name}"
    assert marker in SOURCE, f"Missing replay handler {function_name} in {AUDIT_ROUTER}"
    start = SOURCE.index(marker)
    next_route = SOURCE.find("\n@router.", start + len(marker))
    if next_route == -1:
        next_route = len(SOURCE)
    return SOURCE[start:next_route]


def _has_explicit_idempotency_contract(body: str) -> bool:
    """True only for a visible replay-safe contract, not incidental happy-path code."""
    patterns = [
        r"Idempotency-Key",
        r"idempotency[_-]?key",
        r"client[_-]operation[_-]id",
        r"offline[_-]operation[_-]id",
        r"replay[_-]id",
        r"ON\s+CONFLICT",
        r"UniqueViolationError",
        r"unique constraint",
        r"content[_-]hash",
        r"sha256",
        r"duplicate",
        r"HTTPException\(409",
    ]
    return any(re.search(pattern, body, flags=re.IGNORECASE) for pattern in patterns)


def _has_scoped_authorization(body: str) -> bool:
    """Role checks are not enough; replay endpoints must scope by assigned/provider/business user."""
    scoped_patterns = [
        r"assert_audit_visit_mutation_scope\(",
        r"_audit_filter\(",
        r"resolve_canonical_tenant_id\(",
        r"resolve_canonical_user_id\(",
        r"provider_id\s*=\s*\$",
        r"auditor_id\s*=\s*\$",
        r"business_tenant\s*=\s*\$",
        r"JOIN\s+audit_visits",
    ]
    return "get_current_user" in body and any(re.search(pattern, body, flags=re.IGNORECASE) for pattern in scoped_patterns)


def test_mobile_offline_replay_contract_map_enumerates_backend_routes_and_actions():
    """Every known mobile offline operation is mapped to an explicit backend action."""
    assert {op.op_type for op in REPLAY_OPERATIONS} == {
        "checklist_item_update",
        "evidence_photo_upload:item_photo",
        "evidence_photo_upload:ncr_photo",
        "ncr_create",
        "ncr_update",
        "signature_upload",
        "visit_submit:status",
        "visit_submit:report",
    }
    for op in REPLAY_OPERATIONS:
        assert _route_fragment(op) in SOURCE, f"{op.op_type} expected route {_route_fragment(op)}"
        body = _function_body(op.function_name)
        assert op.action
        assert "Depends(get_current_user)" in body, f"{op.op_type} must remain authenticated"


def test_replay_create_or_append_endpoints_require_idempotency_key_or_unique_dedupe():
    """Create/append operations must not duplicate NCRs/photos on queue replay."""
    missing = []
    for op in REPLAY_OPERATIONS:
        if op.idempotency_kind != "create_or_append":
            continue
        body = _function_body(op.function_name)
        if not _has_explicit_idempotency_contract(body):
            missing.append(f"{op.op_type} -> {op.method.upper()} {op.route} ({op.function_name})")

    assert not missing, (
        "BLOCKED: mobile offline replay can duplicate side effects. Add Idempotency-Key/client_operation_id "
        "handling with unique persistence or ON CONFLICT/409 stable duplicate behavior for: "
        + "; ".join(missing)
    )


def test_replay_set_or_overwrite_endpoints_document_stable_duplicate_success_or_conflict():
    """PUT/set and deterministic overwrite handlers still need an explicit duplicate replay contract."""
    missing = []
    for op in REPLAY_OPERATIONS:
        if op.idempotency_kind not in {"set_update", "deterministic_overwrite"}:
            continue
        body = _function_body(op.function_name)
        stable_set_update = op.idempotency_kind == "set_update" and "UPDATE" in body and "INSERT INTO" not in body
        deterministic_overwrite = (
            op.idempotency_kind == "deterministic_overwrite"
            and "uuid4" not in body
            and "||" not in body
            and "UPDATE" in body
        )
        if not (_has_explicit_idempotency_contract(body) or stable_set_update or deterministic_overwrite):
            missing.append(f"{op.op_type} -> {op.method.upper()} {op.route} ({op.function_name})")

    assert not missing, (
        "BLOCKED: duplicate replay result is not explicitly stable success/conflict for: " + "; ".join(missing)
    )


def test_replay_endpoints_preserve_tenant_user_authorization_scope():
    """Offline replay must not bypass tenant/provider/auditor/business ownership checks."""
    missing_scope = []
    for op in REPLAY_OPERATIONS:
        body = _function_body(op.function_name)
        if not _has_scoped_authorization(body):
            missing_scope.append(f"{op.op_type} -> {op.method.upper()} {op.route} ({op.function_name})")

    assert not missing_scope, (
        "BLOCKED: replay endpoint has only role/id checks or unscoped writes; enforce visit/provider/auditor/business "
        "authorization before mutation for: "
        + "; ".join(missing_scope)
    )
