import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        timeout=30.0,
    )

body = resp.json()
a = body.get("data", body)

print(f"Status: {resp.status_code}")
print(f"transfer: {json.dumps(a.get('transfer'), indent=2)}")
print(f"has transfer: {bool(a.get('transfer'))}")
