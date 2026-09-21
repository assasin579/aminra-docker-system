"""Source contracts for module activation browser UAT runner.

The activation-request workflow is not fully accepted until a safe credentialed
browser lane proves business locked-screen request creation and admin queue review
without committing or printing secrets.
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [here.parents[2], here.parents[1]]
    for candidate in candidates:
        if (candidate / "scripts" / "qa").exists():
            return candidate
    raise AssertionError(f"repo root not found from {here}; candidates={candidates}")


def test_module_activation_browser_uat_runner_exists_and_sources_gitignored_credentials() -> None:
    script = repo_root() / "scripts" / "qa" / "run-module-activation-browser-uat.sh"
    assert script.exists(), "module activation browser UAT runner must exist"
    text = script.read_text()
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert ".qa/aminra-demo-credentials.env" in text
    assert "repair-demo-accounts.sh" in text
    assert "set -x" not in text
    assert "REDACTED" in text or "without secrets" in text


def test_module_activation_browser_uat_runner_executes_business_and_admin_flow() -> None:
    script = repo_root() / "scripts" / "qa" / "run-module-activation-browser-uat.sh"
    text = script.read_text()
    for expected in [
        "module-guard-live-uat.spec.ts",
        "UAT_EVIDENCE_DIR",
        "PW_BIZ_PASSWORD",
        "TEST_ADMIN_PASSWORD",
        "status.tsv",
        "report.md",
        "activation-request-browser-uat",
    ]:
        assert expected in text


def test_module_activation_browser_uat_runner_records_admin_queue_acceptance() -> None:
    script = repo_root() / "scripts" / "qa" / "run-module-activation-browser-uat.sh"
    text = script.read_text()
    for expected in [
        "business locked-route CTA creates request",
        "admin queue shows SLA/notification cues",
        "admin rejects QA request for cleanup",
    ]:
        assert expected in text
