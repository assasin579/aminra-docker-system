"""Source contract for scripts/qa/repair-demo-accounts.sh.

Gate 1 browser/API tests depend on seeded business, provider, and platform-admin
Keycloak accounts. The repair script must reset all three accounts and update QA
credential env keys without leaking values.
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [here.parents[2], here.parents[1]]
    for candidate in candidates:
        if (candidate / "scripts" / "qa" / "repair-demo-accounts.sh").exists():
            return candidate
    raise AssertionError(f"repo root not found from {here}; candidates={candidates}")


def test_repair_demo_accounts_repairs_business_provider_and_admin_accounts() -> None:
    src = (repo_root() / "scripts" / "qa" / "repair-demo-accounts.sh").read_text()
    assert 'ensure_user("biz-demo-1@demo.aminra.vn", "business"' in src
    assert 'ensure_user("cb-demo@demo.aminra.vn", "cb_admin"' in src
    assert 'ensure_user("demo-platform-admin@demo.aminra.vn", "platform_admin"' in src


def test_repair_demo_accounts_exports_playwright_password_keys() -> None:
    src = (repo_root() / "scripts" / "qa" / "repair-demo-accounts.sh").read_text()
    for key in [
        'existing["DEMO_PW"]',
        'existing["PW_BIZ_PASSWORD"]',
        'existing["PROVIDER_DEMO_PW"]',
        'existing["PW_PROVIDER_PASSWORD"]',
        'existing["TEST_ADMIN_PASSWORD"]',
    ]:
        assert key in src


def test_repair_demo_accounts_does_not_print_generated_password_values() -> None:
    src = (repo_root() / "scripts" / "qa" / "repair-demo-accounts.sh").read_text()
    assert "password=REDACTED" in src
    assert "values=REDACTED" in src
    assert "print(new_pw" not in src
