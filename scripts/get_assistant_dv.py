import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )
    data = resp.json().get("data", {})
    print("dynamic_variables:", json.dumps(data.get("dynamic_variables"), indent=2))
    print("dynamic_variables_webhook_timeout_ms:", data.get("dynamic_variables_webhook_timeout_ms"))
    print("webhook_url:", data.get("dynamic_variables_webhook_url"))
