import json

with open("assistant/workflow.json", "r", encoding="utf-8") as f:
    d = json.load(f)

# Fix mojibake in n_triage and n_faq instructions
for node in d["conversation_flow"]["nodes"]:
    if "instructions" in node:
        instr = node["instructions"]
        # Replace garbled UTF-8 sequences with correct characters
        # \u00e2\u2020\u2019 is the garbled representation of '→'
        # \u00e2\u20ac\u201d is the garbled representation of '—'
        instr = instr.replace("\u00e2\u2020\u2019", "→")
        instr = instr.replace("\u00e2\u20ac\u201d", "—")
        node["instructions"] = instr

# Add outgoing edges from n_after_hours
new_edges = [
    {
        "id": "e_after_hours_human",
        "start_node_id": "n_after_hours",
        "target": {"type": "node", "node_id": "n_transfer_prompt"},
        "condition": {"type": "llm", "prompt": "The caller asks for a human or pharmacist"}
    },
    {
        "id": "e_after_hours_closing",
        "start_node_id": "n_after_hours",
        "target": {"type": "node", "node_id": "n_closing"},
        "condition": {"type": "llm", "prompt": "The caller is done or says goodbye"}
    },
]

# Insert before e_transfer_failed (the last few edges)
insert_idx = None
for i, e in enumerate(d["conversation_flow"]["edges"]):
    if e["id"] == "e_transfer_failed":
        insert_idx = i
        break

if insert_idx is not None:
    for e in reversed(new_edges):
        d["conversation_flow"]["edges"].insert(insert_idx, e)

with open("assistant/workflow.json", "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)

print("Fixed mojibake and added n_after_hours edges.")
print("Nodes:", [n["id"] for n in d["conversation_flow"]["nodes"]])
print("n_after_hours edges:", [e["id"] for e in d["conversation_flow"]["edges"] if e.get("start_node_id") == "n_after_hours"])
