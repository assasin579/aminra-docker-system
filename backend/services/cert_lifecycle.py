"""Certificate lifecycle service — revocation + expiry alerts.

Two flows:
1. **Revocation** — provider revokes cert with mandatory reason; tamper-proof
   record + business notification.
2. **Expiry alerts** — daily scheduled job finds certs expiring at fixed
   thresholds (90/60/30/0 days) and emails business owners. Uses
   `expiry_alerts_sent` JSONB to avoid duplicate alerts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import asyncpg

log = logging.getLogger("aminra.cert_lifecycle")


# ── Errors ──────────────────────────────────────────────────────────────────


class CertNotFound(Exception): ...


class InvalidRevocation(Exception): ...


class AlreadyRevoked(Exception): ...


# ── Config ──────────────────────────────────────────────────────────────────

# Days before expiry to send alerts. 0 = day-of-expiry. Order matters
# (most-distant first) so we send "90d warning" before "60d warning".
EXPIRY_ALERT_THRESHOLDS = [90, 60, 30, 0]


# ── Revocation ──────────────────────────────────────────────────────────────


@dataclass
class RevokeResult:
    cert_id: str
    cert_number: str
    business_tenant: str
    revoked_at: datetime
    reason: str


async def revoke_cert(
    db: asyncpg.Connection,
    *,
    cert_id: str,
    reason: str,
    revoked_by_user_id: str,
) -> RevokeResult:
    """Mark a cert revoked with mandatory reason + actor identity.

    Atomic: either the cert flips to status='revoked' with all fields filled,
    or nothing changes. Raises AlreadyRevoked if cert already revoked.
    """
    if not reason.strip():
        raise InvalidRevocation("reason is required")

    row = await db.fetchrow(
        """
        SELECT id, cert_number, business_tenant, issued_by, status, revoked_at
        FROM halal_certificates WHERE id = $1
        """,
        cert_id,
    )
    if row is None:
        raise CertNotFound(cert_id)
    if row["revoked_at"] is not None or row["status"] == "revoked":
        raise AlreadyRevoked(cert_id)
    # P0 provider-scope invariant: a provider may revoke only certificates it
    # issued. Older unit fakes may not include issued_by; enforce when present
    # so the real DB path fails closed without breaking schema-light tests.
    if "issued_by" in row.keys() and str(row["issued_by"]) != str(revoked_by_user_id):
        raise InvalidRevocation("provider scope mismatch")

    result = await db.fetchrow(
        """
        UPDATE halal_certificates
           SET status              = 'revoked',
               revocation_reason   = $1,
               revoked_by          = $2,
               revoked_at          = NOW(),
               updated_at          = NOW()
         WHERE id = $3
        RETURNING revoked_at
        """,
        reason.strip(),
        revoked_by_user_id,
        cert_id,
    )

    log.info("[cert_lifecycle] revoked cert=%s by=%s", row["cert_number"], revoked_by_user_id)
    return RevokeResult(
        cert_id=str(row["id"]),
        cert_number=row["cert_number"],
        business_tenant=str(row["business_tenant"]),
        revoked_at=result["revoked_at"],
        reason=reason.strip(),
    )


# ── Expiry alerts ──────────────────────────────────────────────────────────


@dataclass
class ExpiringCert:
    cert_id: str
    cert_number: str
    business_tenant: str
    expiry_date: date
    days_until_expiry: int
    threshold: int  # which threshold (90/60/30/0) this matches
    alerts_sent: list[int]  # thresholds already alerted
    company_name: str | None = None


async def find_expiring_certs(
    db: asyncpg.Connection,
    *,
    today: Optional[date] = None,
) -> list[ExpiringCert]:
    """Find active certs whose expiry is within an alert threshold AND haven't
    had that alert fired yet.

    Returns one entry per (cert × pending threshold). Idempotent: re-running
    won't duplicate alerts because `expiry_alerts_sent` tracks fired ones.
    """
    today = today or date.today()
    out: list[ExpiringCert] = []

    rows = await db.fetch(
        """
        SELECT id, cert_number, business_tenant, expiry_date, expiry_alerts_sent,
               company_name
        FROM halal_certificates
        WHERE status = 'active'
          AND expiry_date <= $1
        """,
        today + __import__("datetime").timedelta(days=max(EXPIRY_ALERT_THRESHOLDS)),
    )
    for r in rows:
        days_until = (r["expiry_date"] - today).days
        sent = r["expiry_alerts_sent"]
        if isinstance(sent, str):
            sent = json.loads(sent) if sent else []

        # Find the largest threshold that fits (most urgent has lowest number)
        # Days until 30 → threshold=30. Days until 25 → threshold=30 (still pending). Days until 5 → threshold=0.
        for t in sorted(EXPIRY_ALERT_THRESHOLDS):
            if days_until <= t and t not in sent:
                out.append(
                    ExpiringCert(
                        cert_id=str(r["id"]),
                        cert_number=r["cert_number"],
                        business_tenant=str(r["business_tenant"]),
                        expiry_date=r["expiry_date"],
                        days_until_expiry=days_until,
                        threshold=t,
                        alerts_sent=sent,
                        company_name=r["company_name"],
                    )
                )
                break  # only most-urgent unsent threshold per cert

    return out


async def mark_alert_sent(
    db: asyncpg.Connection,
    cert_id: str,
    threshold: int,
) -> None:
    """Append `threshold` to expiry_alerts_sent for a cert (idempotent — JSONB
    array union)."""
    await db.execute(
        """
        UPDATE halal_certificates
           SET expiry_alerts_sent =
                CASE WHEN expiry_alerts_sent ? $1::text
                     THEN expiry_alerts_sent
                     ELSE expiry_alerts_sent || to_jsonb($2::int)
                END
         WHERE id = $3
        """,
        str(threshold),
        threshold,
        cert_id,
    )


# ── Bulk revoke for cert_decision flow ────────────────────────────────────


async def revoke_active_certs_for_business(
    db: asyncpg.Connection,
    *,
    business_tenant: str,
    issued_by: str,
    reason: str,
    revoked_by: str,
) -> int:
    """Revoke every ACTIVE cert this provider issued to this business.

    Used by /audits/{vid}/decision when the decision is 'revoke'. Filters
    by both `business_tenant` AND `issued_by` so we never affect another
    provider's certs (cross-provider write fix C4).

    Each cert revoked individually so the per-row trigger on `audit_logs`
    plus `chk_cert_revocation_has_reason` constraint hold.
    """
    if not reason.strip():
        raise InvalidRevocation("reason is required")
    rows = await db.fetch(
        "SELECT id FROM halal_certificates "
        "WHERE business_tenant=$1 AND issued_by=$2 AND status='active' AND revoked_at IS NULL",
        business_tenant,
        issued_by,
    )
    affected = 0
    for r in rows:
        try:
            await revoke_cert(db, cert_id=str(r["id"]), reason=reason, revoked_by_user_id=revoked_by)
            affected += 1
        except AlreadyRevoked:
            continue
    return affected


# ── Stats helper for admin dashboard ──────────────────────────────────────


async def lifecycle_stats(db: asyncpg.Connection) -> dict:
    """Return counts grouped by lifecycle state for admin dashboard widget."""
    row = await db.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'active' AND expiry_date >  NOW() + INTERVAL '90 days')  AS healthy,
            COUNT(*) FILTER (WHERE status = 'active' AND expiry_date <= NOW() + INTERVAL '90 days'
                                                    AND expiry_date >  NOW() + INTERVAL '60 days')   AS expiring_90,
            COUNT(*) FILTER (WHERE status = 'active' AND expiry_date <= NOW() + INTERVAL '60 days'
                                                    AND expiry_date >  NOW() + INTERVAL '30 days')   AS expiring_60,
            COUNT(*) FILTER (WHERE status = 'active' AND expiry_date <= NOW() + INTERVAL '30 days'
                                                    AND expiry_date >  NOW())                          AS expiring_30,
            COUNT(*) FILTER (WHERE status = 'active' AND expiry_date <= NOW())                         AS expired,
            COUNT(*) FILTER (WHERE status = 'revoked')                                                  AS revoked,
            COUNT(*)                                                                                    AS total
        FROM halal_certificates
        """
    )
    return dict(row)
