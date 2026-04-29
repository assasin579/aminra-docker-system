"""Async job queue (ARQ-based, Redis-backed).

Two job types so far:
    ingest_document  — RAG embedding + Qdrant upsert (heavy, was blocking workers)
    send_email       — async SMTP send (replaces sync await in request path)

Pattern:
    from services.jobs import enqueue, JobNotFound, get_job_status
    job = await enqueue("ingest_document", path=str(p))
    status = await get_job_status(job.job_id)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings
from arq.jobs import Job, JobStatus

log = logging.getLogger("aminra.jobs")


# ── Redis settings ──────────────────────────────────────────────────────────


def _redis_settings_from_env() -> RedisSettings:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return RedisSettings.from_dsn(url)


# ── Worker tasks ───────────────────────────────────────────────────────────


async def ingest_document(ctx: dict, path: str) -> dict:
    """Run RAG ingest in worker process. Returns {filename, chunks, status}."""
    from pipeline.ingest import ingest_file, ensure_collection, get_qdrant_client

    p = Path(path)
    log.info("[job:ingest_document] start path=%s", p.name)
    try:
        client = get_qdrant_client()
        ensure_collection(client, reset=False)
        chunks = ingest_file(p, client)
        log.info("[job:ingest_document] done path=%s chunks=%d", p.name, chunks)
        return {"filename": p.name, "chunks": chunks, "status": "completed"}
    except Exception as e:
        log.exception("[job:ingest_document] failed path=%s", p.name)
        return {"filename": p.name, "chunks": 0, "status": "failed", "error": str(e)}


async def send_email(
    ctx: dict,
    to: str,
    template: str,
    context: dict,
    lang: str = "vi",
) -> dict:
    """Send email via the Mailer service (queue-friendly wrapper)."""
    from services.mailer import get_mailer

    mailer = get_mailer()
    sent = await mailer.send_template(to=to, template=template, context=context, lang=lang)
    return {"to": to, "template": template, "sent": sent}


async def daily_anchor_polygon(ctx: dict) -> dict:
    """Pick certs + batches not yet anchored → Merkle tree → submit to Polygon.

    Idempotent: an item only ever appears in ONE anchor (we LEFT JOIN against
    cert_anchor_proofs / batch_anchor_proofs). Re-running this job after a
    successful anchor is a no-op.
    """
    from services.anchor import run_daily_anchor

    return await run_daily_anchor()


async def daily_submission_sla_check(ctx: dict) -> dict:
    """Find submissions hitting 80%/100% TTL and mark alert sent.

    For MVP: marks the alert internally + emits audit log. Email template
    submission_sla coming in next iteration; for now, internal SLA tracking
    + admin escalation queue is the value. Idempotent.
    """
    from auth.db import get_pool
    from services.audit_log import log_audit
    from services.submission_sla import find_at_risk_submissions, mark_sla_alert_sent

    pool = get_pool()
    flagged = 0
    async with pool.acquire() as conn:
        at_risk = await find_at_risk_submissions(conn)
        log.info("[sla] %d submissions at risk", len(at_risk))
        for r in at_risk:
            await mark_sla_alert_sent(conn, r.submission_id, r.threshold)
            await log_audit(
                conn,
                action="submission.sla_alert" if r.threshold < 100 else "submission.sla_overdue",
                entity_type="submission",
                entity_id=r.submission_id,
                metadata={
                    "threshold": r.threshold,
                    "elapsed_pct": r.elapsed_pct,
                    "days_remaining": r.days_remaining,
                    "provider_id": r.provider_id,
                },
            )
            flagged += 1
    return {"flagged": flagged, "checked": len(at_risk)}


async def daily_cert_expiry_alerts(ctx: dict) -> dict:
    """Find certs hitting alert thresholds (90/60/30/0d) + email business owners.

    Idempotent: each (cert × threshold) only fires once thanks to
    expiry_alerts_sent JSONB tracker.
    """
    from auth.db import get_pool
    from services.cert_lifecycle import find_expiring_certs, mark_alert_sent
    from services.mailer import get_mailer

    pool = get_pool()
    mailer = get_mailer()
    sent_count = 0
    failed = 0

    async with pool.acquire() as conn:
        expiring = await find_expiring_certs(conn)
        log.info("[cert_lifecycle] %d cert(s) need alerting", len(expiring))

        for ec in expiring:
            owner = await conn.fetchrow(
                """
                SELECT id, email, company_name
                FROM users
                WHERE (id = $1 OR tenant_id = $1)
                  AND is_owner = true AND deleted_at IS NULL
                LIMIT 1
                """,
                ec.business_tenant,
            )
            if owner is None or not owner["email"]:
                log.warning("[cert_lifecycle] no owner email for cert=%s", ec.cert_number)
                continue

            ok = await mailer.send_template(
                to=owner["email"],
                template="cert_expiring",
                context={
                    "user_name": owner["company_name"] or "",
                    "company_name": ec.company_name or owner["company_name"] or "",
                    "cert_number": ec.cert_number,
                    "expiry_date": ec.expiry_date.isoformat(),
                    "days_until_expiry": ec.days_until_expiry,
                    "cert_url": f"{mailer.config.app_base_url}/verify/{ec.cert_number}",
                },
                lang="vi",
            )
            if ok:
                await mark_alert_sent(conn, ec.cert_id, ec.threshold)
                sent_count += 1
            else:
                failed += 1

    return {"sent": sent_count, "failed": failed, "checked": len(expiring)}


# ── Worker config (loaded by `arq services.jobs.WorkerSettings`) ────────────

try:
    from arq.cron import cron  # type: ignore

    _CRON_AVAILABLE = True
except ImportError:  # arq < 0.26 fallback (tests)
    _CRON_AVAILABLE = False


class WorkerSettings:
    functions = [
        ingest_document,
        send_email,
        daily_anchor_polygon,
        daily_cert_expiry_alerts,
        daily_submission_sla_check,
    ]
    redis_settings = _redis_settings_from_env()
    job_timeout = 600  # 10 minutes for big PPTX/PDF
    keep_result = 3600  # results live 1 hour for status polling
    max_jobs = 4

    if _CRON_AVAILABLE:
        cron_jobs = [
            # Daily anchor at 23:00 UTC. Each item ends up in only one anchor.
            cron(daily_anchor_polygon, hour={23}, minute={0}, run_at_startup=False),
            # Daily expiry-alert check at 08:00 UTC (15:00 Vietnam).
            cron(daily_cert_expiry_alerts, hour={8}, minute={0}, run_at_startup=False),
            # Daily SLA check at 09:00 UTC.
            cron(daily_submission_sla_check, hour={9}, minute={0}, run_at_startup=False),
        ]


# ── Public producer API (used by FastAPI endpoints) ─────────────────────────


class JobNotFound(Exception):
    """Raised when a job_id cannot be found in Redis."""


_pool = None  # cached arq Redis pool


async def get_pool():
    """Get-or-create the producer-side Redis pool."""
    global _pool
    if _pool is None:
        _pool = await create_pool(_redis_settings_from_env())
    return _pool


async def reset_pool():
    """For tests — clear the cached pool between cases."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


@dataclass
class EnqueueResult:
    job_id: str
    function: str


async def enqueue(function: str, **kwargs: Any) -> EnqueueResult:
    """Push a job onto the queue. Returns the job_id for status polling."""
    pool = await get_pool()
    job = await pool.enqueue_job(function, **kwargs)
    if job is None:
        raise RuntimeError(f"Failed to enqueue {function} (already queued?)")
    return EnqueueResult(job_id=job.job_id, function=function)


@dataclass
class JobView:
    job_id: str
    status: str  # queued | in_progress | complete | failed | not_found
    result: Any | None
    error: str | None


async def get_job_status(job_id: str) -> JobView:
    """Poll a job by its ID. Returns status + result if complete."""
    pool = await get_pool()
    job = Job(job_id, pool)
    status = await job.status()
    if status == JobStatus.not_found:
        return JobView(job_id=job_id, status="not_found", result=None, error="Job not found")
    if status == JobStatus.complete:
        try:
            result = await job.result(timeout=0.1)
            return JobView(job_id=job_id, status="complete", result=result, error=None)
        except Exception as e:
            return JobView(job_id=job_id, status="failed", result=None, error=str(e))
    return JobView(job_id=job_id, status=status.value, result=None, error=None)
