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

# Save full GET response for inspection
with open("assistant_get_response.json", "w") as f:
    json.dump(data, f, indent=2)

print("Saved full GET response to assistant_get_response.json")
print("Top-level keys:", list(data.keys()))
if "data" in data:
    print("data keys:", list(data["data"].keys()))
    cf = data["data"].get("conversation_flow", {})
    print("\nconversation_flow keys:", list(cf.keys()))
    print("Total edges:", len(cf.get("edges", [])))
    print("Edge types:")
    for e in cf.get("edges", []):
        print(f"  {e.get('id')}: start={e.get('start_node_id')} end={e.get('end_node_id')}")
    print("\nn_triage edges:")
    for e in cf.get("edges", []):
        if e.get("start_node_id") == "n_triage":
            print(json.dumps(e, indent=2))
