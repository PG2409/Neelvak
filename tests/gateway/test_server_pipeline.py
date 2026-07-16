import pytest
from fastapi.testclient import TestClient
from gateway.server import app

def test_chat_pipeline_valid_request():
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"prompt": "Hello world"})
        assert response.status_code == 200
        data = response.json()
        assert "winner" in data
        assert "output" in data
        assert "processes" in data

def test_chat_pipeline_rate_limit():
    from gateway.server import session_manager
    session_manager._rate_limits.clear()
    with TestClient(app) as client:
        # Attempt to hit the rate limit
        for _ in range(16):
            resp = client.post("/api/chat", json={"prompt": "Spam"})
        
        assert resp.status_code == 429
        assert "Rate Limit Exceeded" in resp.json()["detail"]
    session_manager._rate_limits.clear()

def test_chat_pipeline_invalid_payload():
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"not_prompt": "Hello"})
        assert response.status_code == 422
