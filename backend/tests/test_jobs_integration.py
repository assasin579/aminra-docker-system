"""Integration tests for the ARQ queue + worker.

Uses a real Redis instance (TEST_REDIS_URL env, default redis://aminra-test-redis:6379/0).
Skips cleanly if Redis isn't reachable so CI without Redis still passes.
"""
from __future__ import annotations

import asyncio
import os
import socket
from urllib.parse import urlparse

import pytest

TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://aminra-test-redis:6379/0")


def _redis_reachable(url: str) -> bool:
    try:
        parsed = urlparse(url)
        with socket.create_connection((parsed.hostname, parsed.port or 6379), timeout=1):
            return True
    except (socket.error, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _redis_reachable(TEST_REDIS_URL),
    reason=f"Redis not reachable at {TEST_REDIS_URL}",
)


@pytest.fixture(autouse=True)
async def isolate_redis(monkeypatch):
    """Point services.jobs at the test Redis + clear pool between tests."""
    monkeypatch.setenv("REDIS_URL", TEST_REDIS_URL)
    from services.jobs import reset_pool
    await reset_pool()
    # Flush keys from previous test runs
    import redis.asyncio as aioredis
    r = aioredis.from_url(TEST_REDIS_URL)
    await r.flushdb()
    await r.aclose()
    yield
    await reset_pool()


# ── Pure producer round-trip (no worker yet) ────────────────────────────────

class TestEnqueueAgainstRealRedis:
    async def test_enqueue_returns_real_job_id(self):
        from services.jobs import enqueue

        result = await enqueue("ingest_document", path="/tmp/never-exists.pdf")
        assert isinstance(result.job_id, str)
        assert len(result.job_id) > 0

    async def test_status_immediately_after_enqueue_is_queued(self):
        from services.jobs import enqueue, get_job_status

        result = await enqueue("ingest_document", path="/tmp/x.pdf")
        view = await get_job_status(result.job_id)
        # ARQ status values: queued, in_progress, deferred, complete, not_found
        assert view.status in ("queued", "deferred")

    async def test_unknown_job_id_returns_not_found(self):
        from services.jobs import get_job_status

        view = await get_job_status("definitely-not-a-real-job-id-xyz")
        assert view.status == "not_found"


# ── End-to-end: enqueue → run a worker → poll completed status ─────────────

class TestWorkerExecutesJob:
    async def test_send_email_job_runs_via_worker(self, monkeypatch):
        """Enqueue, spin up an ARQ worker briefly, verify the job ran.

        Uses send_email since it's fast + has no external deps to mock.
        We replace get_mailer with a Capturing one so the job has something
        to call without needing real SMTP.
        """
        from services.mailer import CapturingSender, Mailer, MailerConfig

        # Make get_mailer() return a CapturingSender — survives both producer
        # and worker side because monkeypatch is per-process and ARQ workers
        # spawn within the same process when started via worker_settings.
        cfg = MailerConfig(
            enabled=False, from_email="x@y.z", from_name="Test",
            default_lang="vi", app_base_url="https://test",
        )
        sender = CapturingSender()
        mailer = Mailer(cfg, sender=sender)
        monkeypatch.setattr("services.mailer.get_mailer", lambda: mailer)

        from services.jobs import enqueue, get_job_status, WorkerSettings, get_pool
        from arq.worker import Worker

        # Enqueue
        result = await enqueue(
            "send_email",
            to="user@example.vn",
            template="password_reset",
            context={"reset_url": "https://x", "user_name": "Test"},
            lang="vi",
        )

        # Spin up a single-shot worker to drain the queue
        pool = await get_pool()
        worker = Worker(
            functions=WorkerSettings.functions,
            redis_pool=pool,
            handle_signals=False,
            burst=True,         # exit when queue empty
            max_jobs=1,
        )
        await worker.async_run()

        # Now the job should be complete
        view = await get_job_status(result.job_id)
        assert view.status == "complete"
        assert view.result == {"to": "user@example.vn", "template": "password_reset", "sent": True}

        # Email actually sent (captured)
        assert len(sender.outbox) == 1
        assert sender.outbox[0]["To"] == "user@example.vn"
