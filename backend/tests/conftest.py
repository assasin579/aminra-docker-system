import os
import pytest
import httpx


@pytest.fixture(scope="session")
def client():
    """HTTP client that talks to the running backend via Docker."""
    base_url = os.getenv("TEST_BACKEND_URL", "http://localhost:8100")
    with httpx.Client(base_url=base_url, timeout=60) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    """Get admin JWT token."""
    resp = client.post("/auth/login", json={
        "email": "admin@aminra.com",
        "password": "admin123!"
    })
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None
