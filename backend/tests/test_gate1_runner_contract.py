"""Contract tests for Gate 1 onboarding QA runner.

These tests intentionally validate runner behavior, not product behavior:
- the runner must exist;
- it must produce durable report/status artifacts;
- it must not print secrets;
- it must classify required gates instead of silently succeeding.
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    here = Path(__file__).resolve()
    # Host: <repo>/backend/tests/test_*.py. Container may place tests under /app/tests.
    candidates = [here.parents[2], here.parents[1]]
    for candidate in candidates:
        if (candidate / "scripts" / "qa").exists():
            return candidate
    raise AssertionError(f"repo root not found from {here}; candidates={candidates}")


def test_gate1_runner_exists_and_is_shell_script() -> None:
    script = repo_root() / "scripts" / "qa" / "run-gate1-onboarding.sh"
    assert script.exists(), "Gate 1 runner script must exist"
    text = script.read_text()
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -" in text
    assert "20260917-gate1-onboarding" in text


def test_gate1_runner_writes_required_artifacts() -> None:
    script = repo_root() / "scripts" / "qa" / "run-gate1-onboarding.sh"
    text = script.read_text()
    for required in ["status.tsv", "report.md", "evidence/terminal", "acceptance-matrix.md"]:
        assert required in text
    assert "append_status" in text
    assert "run_step" in text


def test_gate1_runner_redacts_secret_like_values() -> None:
    script = repo_root() / "scripts" / "qa" / "run-gate1-onboarding.sh"
    text = script.read_text().lower()
    assert "set -x" not in text
    assert "password}" not in text
    assert "token}" not in text
    assert "secret}" not in text
    assert "redact" in text or "without secrets" in text


def test_gate1_runner_has_required_gate_labels() -> None:
    script = repo_root() / "scripts" / "qa" / "run-gate1-onboarding.sh"
    text = script.read_text()
    required_gate_ids = [
        "G1-RUNTIME",
        "G1-EMAIL",
        "G1-SESSION",
        "G1-BUSINESS",
        "G1-PROVIDER",
        "G1-AUDITOR",
        "G1-ERROR",
        "G1-OUTPUT",
        "G1-FULL-CHROMIUM",
    ]
    for gate_id in required_gate_ids:
        assert gate_id in text


def test_active_auth_defaults_use_canonical_aminra_domain() -> None:
    root = repo_root()
    active_files = [
        root / "frontend" / "aminra-web" / "app" / "api" / "auth" / "login" / "route.ts",
        root / "scripts" / "pre_demo_check.sh",
    ]
    for path in active_files:
        text = path.read_text()
        assert "auth.aminra.org" in text
        assert "auth.silvergem.org" not in text
