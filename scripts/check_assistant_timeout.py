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
    
    # Check the actual assistant fields
    for key in ["dynamic_variables", "dynamic_variables_webhook_timeout_ms", 
                "dynamic_variables_webhook_url", "telephony_settings"]:
        val = data.get(key)
        print(f"{key}: {json.dumps(val, indent=2)[:200] if val is not None else val}")
