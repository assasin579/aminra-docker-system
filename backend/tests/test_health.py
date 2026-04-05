def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"

def test_stats(client):
    resp = client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "vectors" in data
    assert data["status"] == "green"

def test_topics(client):
    resp = client.get("/topics")
    assert resp.status_code == 200
    assert "topics" in resp.json()
