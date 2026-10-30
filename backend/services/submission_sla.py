"""Submission SLA tracking — alert provider/business at 80% TTL + admin
escalation queue for overdue items.

Two thresholds:
  80  — "warning" — 80% of submission→deadline window elapsed, still not approved
  100 — "overdue" — past deadline, still not approved

`sla_alerts_sent` JSONB on submissions tracks which thresholds already alerted,
making the daily scan idempotent.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import asyncpg

log = logging.getLogger("aminra.submission_sla")

# Active states that count toward SLA (terminal states are excluded from scans)
ACTIVE_STATUSES = ("pending", "reviewing", "revision_required", "assigned")

# Thresholds expressed as percent of the submitted_at→deadline window elapsed
SLA_THRESHOLDS = [80, 100]


@dataclass
class AtRiskSubmission:
    submission_id: str
    business_tenant: str
    provider_id: str
    company_name: Optional[str]
    submitted_at: datetime
    deadline: datetime
    status: str
    threshold: int  # 80 or 100
    elapsed_pct: float  # actual % elapsed (>= threshold)
    days_remaining: int  # negative if overdue
    alerts_sent: list[int]


# ── Discovery ──────────────────────────────────────────────────────────────


async def find_at_risk_submissions(
    db: asyncpg.Connection,
    *,
    now: Optional[datetime] = None,
) -> list[AtRiskSubmission]:
    """Return submissions whose elapsed % >= an unsent threshold.

    Idempotent: each (submission × threshold) only fires once thanks to
    sla_alerts_sent tracker.
    """
    now = now or datetime.now(timezone.utc)

    rows = await db.fetch(
        """
        SELECT id, business_tenant, provider_id, company_name,
               submitted_at, deadline, status, sla_alerts_sent
        FROM submissions
        WHERE deadline IS NOT NULL
          AND status = ANY($1::text[])
        """,
        list(ACTIVE_STATUSES),
    )

    out: list[AtRiskSubmission] = []
    for r in rows:
        if r["submitted_at"] is None or r["deadline"] is None:
            continue
        # Normalize timezone — DB returns aware tz; ensure now is also aware
        submitted_at = r["submitted_at"]
        deadline = r["deadline"]
        if submitted_at >= deadline:
            continue  # malformed, skip

        total_seconds = (deadline - submitted_at).total_seconds()
        elapsed_seconds = (now - submitted_at).total_seconds()
        elapsed_pct = (elapsed_seconds / total_seconds) * 100 if total_seconds else 0
        days_remaining = int((deadline - now).total_seconds() // 86400)

        sent = r["sla_alerts_sent"]
        if isinstance(sent, str):
            sent = json.loads(sent) if sent else []

        # Find lowest unsent threshold this submission has crossed
        for t in sorted(SLA_THRESHOLDS):
            if elapsed_pct >= t and t not in sent:
                out.append(
                    AtRiskSubmission(
                        submission_id=str(r["id"]),
                        business_tenant=str(r["business_tenant"]),
                        provider_id=str(r["provider_id"]),
                        company_name=r["company_name"],
                        submitted_at=submitted_at,
                        deadline=deadline,
                        status=r["status"],
                        threshold=t,
                        elapsed_pct=round(elapsed_pct, 1),
                        days_remaining=days_remaining,
                        alerts_sent=sent,
                    )
                )
                break  # only the next pending threshold per submission per scan
    return out


async def mark_sla_alert_sent(
    db: asyncpg.Connection,
    submission_id: str,
    threshold: int,
) -> None:
    """Mark threshold as alerted for a submission. Idempotent (JSONB array union)."""
    await db.execute(
        """
        UPDATE submissions
           SET sla_alerts_sent =
                CASE WHEN sla_alerts_sent ? $1::text
                     THEN sla_alerts_sent
                     ELSE sla_alerts_sent || to_jsonb($2::int)
                END
         WHERE id = $3
        """,
        str(threshold),
        threshold,
        submission_id,
    )


# ── Admin escalation queue ─────────────────────────────────────────────────


async def list_overdue_submissions(
    db: asyncpg.Connection,
    *,
    limit: int = 100,
    provider_id: Optional[str] = None,
    auditor_id: Optional[str] = None,
) -> list[dict]:
    """All overdue submissions across providers (admin), or scoped to a
    single provider org / auditor.

    Scope rules:
      - provider_id given → only submissions where s.provider_id = $X
      - auditor_id given → only submissions where s.auditor_id = $X
      - neither → cross-tenant (admin use)

    At most ONE of provider_id / auditor_id should be set; if both given,
    auditor_id wins (narrower scope).
    """
    extra_clause = ""
    params: list = [list(ACTIVE_STATUSES), limit]
    if auditor_id is not None:
        extra_clause = " AND s.auditor_id = $3"
        params.append(auditor_id)
    elif provider_id is not None:
        extra_clause = " AND s.provider_id = $3"
        params.append(provider_id)

    rows = await db.fetch(
        f"""
        SELECT s.id, s.company_name, s.status, s.submitted_at, s.deadline,
               u.email AS provider_email,
               u.company_name AS provider_name,
               EXTRACT(EPOCH FROM (NOW() - s.deadline)) / 86400 AS days_overdue
        FROM submissions s
        LEFT JOIN users u ON u.id = s.provider_id
        WHERE s.deadline IS NOT NULL
          AND s.deadline < NOW()
          AND s.status = ANY($1::text[]){extra_clause}
        ORDER BY s.deadline ASC
        LIMIT $2
        """,
        *params,
    )
    return [
        {
            "submission_id": str(r["id"]),
            "company_name": r["company_name"],
            "status": r["status"],
            "submitted_at": r["submitted_at"].isoformat() if r["submitted_at"] else None,
            "deadline": r["deadline"].isoformat(),
            "provider_email": r["provider_email"],
            "provider_name": r["provider_name"],
            "days_overdue": round(r["days_overdue"] or 0, 1),
        }
        for r in rows
    ]
