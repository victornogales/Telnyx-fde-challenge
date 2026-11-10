import json, httpx, os

payload = {
    "instructions": (
        "You are the Maple Pharmacy voice assistant.\n\n"
        "IMPORTANT: Do NOT greet the caller with 'Hello' or 'Welcome' — the workflow handles the greeting. "
        "After the caller speaks, be concise and friendly. Limit to 1-2 sentence responses and always end with a question."
    ),
}

api_key = os.environ.get("TELNYX_API_KEY", "")

with httpx.Client() as client:
    resp = client.post(
        "https://api.telnyx.com/v2/ai/assistants/assistant-9befc905-0e48-42f9-b65f-ae91b269bb65",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        json=payload,
        timeout=30.0,
    )

print(f"Status: {resp.status_code}")
body = resp.json()

if resp.status_code == 200:
    print("SUCCESS!")
    print(f"  instructions: {body.get('instructions', 'N/A')[:120]}...")
else:
    print(f"ERROR: {json.dumps(body, indent=2)}")
