"""Admin analytics — composite dashboard for Halal cert ops.

Returns aggregated stats useful for the MVP admin dashboard:
- Certificate expiry buckets (active, <30d, <60d, <90d, expired)
- Submission funnel (counts per status)
- Monthly cert issuance trend (last 12 months)
- Recent audit-log activity (top actions in last 7 days)
- User activity heatmap by day-of-week × hour
"""

from __future__ import annotations

from datetime import datetime, timezone

from asyncpg import Connection
from fastapi import APIRouter, Depends

from auth.db import get_db
from auth.jwt_utils import require_admin

router = APIRouter()


@router.get("/admin/analytics")
async def admin_analytics(
    admin: dict = Depends(require_admin),
    db: Connection = Depends(get_db),
):
    cert_buckets = await _cert_expiry_buckets(db)
    funnel = await _submission_funnel(db)
    monthly_trend = await _monthly_cert_trend(db)
    top_actions = await _top_actions_recent(db)
    heatmap = await _activity_heatmap(db)
    return {
        "cert_buckets": cert_buckets,
        "funnel": funnel,
        "monthly_trend": monthly_trend,
        "top_actions": top_actions,
        "heatmap": heatmap,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── 1. Certificate expiry buckets ──────────────────────────────────────────


async def _cert_expiry_buckets(db: Connection) -> dict:
    row = await db.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status='active' AND expiry_date >= NOW() + INTERVAL '90 days') AS healthy,
            COUNT(*) FILTER (WHERE status='active' AND expiry_date >= NOW() + INTERVAL '60 days'
                                                  AND expiry_date <  NOW() + INTERVAL '90 days') AS expiring_90d,
            COUNT(*) FILTER (WHERE status='active' AND expiry_date >= NOW() + INTERVAL '30 days'
                                                  AND expiry_date <  NOW() + INTERVAL '60 days') AS expiring_60d,
            COUNT(*) FILTER (WHERE status='active' AND expiry_date >= NOW()
                                                  AND expiry_date <  NOW() + INTERVAL '30 days') AS expiring_30d,
            COUNT(*) FILTER (WHERE status='active' AND expiry_date < NOW())                      AS expired,
            COUNT(*) FILTER (WHERE status='suspended')                                           AS suspended,
            COUNT(*) FILTER (WHERE status='revoked')                                             AS revoked,
            COUNT(*)                                                                             AS total
        FROM halal_certificates
        """
    )
    return {k: row[k] or 0 for k in row.keys()}


# ── 2. Submission funnel ───────────────────────────────────────────────────


async def _submission_funnel(db: Connection) -> dict:
    rows = await db.fetch("SELECT status, COUNT(*) AS n FROM submissions GROUP BY status")
    funnel = {r["status"]: r["n"] for r in rows}
    # Always return all known statuses (default 0) so the FE chart axes are stable.
    for s in ("pending", "assigned", "reviewing", "returned", "approved", "rejected"):
        funnel.setdefault(s, 0)
    return funnel


# ── 3. Monthly cert trend ──────────────────────────────────────────────────


async def _monthly_cert_trend(db: Connection) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT TO_CHAR(date_trunc('month', issue_date), 'YYYY-MM') AS month,
               COUNT(*) AS issued
        FROM halal_certificates
        WHERE issue_date >= NOW() - INTERVAL '12 months'
        GROUP BY 1
        ORDER BY 1
        """
    )
    return [{"month": r["month"], "issued": r["issued"]} for r in rows]


# ── 4. Top actions in last 7 days ──────────────────────────────────────────


async def _top_actions_recent(db: Connection) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT action, COUNT(*) AS n
        FROM audit_logs
        WHERE created_at >= NOW() - INTERVAL '7 days'
        GROUP BY action
        ORDER BY n DESC
        LIMIT 10
        """
    )
    return [{"action": r["action"], "count": r["n"]} for r in rows]


# ── 5. Activity heatmap (day-of-week × hour) ───────────────────────────────


async def _activity_heatmap(db: Connection) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT EXTRACT(DOW FROM created_at)::int  AS dow,
               EXTRACT(HOUR FROM created_at)::int AS hour,
               COUNT(*) AS n
        FROM audit_logs
        WHERE created_at >= NOW() - INTERVAL '30 days'
        GROUP BY 1, 2
        """
    )
    return [{"dow": r["dow"], "hour": r["hour"], "count": r["n"]} for r in rows]
