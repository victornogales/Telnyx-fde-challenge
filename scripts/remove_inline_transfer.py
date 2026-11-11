import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

# First, get current assistant
with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )
    cur = resp.json().get("data", {})

# Keep only hangup tool
tools = [t for t in (cur.get("tools") or []) if t.get("type") == "hangup"]

payload = {"tools": tools}

with httpx.Client() as client:
    resp = client.patch(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=30.0,
    )
    print("Status:", resp.status_code)
    if resp.status_code != 200:
        print(resp.text)
    else:
        data = resp.json().get("data", {})
        print("Tools:", [t.get("type") for t in data.get("tools", [])])
