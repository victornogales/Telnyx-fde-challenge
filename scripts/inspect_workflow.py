import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )

body = resp.json()
cf = body.get("conversation_flow", {})

print("=== DEPLOYED WORKFLOW (from API) ===")
print(f"Start node: {cf.get('start_node_id')}")
print(f"Total nodes: {len(cf.get('nodes', []))}")
print(f"Total edges: {len(cf.get('edges', []))}")
print()

print("Edges from n_triage:")
for e in cf.get("edges", []):
    if e.get("start_node_id") == "n_triage":
        cond = e.get("condition", {})
        target = e.get("target", {}).get("node_id", "?")
        if cond.get("type") == "expression":
            expr = cond.get("expression", {})
            op = expr.get("op", "?")
            left = expr.get("left", {}).get("name", "?")
            right = expr.get("right", {}).get("value", "?")
            print(f"  {e['id']} -> {target}")
            print(f"    type: expression | {left} {op} '{right}'")
        elif cond.get("type") == "llm":
            print(f"  {e['id']} -> {target}")
            print(f"    type: llm | {cond.get('prompt', '')[:60]}")
        elif cond.get("type") == "default":
            print(f"  {e['id']} -> {target}")
            print(f"    type: default")
        else:
            print(f"  {e['id']} -> {target}")
            print(f"    type: {cond.get('type')}")
        print()

# Check if after_hours_mode is in dynamic variables
print("Dynamic variables configured:")
dv = body.get("dynamic_variables", {})
for k, v in sorted(dv.items()):
    print(f"  {k}: {v}")
print()
print(f"after_hours_mode present: {'after_hours_mode' in dv}")
print(f"refills_enabled present: {'refills_enabled' in dv}")
