import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

# Test the assistant via chat API to see if dynamic variables are applied
payload = {
    "content": "Hello, I want to refill my prescription",
    "conversation_id": f"debug-convo-{os.getpid()}",
    "dynamic_variables": {
        "telnyx_end_user_target": "+15550000001",
        "telnyx_agent_target": "+442045202115",
    }
}

with httpx.Client() as client:
    resp = client.post(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}/chat",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=30.0,
    )
    print(f"Status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2)[:2000])
