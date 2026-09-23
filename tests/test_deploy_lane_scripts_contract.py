from pathlib import Path
import subprocess


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() and (candidate / "docker-compose.yml").exists():
            return candidate
    raise AssertionError("could not locate repository root")


REPO_ROOT = repo_root()
DEPLOY_DIR = REPO_ROOT / "scripts" / "deploy"


def run_classifier(*paths: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(DEPLOY_DIR / "classify-change.sh"), "--paths", *paths],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_classifier_routes_frontend_only_changes_to_frontend_lane():
    result = run_classifier(
        "frontend/aminra-web/app/page.tsx",
        "frontend/aminra-web/components/Navbar.tsx",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "frontend-only"


def test_classifier_routes_backend_only_changes_to_backend_lane():
    result = run_classifier(
        "backend/app/routers/auth.py",
        "backend/tests/test_auth.py",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "backend-only"


def test_classifier_routes_docs_only_changes_to_docs_lane():
    result = run_classifier(
        "docs/qa/report.md",
        "README.md",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "docs-only"


def test_classifier_fails_closed_for_stateful_or_infra_changes():
    result = run_classifier(
        "docker-compose.yml",
        "backend/alembic/versions/047_new_table.py",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "infra-stateful"


def test_classifier_marks_mixed_frontend_backend_as_mixed():
    result = run_classifier(
        "frontend/aminra-web/app/page.tsx",
        "backend/app/main.py",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "mixed"


def test_frontend_deploy_script_is_no_deps_and_refuses_non_frontend_changes():
    script = DEPLOY_DIR / "frontend-only.sh"
    text = script.read_text()

    assert "classify-change.sh" in text
    assert "frontend-only" in text
    assert "docker compose build aminra-frontend" in text
    assert "docker compose up -d --no-deps aminra-frontend" in text
    assert "assert_unchanged_started_at" in text
    assert "aminra-backend" in text
    assert "postgres-db" in text
    assert "qdrant-db" in text
    assert "keycloak" in text
    assert "redis" in text


def test_backend_deploy_script_is_no_deps_and_refuses_stateful_changes():
    script = DEPLOY_DIR / "backend-only.sh"
    text = script.read_text()

    assert "classify-change.sh" in text
    assert "backend-only" in text
    assert "docker compose build aminra-backend" in text
    assert "docker compose up -d --no-deps aminra-backend" in text
    assert "assert_unchanged_started_at" in text
    assert "postgres-db" in text
    assert "qdrant-db" in text
    assert "redis" in text
    assert "keycloak" in text


def test_auto_deploy_dispatches_lane_without_prompting_for_safe_lanes():
    script = DEPLOY_DIR / "auto-deploy.sh"
    text = script.read_text()

    assert "case \"$LANE\"" in text
    assert "frontend-only.sh" in text
    assert "backend-only.sh" in text
    assert "docs-only" in text
    assert "infra-stateful" in text
    assert "mixed" in text
    assert "read -" not in text
    assert "--stateful-approved" in text
