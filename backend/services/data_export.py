"""User data export service.

Implements Vietnam Nghị định 13/2023/NĐ-CP Article 9 (Right to access /
export personal data) and is structured to also satisfy GDPR Article 20
(Right to data portability) — JSON output, machine-readable.

Design:
- Single function `export_user_data(db, user)` returns a dict ready for
  json.dumps. Caller (router) is responsible for serialization + headers.
- Pulls from every table that stores user-linked or tenant-linked data,
  filtered so the export contains ONLY what's about that user.
- Sensitive fields excluded: password_hash, refresh_token jti, IP of OTHER
  users in shared records (audit_logs metadata.ip is kept for the
  requesting user's own events only).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("aminra.data_export")

EXPORT_FORMAT_VERSION = "1.0"


def _to_jsonable(value: Any) -> Any:
    """Recursively convert asyncpg / datetime / UUID values to JSON-safe."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return str(value)


def _row_to_dict(row, *, drop: set[str] = frozenset()) -> dict:
    if row is None:
        return {}
    return {k: _to_jsonable(v) for k, v in dict(row).items() if k not in drop}


def _rows(rows, *, drop: set[str] = frozenset()) -> list[dict]:
    return [_row_to_dict(r, drop=drop) for r in rows]


# Sensitive fields we never export
SECRET_FIELDS = {"password_hash"}


# ── Main entry point ────────────────────────────────────────────────────────

async def export_user_data(db, user: dict) -> dict:
    """Build a complete export bundle for a single user.

    `user` is the JWT payload (sub, email, role, tenant_id, is_owner).
    """
    if not user or not user.get("sub"):
        raise ValueError("user is required")

    user_id   = user["sub"]
    role      = user.get("role")
    tenant_id = user.get("tenant_id")

    profile = await _profile(db, user_id)
    notifications = await _notifications(db, user_id)
    audit_logs = await _audit_logs(db, user_id)

    # Role-specific bundles
    business_data: dict = {}
    provider_data: dict = {}

    if tenant_id:
        business_data = await _business_tenant_data(db, tenant_id)

    if role == "provider":
        provider_data = await _provider_data(db, user_id)

    return {
        "export_format_version": EXPORT_FORMAT_VERSION,
        "exported_at":           datetime.now(timezone.utc).isoformat(),
        "user_id":               user_id,
        "data_subject": {
            "profile":       profile,
            "notifications": notifications,
            "audit_logs":    audit_logs,
        },
        "tenant_data":   business_data,
        "provider_data": provider_data,
        "legal_basis": {
            "vietnam":    "Nghị định 13/2023/NĐ-CP — Quyền tiếp cận và xuất dữ liệu cá nhân",
            "eu_gdpr":    "Article 20 — Right to data portability",
        },
        "retention_note": (
            "Audit logs may be retained beyond account deletion per legal "
            "compliance requirements (minimum 5 years)."
        ),
    }


# ── Sections ────────────────────────────────────────────────────────────────

async def _profile(db, user_id: str) -> dict:
    row = await db.fetchrow(
        """
        SELECT id, email, role, status, company_name, company_code, is_owner,
               tenant_id, address, phone, representative_name,
               created_at, updated_at, approved_at, approved_by
        FROM users WHERE id = $1
        """,
        user_id,
    )
    return _row_to_dict(row, drop=SECRET_FIELDS)


async def _notifications(db, user_id: str) -> list[dict]:
    rows = await db.fetch(
        "SELECT id, type, title, message, link, read, created_at "
        "FROM notifications WHERE user_id = $1 ORDER BY created_at DESC",
        user_id,
    )
    return _rows(rows)


