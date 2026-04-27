"""Live-DB tests for /auth endpoints.

Login-success tests require real credentials. Set TEST_ADMIN_EMAIL +
TEST_ADMIN_PASSWORD to enable; otherwise these tests skip cleanly so CI
doesn't fail on environments without seeded users.
"""
import pytest


def test_login_success(client, admin_credentials):
    if admin_credentials is None:
        pytest.skip("TEST_ADMIN_EMAIL/TEST_ADMIN_PASSWORD not set")
    email, password = admin_credentials
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data


def test_login_wrong_password(client, admin_credentials):
    if admin_credentials is None:
        pytest.skip("TEST_ADMIN_EMAIL/TEST_ADMIN_PASSWORD not set")
    email, _ = admin_credentials
    resp = client.post("/auth/login", json={
        "email": email,
        "password": "definitely-not-the-real-password-xyz",
    })
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post("/auth/login", json={
        "email": "nonexistent@test.com",
        "password": "whatever"
    })
    assert resp.status_code == 401


def test_me_authenticated(client, admin_token, admin_credentials):
    if not admin_token:
        pytest.skip("No admin token (set TEST_ADMIN_EMAIL/PASSWORD)")
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    expected_email, _ = admin_credentials
    assert data["email"].lower() == expected_email.lower()


def test_me_unauthenticated(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401
