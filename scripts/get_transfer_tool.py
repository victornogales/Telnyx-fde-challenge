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

# Find transfer tool
for t in a.get("tools", []):
    if t.get("type") == "transfer" or t.get("function", {}).get("name") == "transfer":
        print("Transfer tool found:")
        print(json.dumps(t, indent=2))
        break
else:
    print("No transfer tool found in assistant.tools")
    print("Tools:", [t.get("type") or t.get("function",{}).get("name") for t in a.get("tools", [])])
