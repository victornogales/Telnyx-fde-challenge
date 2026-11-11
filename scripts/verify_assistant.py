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

cf = data.get("conversation_flow", {})

print("=== n_triage edges (deployed) ===")
for i, e in enumerate(cf.get("edges", [])):
    if e.get("start_node_id") == "n_triage":
        cond = e.get("condition", {})
        target = e.get("target", {}).get("node_id", "?")
        print(f"  {i+1}. {e['id']} -> {target} | {cond.get('type')}")

# Check dynamic variable defaults
print("\n=== Dynamic variable defaults ===")
dv = data.get("dynamic_variables", {})
for k in sorted(dv.keys()):
    print(f"  {k}: {dv[k]!r} (type: {type(dv[k]).__name__})")

print()
print("after_hours_mode default type:", type(dv.get("after_hours_mode")).__name__)
