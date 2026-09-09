from __future__ import annotations

import subprocess
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent if (BACKEND_ROOT.parent / "scripts").exists() else BACKEND_ROOT
SCRIPT = REPO_ROOT / "scripts" / "qa" / "check-keycloak-account-login.sh"


def test_keycloak_account_login_smoke_script_exists_and_accepts_json_credentials():
    """Regression guard for demo credentials containing shell metacharacters.

    Custom demo accounts must be verifiable without hardcoding credentials in the
    repository or splitting on punctuation such as ';' in the password.
    """
    text = SCRIPT.read_text()

    assert "DEMO_LOGIN_SMOKE_ACCOUNTS_JSON" in text
    assert "json.load" in text
    assert "--data-urlencode" in text
    assert "password" in text


def test_keycloak_account_login_smoke_script_never_echoes_passwords():
    text = SCRIPT.read_text()

    assert "REDACTED" in text
    assert "set -x" not in text
    assert "echo \"$password\"" not in text
    assert "echo ${password}" not in text


def test_keycloak_account_login_smoke_script_has_safe_dry_run_for_special_chars():
    password = "VH@#3r79WVwetBEx2Sgk;"
    result = subprocess.run(
        ["bash", str(SCRIPT), "--dry-run"],
        input='[{"email":"abc@demo.com","password":"%s","expected_role":"business"}]' % password,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        timeout=10,
    )

    assert result.returncode == 0
    assert "abc@demo.com" in result.stdout
    assert "REDACTED" in result.stdout
    assert password not in result.stdout
    assert result.stderr == ""
