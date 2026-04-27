"""Tests for the env-tunable resilience knobs added in Critical #3.

We cover:
- DB pool config reads each env var
- Pool config defaults are conservative but safe
- Procfile + Dockerfile use env interpolation (text-level check)
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


# ── Pool config ────────────────────────────────────────────────────────────

class TestPoolConfig:
    def test_defaults_are_conservative(self, monkeypatch):
        # Clear any test-time overrides
        for var in ("DB_POOL_MIN_SIZE", "DB_POOL_MAX_SIZE", "DB_POOL_MAX_QUERIES",
                    "DB_POOL_INACTIVE_LIFETIME", "DB_COMMAND_TIMEOUT"):
            monkeypatch.delenv(var, raising=False)
        from auth.db import _pool_config
        cfg = _pool_config()
        assert cfg["min_size"] == 2
        assert cfg["max_size"] == 10
        assert cfg["command_timeout"] == 30

    def test_env_overrides_apply(self, monkeypatch):
        monkeypatch.setenv("DB_POOL_MIN_SIZE", "5")
        monkeypatch.setenv("DB_POOL_MAX_SIZE", "30")
        monkeypatch.setenv("DB_POOL_MAX_QUERIES", "100000")
        monkeypatch.setenv("DB_POOL_INACTIVE_LIFETIME", "600")
        monkeypatch.setenv("DB_COMMAND_TIMEOUT", "60")
        from auth.db import _pool_config
        cfg = _pool_config()
        assert cfg["min_size"] == 5
        assert cfg["max_size"] == 30
        assert cfg["max_queries"] == 100_000
        assert cfg["max_inactive_connection_lifetime"] == 600
        assert cfg["command_timeout"] == 60

    def test_max_size_can_exceed_min_size(self, monkeypatch):
        # Sanity: asyncpg requires min_size <= max_size
        monkeypatch.setenv("DB_POOL_MIN_SIZE", "2")
        monkeypatch.setenv("DB_POOL_MAX_SIZE", "100")
        from auth.db import _pool_config
        cfg = _pool_config()
        assert cfg["min_size"] <= cfg["max_size"]

    def test_invalid_int_raises(self, monkeypatch):
        monkeypatch.setenv("DB_POOL_MAX_SIZE", "not-a-number")
        from auth.db import _pool_config
        with pytest.raises(ValueError):
            _pool_config()


# ── Procfile / Dockerfile env interpolation ────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent  # /app


class TestStartupCommandUsesEnv:
    def test_procfile_reads_web_concurrency_env(self):
        text = (REPO_ROOT / "Procfile").read_text()
        assert "${WEB_CONCURRENCY" in text, "Procfile must read WEB_CONCURRENCY env"

    def test_procfile_has_max_requests_for_leak_protection(self):
        text = (REPO_ROOT / "Procfile").read_text()
        assert "--max-requests" in text, (
            "gunicorn --max-requests prevents memory-leak accumulation across long-running workers"
        )

    def test_dockerfile_uses_env_for_workers(self):
        text = (REPO_ROOT / "Dockerfile").read_text()
        assert "${WEB_CONCURRENCY" in text, (
            "Dockerfile CMD must interpolate WEB_CONCURRENCY so deployments can tune"
        )
        assert "--max-requests" in text


# ── env.example documents knobs ────────────────────────────────────────────

class TestEnvExampleDocsKnobs:
    def test_lists_all_pool_knobs(self):
        text = (REPO_ROOT / "env.example").read_text()
        for var in ("DB_POOL_MIN_SIZE", "DB_POOL_MAX_SIZE", "DB_COMMAND_TIMEOUT"):
            assert var in text, f"env.example must document {var}"

    def test_lists_worker_knobs(self):
        text = (REPO_ROOT / "env.example").read_text()
        for var in ("WEB_CONCURRENCY", "WORKER_TIMEOUT", "MAX_REQUESTS"):
            assert var in text

    def test_lists_redis_url(self):
        text = (REPO_ROOT / "env.example").read_text()
        assert "REDIS_URL" in text
