"""Step definitions for login.feature.

Sample only — demonstrates the pattern that feature teams will follow when
writing UAT scenarios for Tier-1 modules (IHC Meeting, Training Matrix,
Internal Audit, Hazard Analysis, CCP, Recall).

Run:
    pytest backend/tests/bdd/

Convention:
- Each .feature file paired with a test_*_steps.py
- @scenarios("file.feature") binds all scenarios; or use @scenario(...) per case
- @given/@when/@then refer back to Gherkin steps — keep them lean, defer to
  domain helpers + factories
- Skip cleanly if backend not reachable (so CI without live stack still runs)
"""

from __future__ import annotations

import os

import httpx
import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("login.feature")


@pytest.fixture
def context() -> dict:
    """Per-scenario state bag — accumulates request/response across steps."""
    return {}


def _backend_url() -> str:
    return os.getenv("TEST_BACKEND_URL") or (
        "http://localhost:8000" if os.path.exists("/.dockerenv") else "http://localhost:8100"
    )


@given('an active business owner "biz-demo-1@demo.aminra.vn" with password "DemoP@ss2026"')
def _owner_seeded(context):
    # In real Tier-1 step impls, this would assert via the live API or DB
    # that the seeded user exists. Here we record what we expect.
    context["email"] = "biz-demo-1@demo.aminra.vn"
    context["password"] = "DemoP@ss2026"


@given('the owner account status is "suspended"')
def _suspended(context):
    pytest.skip("Requires live DB write to suspend the account; out of sample scope")


@when("the owner submits valid credentials to /auth/login")
def _submit_valid(context):
    try:
        r = httpx.post(
            f"{_backend_url()}/auth/login",
            json={"email": context["email"], "password": context["password"], "role": "business"},
            timeout=10,
        )
    except httpx.RequestError:
        pytest.skip("Backend not reachable")
    context["response"] = r


@when('the owner submits the email but password "WrongPass!1"')
def _submit_wrong(context):
    try:
        r = httpx.post(
            f"{_backend_url()}/auth/login",
            json={"email": context["email"], "password": "WrongPass!1", "role": "business"},
            timeout=10,
        )
    except httpx.RequestError:
        pytest.skip("Backend not reachable")
    context["response"] = r


@then("the response status is 200")
def _ok(context):
    assert context["response"].status_code == 200


@then("the response status is 401")
def _unauth(context):
    assert context["response"].status_code == 401


@then("the response status is 403")
def _forbidden(context):
    assert context["response"].status_code == 403


@then("the response body has a non-empty access_token")
def _has_access(context):
    body = context["response"].json()
    assert body.get("access_token")


@then("the response body has a non-empty refresh_token")
def _has_refresh(context):
    body = context["response"].json()
    assert body.get("refresh_token")


@then('the response body contains "Email hoặc mật khẩu không đúng"')
def _msg_invalid(context):
    body = context["response"].json()
    assert "Email hoặc mật khẩu không đúng" in str(body)


@then('the response body contains "tạm khoá"')
def _msg_suspended(context):
    body = context["response"].json()
    assert "tạm khoá" in str(body)
