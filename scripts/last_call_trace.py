#!/usr/bin/env python3
"""Fetch the latest AI conversation for the assistant and show routing details."""
import httpx, os, json

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"


def main():
    if not api_key:
        print("ERROR: set TELNYX_API_KEY", file=os.sys.stderr)
        os.sys.exit(1)

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    # List recent conversations
    url = f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}/conversations"
    with httpx.Client() as client:
        resp = client.get(url, headers=headers, params={"limit": 5}, timeout=30.0)
        data = resp.json().get("data", [])

    if not data:
        print("No conversations found.")
        return

    # Pick the most recent one
    conv = data[0]
    cid = conv["id"]
    created = conv.get("created_at", "?")
    print(f"Latest conversation: {cid} (created {created})")
    print()

    # Fetch full conversation with messages
    url = f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}/conversations/{cid}"
    with httpx.Client() as client:
        resp = client.get(url, headers=headers, params={"include_messages": "true"}, timeout=30.0)
        body = resp.json().get("data", {})

    msgs = body.get("messages", [])
    transitions = [m for m in msgs if m.get("type") == "transition"]
    tools = [m for m in msgs if m.get("type") == "tool"]
    user_utts = [m for m in msgs if m.get("role") == "user"]
    assistant_utts = [m for m in msgs if m.get("role") == "assistant"]

    print("=== Transitions (workflow routing) ===")
    for t in transitions:
        edge = t.get("edge", {})
        print(f"  {edge.get('source_node_id')} --[{edge.get('id')}]--> {edge.get('target_node_id')}")
    print()

    print("=== User utterances ===")
    for u in user_utts[-5:]:
        print(f"  User: {u.get('text', '')[:60]}")
    print()

    print("=== Assistant utterances ===")
    for a in assistant_utts[-5:]:
        print(f"  Assistant: {a.get('text', '')[:80]}")
    print()

    print("=== Tool calls ===")
    for t in tools:
        print(f"  Tool: {t.get('tool_name', '?')} -> {t.get('status', '?')}")
    print()

    # Check dynamic variables used in this call
    init = body.get("initialization", {})
    dv = init.get("dynamic_variables", {})
    print("=== Dynamic variables on this call ===")
    for k in sorted(dv.keys()):
        print(f"  {k}: {dv[k]}")


if __name__ == "__main__":
    main()
