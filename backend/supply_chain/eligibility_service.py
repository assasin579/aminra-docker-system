"""CB-authoritative supplier eligibility service.

All checks fail closed: supplier must belong to the requesting buyer tenant and
have exactly CB source, active status, current validity dates, and matching
scope when a material category is requested.
"""

from __future__ import annotations

from datetime import date
import json
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel


ELIGIBLE_STATUS = "active"
ALERT_STATUSES = {"expired", "suspended", "revoked"}


class SupplierEligibilityResult(BaseModel):
    supplier_id: str
    tenant_id: str
    eligible: bool
    reason: str
    certificate_id: str | None = None
    status: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    source_of_truth: str | None = None
    scope: dict[str, Any] = {}


def _json_object(value: Any) -> dict[str, Any]:
    """Normalize asyncpg JSON/JSONB values to an object dict.

    Some environments return jsonb as a JSON string, others as decoded dicts.
    Malformed/non-object scope fails closed as `{}` instead of crashing the
    eligibility path.
    """
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _scope_matches(scope: dict[str, Any] | None, material_category: str | None) -> bool:
    if not material_category:
        return True
    if not scope:
        return False
    allowed = scope.get("material_categories") or scope.get("categories")
    if allowed in (None, [], ""):
        return False
    if isinstance(allowed, str):
        allowed_values = {allowed.lower()}
    elif isinstance(allowed, list):
        allowed_values = {str(v).lower() for v in allowed}
    else:
        return False
    return material_category.lower() in allowed_values or "*" in allowed_values


async def evaluate_supplier_eligibility(
    db,
    tenant_id: str,
    supplier_id: str,
    material_category: str | None = None,
    as_of: date | None = None,
) -> SupplierEligibilityResult:
    row = await db.fetchrow(
        """
        SELECT s.id AS supplier_id, s.tenant_id,
               e.id AS certificate_id, e.status, e.valid_from, e.valid_until,
               e.source_of_truth, e.scope
        FROM suppliers s
        LEFT JOIN supplier_eligibilities e ON e.supplier_id = s.id
        WHERE s.id = $1 AND s.tenant_id = $2
        """,
        supplier_id,
        tenant_id,
    )
    if not row:
        return SupplierEligibilityResult(
            supplier_id=supplier_id, tenant_id=tenant_id, eligible=False, reason="supplier_not_found"
        )
    if not row["certificate_id"]:
        return SupplierEligibilityResult(
            supplier_id=supplier_id, tenant_id=tenant_id, eligible=False, reason="missing_cb_eligibility"
        )

    scope = _json_object(row["scope"])
    base = SupplierEligibilityResult(
        supplier_id=str(row["supplier_id"]),
        tenant_id=str(row["tenant_id"]),
        eligible=False,
        reason="not_evaluated",
        certificate_id=str(row["certificate_id"]),
        status=row["status"],
        valid_from=row["valid_from"],
        valid_until=row["valid_until"],
        source_of_truth=row["source_of_truth"],
        scope=scope,
    )

    if row["source_of_truth"] != "cb":
        base.reason = "source_of_truth_not_cb"
        return base
    if row["status"] != ELIGIBLE_STATUS:
        base.reason = f"status_{row['status']}"
        return base

    today = as_of or date.today()
    if row["valid_from"] and row["valid_from"] > today:
        base.reason = "certificate_not_yet_valid"
        return base
    if row["valid_until"] and row["valid_until"] < today:
        base.reason = "certificate_expired"
        return base
    if not _scope_matches(scope, material_category):
        base.reason = "scope_mismatch"
        return base

    base.eligible = True
    base.reason = "eligible"
    return base


async def is_supplier_eligible(db, tenant_id: str, supplier_id: str, material_category: str | None = None) -> bool:
    result = await evaluate_supplier_eligibility(db, tenant_id, supplier_id, material_category)
    return result.eligible


async def assert_supplier_eligible(
    db, tenant_id: str, supplier_id: str, material_category: str | None = None
) -> SupplierEligibilityResult:
    result = await evaluate_supplier_eligibility(db, tenant_id, supplier_id, material_category)
    if not result.eligible:
        raise HTTPException(400, f"Nhà cung cấp chưa đủ điều kiện CB: {result.reason}")
    return result


async def list_eligible_suppliers(db, tenant_id: str, material_category: str | None = None) -> list[dict[str, Any]]:
    rows = await db.fetch(
        """
        SELECT s.*,
               e.id AS eligibility_id,
               e.certificate_no,
               e.issuer_name,
               e.status AS certificate_status,
               e.valid_from,
               e.valid_until,
               e.scope,
               e.provider_id,
               e.source_certificate_id,
               e.source_of_truth,
               (SELECT COUNT(*) FROM materials m WHERE m.supplier_id = s.id) AS material_count,
               (SELECT COUNT(*) FROM supplier_certificates c WHERE c.supplier_id = s.id) AS cert_count
        FROM suppliers s
        JOIN supplier_eligibilities e ON e.supplier_id = s.id
        WHERE s.tenant_id = $1
          AND e.tenant_id = s.tenant_id
          AND e.source_of_truth = 'cb'
          AND e.status = 'active'
          AND e.valid_from <= CURRENT_DATE
          AND e.valid_until >= CURRENT_DATE
        ORDER BY s.created_at DESC
        """,
        tenant_id,
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        scope = _json_object(row["scope"])
        if not _scope_matches(scope, material_category):
            continue
        result.append(dict(row))
    return result


async def find_impacted_buyers(db, supplier_id: str, certificate_id: str | None = None) -> list[str]:
    rows = await db.fetch(
        """
        SELECT DISTINCT buyer_tenant_id
        FROM supply_relationships
        WHERE supplier_id = $1 AND status = 'active'
        ORDER BY buyer_tenant_id
        """,
        supplier_id,
    )
    return [str(r["buyer_tenant_id"]) for r in rows]


async def create_certificate_status_alerts(
    db,
    supplier_id: str,
    certificate_id: str,
    event_type: str,
    message: str | None = None,
) -> list[str]:
    if event_type not in ALERT_STATUSES:
        return []
    impacted = await find_impacted_buyers(db, supplier_id, certificate_id)
    severity = "critical" if event_type in {"revoked", "suspended"} else "high"
    alert_message = message or f"Chứng nhận CB của nhà cung cấp đã chuyển trạng thái: {event_type}"
    for buyer_tenant_id in impacted:
        await db.execute(
            """
            INSERT INTO certificate_risk_alerts
              (impacted_tenant_id, supplier_id, certificate_id, event_type, severity, message)
            VALUES ($1,$2,$3,$4,$5,$6)
            """,
            buyer_tenant_id,
            supplier_id,
            certificate_id,
            event_type,
            severity,
            alert_message,
        )
    return impacted
