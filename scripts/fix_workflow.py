import json

with open("assistant/workflow.json") as f:
    d = json.load(f)

edges = d["conversation_flow"]["edges"]
# Remove n_triage edges
n_triage = [e for e in edges if e["start_node_id"] == "n_triage"]
others   = [e for e in edges if e["start_node_id"] != "n_triage"]

print("Current n_triage edges:", [e["id"] for e in n_triage])

# Build correct ordered n_triage edges
correct_n_triage = [
    {
        "id": "e_triage_timeout",
        "start_node_id": "n_triage",
        "target": {"type": "node", "node_id": "n_transfer"},
        "condition": {
            "type": "expression",
            "expression": {
                "type": "comparison", "op": ">=",
                "left": {"type": "variable", "name": "telnyx_conversation_duration_secs"},
                "right": {"type": "string_literal", "value": "300"}
            }
        }
    },
    {
        "id": "e_triage_human",
        "start_node_id": "n_triage",
        "target": {"type": "node", "node_id": "n_transfer"},
        "condition": {
            "type": "llm",
            "prompt": "The caller asks for a pharmacist or a human, or is frustrated"
        }
    },
    {
        "id": "e_triage_locked",
        "start_node_id": "n_triage",
        "target": {"type": "node", "node_id": "n_locked"},
        "condition": {
            "type": "expression",
            "expression": {
                "type": "comparison", "op": "==",
                "left": {"type": "variable", "name": "account_locked"},
                "right": {"type": "string_literal", "value": "true"}
            }
        }
    },
    {
        "id": "e_triage_after_hours",
        "start_node_id": "n_triage",
        "target": {"type": "node", "node_id": "n_after_hours"},
        "condition": {
            "type": "expression",
            "expression": {
                "type": "comparison", "op": "==",
                "left": {"type": "variable", "name": "after_hours_mode"},
                "right": {"type": "string_literal", "value": "true"}
            }
        }
    },
    {
        "id": "e_triage_refill",
        "start_node_id": "n_triage",
        "target": {"type": "node", "node_id": "n_verify"},
        "condition": {"type": "llm", "prompt": "The caller wants to refill a prescription"}
    },
    {
        "id": "e_triage_status",
        "start_node_id": "n_triage",
        "target": {"type": "node", "node_id": "n_verify"},
        "condition": {"type": "llm", "prompt": "The caller asks whether an order or refill is ready"}
    },
    {
        "id": "e_triage_faq",
        "start_node_id": "n_triage",
        "target": {"type": "node", "node_id": "n_faq"},
        "condition": {"type": "llm", "prompt": "The caller asks about hours, location, or what a medication is for"}
    },
]

# Insert correct n_triage edges right after the disclosure edge
new_edges = []
for e in others:
    new_edges.append(e)
    if e.get("target",{}).get("node_id") == "n_triage":
        new_edges.extend(correct_n_triage)

d["conversation_flow"]["edges"] = new_edges

with open("assistant/workflow.json", "w") as f:
    json.dump(d, f, indent=2)

print("Fixed. New n_triage edges:", [e["id"] for e in correct_n_triage])
print("Total edges:", len(new_edges))
