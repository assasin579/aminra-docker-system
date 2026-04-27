import os
import pytest
import httpx


@pytest.fixture(scope="session")
def client():
    """HTTP client that talks to the running backend.

    Default targets the backend on the localhost-mapped host port (8100), but
    when pytest runs *inside* the backend container, the service is at port
    8000 instead. We auto-detect by trying 8000 first.
    """
    explicit = os.getenv("TEST_BACKEND_URL")
    if explicit:
        base_url = explicit
    elif os.path.exists("/.dockerenv"):
        base_url = "http://localhost:8000"
    else:
        base_url = "http://localhost:8100"
    with httpx.Client(base_url=base_url, timeout=60) as c:
        yield c


@pytest.fixture(scope="session")
def admin_credentials() -> tuple[str, str] | None:
    """Test login credentials. Set TEST_ADMIN_EMAIL + TEST_ADMIN_PASSWORD in env
    to enable live-login tests; otherwise dependent tests skip cleanly.
    """
    email = os.getenv("TEST_ADMIN_EMAIL")
    password = os.getenv("TEST_ADMIN_PASSWORD")
    if not email or not password:
        return None
    return email, password


@pytest.fixture(scope="session")
def admin_token(client, admin_credentials):
    """Live JWT for admin_credentials, or None if credentials aren't configured."""
    if admin_credentials is None:
        return None
    email, password = admin_credentials
    resp = client.post("/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None