async def _audit_logs(db, user_id: str) -> list[dict]:
    rows = await db.fetch(
        "SELECT id, action, entity_type, entity_id, changes, metadata, created_at "
        "FROM audit_logs WHERE user_id = $1 ORDER BY created_at DESC",
        user_id,
    )
    out = []
    for r in rows:
        item = _row_to_dict(r)
        # Changes / metadata are JSONB strings — re-parse for cleanliness
        for jsonkey in ("changes", "metadata"):
            v = item.get(jsonkey)
            if isinstance(v, str):
                try:
                    item[jsonkey] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    pass
        out.append(item)
    return out


async def _business_tenant_data(db, tenant_id: str) -> dict:
    """Everything tied to a tenant_id — relevant for both business owners
    and provider owners (their CB tenant)."""
    documents      = await db.fetch(
        "SELECT id, filename, doc_type, status, uploaded_at "
        "FROM documents WHERE tenant_id = $1 ORDER BY uploaded_at DESC",
        tenant_id,
    )
    submissions    = await db.fetch(
        "SELECT id, provider_id, document_ids, status, notes, company_name, "
        "       submitted_at, updated_at, auditor_notes "
        "FROM submissions WHERE business_tenant = $1 ORDER BY submitted_at DESC",
        tenant_id,
    )
    certificates   = await db.fetch(
        "SELECT id, cert_number, issued_by, company_name, issue_date, "
        "       expiry_date, status, notes, created_at "
        "FROM halal_certificates WHERE business_tenant = $1 ORDER BY issue_date DESC",
        tenant_id,
    )
    audit_visits   = await db.fetch(
        "SELECT id, visit_type, status, scheduled_date, location, "
        "       compliance_score, created_at "
        "FROM audit_visits WHERE business_tenant = $1 ORDER BY scheduled_date DESC",
        tenant_id,
    )
    suppliers      = await db.fetch(
        "SELECT id, name, supplier_type, status, contact_person, created_at "
        "FROM suppliers WHERE tenant_id = $1 ORDER BY created_at DESC",
        tenant_id,
    )
    materials      = await db.fetch(
        "SELECT id, name, sku, category, supplier_id, halal_risk, created_at "
        "FROM materials WHERE tenant_id = $1 ORDER BY created_at DESC",
        tenant_id,
    )
    batches        = await db.fetch(
        "SELECT id, batch_code, product_name, status, started_at, completed_at "
        "FROM production_batches WHERE tenant_id = $1 ORDER BY created_at DESC",
        tenant_id,
    )
    self_assess    = await db.fetch(
        "SELECT id, standard, name, score, total_items, passed_items, status, created_at "
        "FROM self_assessments WHERE tenant_id = $1 ORDER BY created_at DESC",
        tenant_id,
    )

    return {
        "tenant_id":         tenant_id,
        "documents":         _rows(documents),
        "submissions":       _rows(submissions),
        "certificates":      _rows(certificates),
        "audit_visits":      _rows(audit_visits),
        "suppliers":         _rows(suppliers),
        "materials":         _rows(materials),
        "production_batches": _rows(batches),
        "self_assessments":  _rows(self_assess),
    }


async def _provider_data(db, provider_user_id: str) -> dict:
    """For users with role=provider: submissions/audits/certs they issued."""
    received_submissions = await db.fetch(
        "SELECT id, business_tenant, status, submitted_at, updated_at, auditor_notes "
        "FROM submissions WHERE provider_id = $1 ORDER BY submitted_at DESC",
        provider_user_id,
    )
    audits_run = await db.fetch(
        "SELECT id, business_tenant, visit_type, status, scheduled_date "
        "FROM audit_visits WHERE provider_id = $1 ORDER BY scheduled_date DESC",
        provider_user_id,
    )
    certs_issued = await db.fetch(
        "SELECT id, cert_number, business_tenant, company_name, "
        "       issue_date, expiry_date, status "
        "FROM halal_certificates WHERE issued_by = $1 ORDER BY issue_date DESC",
        provider_user_id,
    )
    return {
        "received_submissions": _rows(received_submissions),
        "audit_visits_run":     _rows(audits_run),
        "certificates_issued":  _rows(certs_issued),
    }
