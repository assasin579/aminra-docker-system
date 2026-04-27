"""Unit tests for services/jobs.py.

Covers the producer-side helpers (`enqueue`, `get_job_status`, `JobView`)
without standing up a real Redis. Where Redis behavior matters
(end-to-end queue + worker), see test_jobs_integration.py.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.jobs import (
    EnqueueResult,
    JobView,
    enqueue,
    get_job_status,
    reset_pool,
)


@pytest.fixture(autouse=True)
async def clear_pool():
    """Make sure each test starts with no cached pool."""
    await reset_pool()
    yield
    await reset_pool()


@pytest.fixture
def mock_pool(monkeypatch):
    """Replace get_pool() with an AsyncMock returning a fake pool."""
    pool = MagicMock()
    pool.aclose = AsyncMock()
    pool.enqueue_job = AsyncMock()

    async def _get_pool():
        return pool
    monkeypatch.setattr("services.jobs.get_pool", _get_pool)
    return pool


# ── enqueue() ───────────────────────────────────────────────────────────────

class TestEnqueue:
    async def test_returns_job_id_on_success(self, mock_pool):
        fake_job = MagicMock()
        fake_job.job_id = "job-abc-123"
        mock_pool.enqueue_job.return_value = fake_job

        result = await enqueue("ingest_document", path="/tmp/x.pdf")

        assert isinstance(result, EnqueueResult)
        assert result.job_id == "job-abc-123"
        assert result.function == "ingest_document"
        mock_pool.enqueue_job.assert_awaited_once_with("ingest_document", path="/tmp/x.pdf")

    async def test_raises_when_arq_returns_none(self, mock_pool):
        mock_pool.enqueue_job.return_value = None
        with pytest.raises(RuntimeError, match="Failed to enqueue"):
            await enqueue("ingest_document", path="/tmp/x.pdf")


# ── get_job_status() ────────────────────────────────────────────────────────

class TestGetJobStatus:
    async def test_complete_job_returns_result(self, mock_pool, monkeypatch):
        from arq.jobs import JobStatus

        # Stub the Job class so we don't hit Redis
        fake_job = MagicMock()
        fake_job.status = AsyncMock(return_value=JobStatus.complete)
        fake_job.result = AsyncMock(return_value={"chunks": 42, "status": "completed"})
        monkeypatch.setattr("services.jobs.Job", lambda *a, **kw: fake_job)

        view = await get_job_status("job-1")
        assert view.status == "complete"
        assert view.result == {"chunks": 42, "status": "completed"}
        assert view.error is None

    async def test_in_progress_job_returns_status_no_result(self, mock_pool, monkeypatch):
        from arq.jobs import JobStatus

        fake_job = MagicMock()
        fake_job.status = AsyncMock(return_value=JobStatus.in_progress)
        monkeypatch.setattr("services.jobs.Job", lambda *a, **kw: fake_job)

        view = await get_job_status("job-2")
        assert view.status == "in_progress"
        assert view.result is None

    async def test_unknown_job_returns_not_found(self, mock_pool, monkeypatch):
        from arq.jobs import JobStatus

        fake_job = MagicMock()
        fake_job.status = AsyncMock(return_value=JobStatus.not_found)
        monkeypatch.setattr("services.jobs.Job", lambda *a, **kw: fake_job)

        view = await get_job_status("nonexistent")
        assert view.status == "not_found"
        assert view.error == "Job not found"

    async def test_complete_job_with_failed_result_returns_failed(self, mock_pool, monkeypatch):
        from arq.jobs import JobStatus

        fake_job = MagicMock()
        fake_job.status = AsyncMock(return_value=JobStatus.complete)
        fake_job.result = AsyncMock(side_effect=ValueError("ingest failed"))
        monkeypatch.setattr("services.jobs.Job", lambda *a, **kw: fake_job)

        view = await get_job_status("job-3")
        assert view.status == "failed"
        assert "ingest failed" in view.error


# ── Worker function: send_email wrapper ─────────────────────────────────────

class TestSendEmailWorker:
    async def test_calls_mailer_send_template(self, monkeypatch):
        from services.jobs import send_email

        mailer = MagicMock()
        mailer.send_template = AsyncMock(return_value=True)
        monkeypatch.setattr("services.mailer.get_mailer", lambda: mailer)

        result = await send_email(
            ctx={},
            to="biz@example.vn",
            template="password_reset",
            context={"reset_url": "https://x"},
            lang="vi",
        )
        assert result == {"to": "biz@example.vn", "template": "password_reset", "sent": True}
        mailer.send_template.assert_awaited_once_with(
            to="biz@example.vn",
            template="password_reset",
            context={"reset_url": "https://x"},
            lang="vi",
        )

    async def test_propagates_send_failure(self, monkeypatch):
        from services.jobs import send_email

        mailer = MagicMock()
        mailer.send_template = AsyncMock(return_value=False)
        monkeypatch.setattr("services.mailer.get_mailer", lambda: mailer)

        result = await send_email(ctx={}, to="x@y.z", template="password_reset",
                                  context={"reset_url": "u"})
        assert result["sent"] is False


# ── WorkerSettings — config sanity ──────────────────────────────────────────

class TestWorkerSettings:
    def test_includes_both_job_functions(self):
        from services.jobs import WorkerSettings, ingest_document, send_email
        names = [f.__name__ for f in WorkerSettings.functions]
        assert "ingest_document" in names
        assert "send_email" in names

    def test_timeout_long_enough_for_pptx(self):
        from services.jobs import WorkerSettings
        # PPTX ingest can take several minutes — must not hard-fail at 60s default
        assert WorkerSettings.job_timeout >= 600

    def test_keeps_results_for_polling_window(self):
        from services.jobs import WorkerSettings
        # Clients need a window to poll completion — 1 hour is reasonable
        assert WorkerSettings.keep_result >= 600
