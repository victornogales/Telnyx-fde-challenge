import json

with open("assistant/workflow.json") as f:
    d = json.load(f)

edges = d["conversation_flow"]["edges"]
# Collect unique edge IDs, keeping first occurrence
seen = set()
unique_edges = []
for e in edges:
    eid = e["id"]
    if eid in seen:
        print(f"Removing duplicate: {eid}")
        continue
    seen.add(eid)
    unique_edges.append(e)

d["conversation_flow"]["edges"] = unique_edges

with open("assistant/workflow.json", "w") as f:
    json.dump(d, f, indent=2)

print("Total edges:", len(unique_edges))
print("n_triage edges:", [e["id"] for e in unique_edges if e.get("start_node_id") == "n_triage"])
