import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

# Update webhook timeout to 5000ms to handle cold-start latency
payload = {
    "dynamic_variables_webhook_timeout_ms": 5000,
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
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"webhook_timeout_ms: {data.get('dynamic_variables_webhook_timeout_ms')}")
