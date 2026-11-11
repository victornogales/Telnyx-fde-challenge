import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

# Check shared tools attached to the assistant
with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )
    data = resp.json()

print("=== Tools in assistant ===")
for t in data.get("tools", []):
    print(f"  {t.get('tool_id')} type={t.get('type')} shared={t.get('shared')}")

# Check if transfer tool exists at all
with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/tools",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )
    tools_data = resp.json()
    if "data" in tools_data:
        tools_data = tools_data["data"]
    elif isinstance(tools_data, list):
        pass
    else:
        tools_data = tools_data.get("data", [])

print(f"\n=== All account tools ===")
for t in tools_data:
    tid = t.get("id") or t.get("tool_id", "")
    ttype = t.get("type", "")
    print(f"  {tid} type={ttype} name={t.get('name', '')}")
