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

print("=== Assistant Config ===")
print(f"version_id: {data.get('version_id')}")
print(f"greeting: {data.get('greeting')!r}")
print(f"webhook_url: {data.get('dynamic_variables_webhook_url')!r}")
print(f"webhook_timeout_ms: {data.get('dynamic_variables_webhook_timeout_ms')!r}")
print(f"dynamic_variables defaults: {json.dumps(data.get('dynamic_variables', {}), indent=2)}")

cf = data.get("conversation_flow", {})
print(f"\n=== Workflow ===")
print(f"start_node_id: {cf.get('start_node_id')}")
print(f"node count: {len(cf.get('nodes', []))}")
print(f"edge count: {len(cf.get('edges', []))}")

n_disclosure = next((n for n in cf.get('nodes', []) if n['id'] == 'n_disclosure'), None)
if n_disclosure:
    print(f"\nn_disclosure message: {n_disclosure.get('message')!r}")
else:
    print("\nWARNING: n_disclosure not found!")

# Check n_triage
n_triage = next((n for n in cf.get('nodes', []) if n['id'] == 'n_triage'), None)
if n_triage:
    print(f"\nn_triage instructions preview (first 120 chars): {n_triage.get('instructions', '')[:120]!r}")
