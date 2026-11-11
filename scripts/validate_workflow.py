import json

j = json.load(open("assistant/workflow.json"))
nodes = {n["id"] for n in j["conversation_flow"]["nodes"]}
edges = j["conversation_flow"]["edges"]
print("nodes:", len(nodes), sorted(nodes))
print("edges:", len(edges))
missing = []
for e in edges:
    tid = e["target"]["node_id"]
    if tid not in nodes:
        missing.append(f"  MISSING TARGET: {e['id']} -> {tid}")
if missing:
    for m in missing:
        print(m)
else:
    print("OK - no missing targets")
