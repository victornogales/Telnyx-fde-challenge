import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )
    full = resp.json()

print(f"Status: {resp.status_code}")
print(f"Top-level keys: {list(full.keys())}")
print(f"\nFull response (truncated):")
print(json.dumps(full, indent=2)[:2000])
