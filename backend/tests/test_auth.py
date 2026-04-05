import pytest

def test_login_success(client):
    resp = client.post("/auth/login", json={
        "email": "admin@aminra.com",
        "password": "admin123!"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data

def test_login_wrong_password(client):
    resp = client.post("/auth/login", json={
        "email": "admin@aminra.com",
        "password": "wrongpassword"
    })
    assert resp.status_code == 401

def test_login_nonexistent_user(client):
    resp = client.post("/auth/login", json={
        "email": "nonexistent@test.com",
        "password": "whatever"
    })
    assert resp.status_code == 401

def test_me_authenticated(client, admin_token):
    if not admin_token:
        pytest.skip("No admin token")
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@aminra.com"

def test_me_unauthenticated(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401
