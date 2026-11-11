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

print(f"Status: {resp.status_code}")
body = resp.json()
if resp.status_code == 200:
    a = body.get("data", body)
    print(f"greeting: {repr(a.get('greeting', 'N/A'))}")
    print(f"instructions length: {len(a.get('instructions', ''))}")
    cf = a.get("conversation_flow", {})
    print(f"start_node_id: {cf.get('start_node_id')}")
    print(f"nodes: {[n['id'] for n in cf.get('nodes', [])]}")
    edges = cf.get("edges", [])
    print(f"edges from n_disclosure: {[e['id'] for e in edges if e.get('start_node_id') == 'n_disclosure']}")
else:
    print(f"ERROR: {json.dumps(body, indent=2)}")
