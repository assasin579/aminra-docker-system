import pytest

def test_chat_basic(client):
    resp = client.post("/chat", json={
        "question": "Halal la gi?",
        "top_k": 3
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["answer"]) > 50

def test_chat_empty_question(client):
    resp = client.post("/chat", json={"question": "", "top_k": 3})
    assert resp.status_code == 400

def test_chat_long_question(client):
    resp = client.post("/chat", json={"question": "a" * 1001, "top_k": 3})
    assert resp.status_code == 400
