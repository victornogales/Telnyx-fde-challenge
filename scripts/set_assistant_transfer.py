import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

payload = {
    "transfer": {
        "destination": "+15550000001"  # Maria's number = pharmacist destination for tests
    }
}

with httpx.Client() as client:
    resp = client.patch(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=30.0,
    )

body = resp.json()
print(f"Status: {resp.status_code}")
print(f"transfer: {json.dumps(body.get('data',{}).get('transfer'), indent=2)}")
