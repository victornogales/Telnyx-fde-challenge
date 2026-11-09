import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "assistant/workflow.json"

with open(path) as f:
    data = json.load(f)

for node in data["conversation_flow"]["nodes"]:
    if node.get("type") == "prompt":
        node["tools_mode"] = "append"
        node["tools"] = []

with open(path, "w") as f:
    json.dump(data, f, indent=2)

print("Updated", sum(1 for n in data["conversation_flow"]["nodes"] if n.get("type") == "prompt"), "prompt nodes to tools_mode=append")
