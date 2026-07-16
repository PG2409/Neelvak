import asyncio
import json
from fastapi.testclient import TestClient
from gateway.server import app

def test_what_is_python():
    client = TestClient(app)
    response = client.post("/api/chat", json={"prompt": "What is Python?"})
    print("STATUS:", response.status_code)
    data = response.json()
    print("OUTPUT:\n", data.get("output", "None"))
    print("METADATA:\n", data.get("metadata", {}))

if __name__ == "__main__":
    test_what_is_python()
