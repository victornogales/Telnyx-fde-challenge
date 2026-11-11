import json

with open("assistant/workflow.json") as f:
    d = json.load(f)

nodes = d["conversation_flow"]["nodes"]
edges = d["conversation_flow"]["edges"]

# 1. Insert n_transfer_prompt right before n_transfer in the nodes list
prompt_node = {
    "id": "n_transfer_prompt",
    "type": "speak",
    "message": "I'll transfer you now. Please hold."
}

# Find index of n_transfer
for i, n in enumerate(nodes):
    if n["id"] == "n_transfer":
        nodes.insert(i, prompt_node)
        break

# 2. Update human-initiated edges to point to n_transfer_prompt instead of n_transfer
human_edges = ["e_triage_human", "e_verify_human", "e_faq_transfer"]
for e in edges:
    if e["id"] in human_edges:
        if e.get("target", {}).get("node_id") == "n_transfer":
            e["target"]["node_id"] = "n_transfer_prompt"

# 3. Add edge from n_transfer_prompt -> n_transfer (default)
prompt_edge = {
    "id": "e_transfer_prompt",
    "start_node_id": "n_transfer_prompt",
    "target": {"type": "node", "node_id": "n_transfer"},
    "condition": {"type": "default"}
}

# Insert right after the last human edge
for i, e in enumerate(edges):
    if e["id"] == "e_faq_transfer":
        edges.insert(i + 1, prompt_edge)
        break

with open("assistant/workflow.json", "w") as f:
    json.dump(d, f, indent=2)

print("Added n_transfer_prompt. Nodes:", [n["id"] for n in nodes])
print("Edges targeting n_transfer_prompt:", [e["id"] for e in edges if e.get("target",{}).get("node_id") == "n_transfer_prompt"])
