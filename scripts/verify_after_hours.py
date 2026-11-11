import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )
    data = resp.json()

print(f"version_id: {data.get('version_id')}")
print(f"after_hours_mode: {data.get('dynamic_variables', {}).get('after_hours_mode')}")
print(f"webhook_timeout_ms: {data.get('dynamic_variables_webhook_timeout_ms')}")

cf = data.get("conversation_flow", {})
print(f"\nnodes: {[n['id'] for n in cf.get('nodes', [])]}")
print(f"\nedges from n_triage:")
for e in cf.get("edges", []):
    if e.get("start_node_id") == "n_triage":
        cond = e.get("condition", {})
        print(f"  {e['id']}: {cond.get('type')} -> {e['target']['node_id']}")

print(f"\nedges from n_after_hours:")
for e in cf.get("edges", []):
    if e.get("start_node_id") == "n_after_hours":
        cond = e.get("condition", {})
        print(f"  {e['id']}: {cond.get('type')} -> {e['target']['node_id']}")
