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

# Top level might be the assistant directly
if "conversation_flow" in body:
    cf = body["conversation_flow"]
    print("conversation_flow in top level")
    print("Nodes:", [n["id"] for n in cf.get("nodes", [])])
    print("\nEdges from n_triage:")
    for e in cf.get("edges", []):
        if e.get("start_node_id") == "n_triage":
            print(f"  {e['id']} -> {e['target']['node_id']} ({e['condition']['type']})")
else:
    print("No conversation_flow found in top level")
    data = body.get("data", {})
    if isinstance(data, dict) and "conversation_flow" in data:
        cf = data["conversation_flow"]
        print("conversation_flow in data")
        for e in cf.get("edges", []):
            if e.get("start_node_id") == "n_triage":
                print(f"  {e['id']} -> {e['target']['node_id']} ({e['condition']['type']})")
