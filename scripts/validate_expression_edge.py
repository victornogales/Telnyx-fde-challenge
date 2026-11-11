import json, httpx, os, time

api_key = os.environ.get("TELNYX_API_KEY", "")

# ── 1. CREATE a minimal test assistant ────────────────────────────────────
payload = {
    "name": "ExpressionEdgeValidator",
    "instructions": "You are a routing validator.",
    "telephony_settings": {"default_texml_app_id": ""},
    "dynamic_variables": {
        "test_flag": "false"
    },
    "conversation_flow": {
        "start_node_id": "n_start",
        "nodes": [
            {
                "id": "n_start",
                "type": "speak",
                "message": "Hello, starting test."
            },
            {
                "id": "n_triage",
                "type": "prompt",
                "instructions": "The user will say something. Route based on variable.",
                "instructions_mode": "replace"
            },
            {
                "id": "n_flag_true",
                "type": "speak",
                "message": "FLAG IS TRUE"
            },
            {
                "id": "n_flag_false",
                "type": "speak",
                "message": "FLAG IS FALSE"
            }
        ],
        "edges": [
            {
                "id": "e_start_triage",
                "start_node_id": "n_start",
                "target": {"type": "node", "node_id": "n_triage"},
                "condition": {"type": "default"}
            },
            {
                "id": "e_triage_flag_true",
                "start_node_id": "n_triage",
                "target": {"type": "node", "node_id": "n_flag_true"},
                "condition": {
                    "type": "expression",
                    "expression": {
                        "type": "comparison",
                        "op": "==",
                        "left": {"type": "variable", "name": "test_flag"},
                        "right": {"type": "string_literal", "value": "true"}
                    }
                }
            },
            {
                "id": "e_triage_flag_false",
                "start_node_id": "n_triage",
                "target": {"type": "node", "node_id": "n_flag_false"},
                "condition": {
                    "type": "llm",
                    "prompt": "Any other input"
                }
            },
            {
                "id": "e_true_end",
                "start_node_id": "n_flag_true",
                "target": {"type": "node", "node_id": "n_triage"},
                "condition": {"type": "default"}
            },
            {
                "id": "e_false_end",
                "start_node_id": "n_flag_false",
                "target": {"type": "node", "node_id": "n_triage"},
                "condition": {"type": "default"}
            }
        ]
    }
}

print("Creating temporary validator assistant...")
with httpx.Client() as client:
    resp = client.post(
        "https://api.telnyx.com/v2/ai/assistants",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=30.0,
    )
    print(f"Create status: {resp.status_code}")
    body = resp.json()
    assistant = body  # response body is the assistant object directly
    assistant_id = assistant.get("id", "")
    print(f"Assistant ID: {assistant_id}")

if not assistant_id:
    print(json.dumps(body, indent=2))
    raise SystemExit("Failed to create validator assistant")

# ── 2. TEST with test_flag=false ──────────────────────────────────────────
print("\nTest 1: test_flag=false")
conv_id = f"validator-{int(time.time())}-a"
with httpx.Client() as client:
    resp = client.post(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}/chat",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "content": "Say something",
            "conversation_id": conv_id,
        },
        timeout=30.0,
    )
    print(f"Chat status: {resp.status_code}")
    data = resp.json()
    text = data.get("content", "")
    print(f"Response: {text!r}")

# Also try to infer routing by getting conversation messages
print("Getting conversation messages...")
with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}/conversations/{conv_id}/messages",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )
    if resp.status_code == 200:
        messages = resp.json().get("data", {}).get("messages", [])
        print(f"Messages: {len(messages)}")
        for m in messages:
            print(f"  [{m.get('role')}] {m.get('content', '')!r}")
    else:
        print(f"Could not get messages: {resp.status_code}")

# ── 3. PATCH test_flag=true ───────────────────────────────────────────────
print("\nPatching test_flag to true")
with httpx.Client() as client:
    resp = client.patch(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={"dynamic_variables": {"test_flag": "true"}},
        timeout=30.0,
    )
    print(f"Patch status: {resp.status_code}")

# ── 4. TEST with test_flag=true ───────────────────────────────────────────
print("Test 2: test_flag=true")
conv_id2 = f"validator-{int(time.time())}-b"
with httpx.Client() as client:
    resp = client.post(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}/chat",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "content": "Say something else",
            "conversation_id": conv_id2,
        },
        timeout=30.0,
    )
    print(f"Chat status: {resp.status_code}")
    data = resp.json()
    text = data.get("content", "")
    print(f"Response: {text!r}")

with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}/conversations/{conv_id2}/messages",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )
    if resp.status_code == 200:
        messages = resp.json().get("data", {}).get("messages", [])
        print(f"Messages: {len(messages)}")
        for m in messages:
            print(f"  [{m.get('role')}] {m.get('content', '')!r}")
    else:
        print(f"Could not get messages: {resp.status_code}")

# ── 5. CLEANUP ────────────────────────────────────────────────────────────
print("\nDeleting temporary validator assistant...")
with httpx.Client() as client:
    resp = client.delete(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )
    print(f"Delete status: {resp.status_code}")

print("\n=== RESULTS ===")
print("If test 1 said 'FLAG IS FALSE' and test 2 said 'FLAG IS TRUE': expression edges WORK")
print("If both said the same thing: expression edges with custom variables are BROKEN on this platform")
