"""Source contracts for CB Trust Core credentialed browser UAT runner.

CB Trust Core is not accepted for sandbox demo without a secret-safe browser lane
that proves the decision, conflict, and complaint/appeal routes with real
Keycloak-issued role tokens and durable UI evidence.
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parents[2], here.parents[1]):
        if (candidate / "scripts" / "qa").exists():
            return candidate
    raise AssertionError(f"repo root not found from {here}")


def test_cb_trust_browser_uat_runner_exists_and_is_secret_safe() -> None:
    script = repo_root() / "scripts" / "qa" / "run-cb-trust-browser-uat.sh"
    assert script.exists(), "CB Trust browser UAT runner must exist"
    text = script.read_text()
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert ".qa/aminra-demo-credentials.env" in text
    assert "repair-demo-accounts.sh" in text
    assert "set -x" not in text
    assert "REDACTED" in text
    assert "PW_PROVIDER_PASSWORD" in text
    assert "PW_BIZ_PASSWORD" in text


def test_cb_trust_browser_uat_runner_executes_maintained_playwright_spec() -> None:
    root = repo_root()
    script = root / "scripts" / "qa" / "run-cb-trust-browser-uat.sh"
    spec = root / "frontend" / "aminra-web" / "e2e" / "cb-trust-core-live-uat.spec.ts"
    assert spec.exists(), "CB Trust live UAT spec must be maintained under frontend/aminra-web/e2e"
    text = script.read_text()
    spec_text = spec.read_text()
    for expected in [
        "cb-trust-core-live-uat.spec.ts",
        "UAT_EVIDENCE_DIR",
        "status.tsv",
        "report.md",
        "cb-trust-browser-uat",
    ]:
        assert expected in text
    for expected in [
        "/api/api/conflicts",
        "/api/api/complaints",
        "/api/api/certification-decisions",
        "Conflict-of-Interest Register",
        "Complaints & Appeals",
        "qa-cb-trust",
    ]:
        assert expected in spec_text


def test_cb_trust_browser_uat_runner_records_acceptance_lanes() -> None:
    script = repo_root() / "scripts" / "qa" / "run-cb-trust-browser-uat.sh"
    text = script.read_text()
    for expected in [
        "provider conflict declaration/review/override",
        "business complaint create/list and provider transition",
        "certification decision route denies unauthorized business creation",
        "static CB Trust UI pages render acceptance markers",
    ]:
        assert expected in text
