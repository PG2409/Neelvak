import requests
import json

payload = {
    "prompt": "Hello! My SSN is 123-45-6789 and my email is test@example.com. Please analyze this infrastructure.",
    "conversation_id": "test_pii_1"
}

resp = requests.post("http://localhost:8000/api/chat", json=payload)
data = resp.json()

print("Status:", resp.status_code)
print("Output:", data.get("output", ""))
print("\nTelemetry:")
for log in data.get("telemetry", []):
    print("  ", log)
