import pytest

def test_upload_invalid_extension(client, admin_token):
    if not admin_token:
        pytest.skip("No admin token")
    # Try uploading a .exe file
    files = {"file": ("malware.exe", b"fake content", "application/octet-stream")}
    resp = client.post("/ingest", files=files)
    assert resp.status_code in [400, 413, 422]

def test_evaluate_without_file(client):
    resp = client.post("/evaluate")
    assert resp.status_code == 422  # missing required field
