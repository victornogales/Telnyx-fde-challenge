# RefillLine Assistant Workflow Notes

> This document mirrors the design rationale that used to live as comments inside `workflow.json`. The JSON itself is kept comment-free so it can be shipped directly via the Assistants API.

## Upload command

```bash
PATCH https://api.telnyx.com/v2/ai/assistants/{assistant_id}
Content-Type: application/json
Authorization: Bearer $TELNYX_API_KEY
```

Body: the contents of `workflow.json` (the `conversation_flow` object, wrapped in an object as the API expects).

---

## Tool naming caveat

All MCP tool names in the node instructions are prefixed with `refill__` (e.g. `refill__verify_identity`). This assumes the MCP server was registered with `--name refill` (or the Portal equivalent). If your actual server name is different, replace `refill__` with `<your_name>__` everywhere.

**How to verify the real prefix:**

```bash
curl -s https://api.telnyx.com/v2/ai/mcp_servers \
  -H "Authorization: Bearer $TELNYX_API_KEY" | jq '.data[].name'
```

Or run `telnyx-acp tools` and look at the names the model sees.

**Automated fix:** A script at `scripts/update-workflow-prefix.py` can fetch your MCP server name from the API and rewrite the JSON automatically.

```bash
# Discover and apply
python scripts/update-workflow-prefix.py --fetch

# Or specify the name directly
python scripts/update-workflow-prefix.py --name refill --dry-run

# Discover + push to assistant (requires ASSISTANT_ID env or --assistant-id)
python scripts/update-workflow-prefix.py --fetch --assistant-id <id>
```

---

## Known platform limitation (MCP tool scoping in workflows)

> A Portal UI bug means MCP tools **do not appear** in the Prompt-node "Tools" tab dropdown. They only appear in the Assistant-level "Allowed Tools" page under the MCP server integration.

**Workaround:** We allow all 6 MCP tools globally on the assistant, and rely on node instructions to constrain which tool the model calls in each node.

---

## Node design choices

| Node | Type | Instructions mode | Purpose |
|---|---|---|---|
| `n_disclosure` | speak | n/a | Verbatim recording disclosure |
| `n_triage` | prompt | append | Route caller intent (refill / status / FAQ / human) |
| `n_verify` | prompt | **replace** | Identity verification by DOB. `replace` prevents the base persona from leaking in and trying to be helpful. |
| `n_refill` | prompt | append | List prescriptions, caller chooses |
| `n_confirm` | prompt | append | Confirm choice, call `refill__request_refill` |
| `n_status` | prompt | append | Read back open refill status |
| `n_faq` | prompt | append | Pharmacy hours / medication info |
| `n_after_hours` | prompt | append | Closed-hours info only |
| `n_locked` | speak | n/a | Lockout message, then transfer |
| `n_transfer` | tool | n/a | Shared transfer tool |
| `n_transfer_failed` | speak | n/a | Fallback if transfer fails |
| `n_closing` | speak | n/a | Confirmation + goodbye |
| `n_hangup` | tool | n/a | Shared hangup tool |

### Why `replace` on `n_verify`?

Verification is the security boundary. The base persona says "be helpful, answer questions", and we don't want that leaking in. With `replace`, the node does exactly one thing.

### Why `append` elsewhere?

Persona, tone and safety rules ("never give medical advice") should apply everywhere, so we add the node's task on top of them.

---

## Edge evaluation order

Variable-comparison edges are evaluated **before** the model turn on voice calls, and **take precedence** over LLM edges.

### From `n_triage` (expression edges first)

1. `account_locked == "true"` → `n_locked`
2. `after_hours_mode == "true"` → `n_after_hours`
3. `telnyx_conversation_duration_secs >= 300` → `n_transfer`
4. LLM: "Caller wants to refill" → `n_verify`
5. LLM: "Caller asks status" → `n_verify`
6. LLM: "Caller asks hours/location/medication" → `n_faq`
7. LLM: "Caller asks for human" → `n_transfer`

### From `n_verify`

- `account_locked == "true"` → `n_locked`
- `telnyx_conversation_duration_secs >= 300` → `n_transfer`
- LLM "human" → `n_transfer`
- LLM "verified + wants refill" → `n_refill`
- LLM "verified + wants status" → `n_status`

### Other key flows

- `n_refill` → `n_confirm` (chosen) or `n_triage` (declined)
- `n_confirm` → `n_closing` (success) or `n_refill` (declined)
- `n_status` → `n_closing` (done) or `n_refill` (wants refill)
- `n_faq` → `n_verify` (wants refill/status), `n_closing` (done), `n_transfer` (human)
- `n_locked` → `n_transfer` (default)
- `n_transfer` → `n_transfer_failed` (default, failure path)
- `n_transfer_failed` → `n_hangup`
- `n_closing` → `n_hangup`

---

## Tool scoping (assistant-level)

Since per-node scoping is broken for MCP tools in the Portal, set the allowed tools globally on the MCP server integration:

- `refill__verify_identity`
- `refill__list_prescriptions`
- `refill__request_refill`
- `refill__get_refill_status`
- `refill__get_medication_info`
- `refill__get_pharmacy_info`

Plus built-in shared tools:
- `hangup`
- `transfer`

---

## Variables used in expressions

All comparison values must be **strings** on voice channels:

- `account_locked`: `"true"` / `"false"`
- `after_hours_mode`: `"true"` / `"false"`
- `telnyx_conversation_duration_secs`: string integer (e.g. `"300"`)
- `telnyx_last_tool_status_code`: string (e.g. `"200"`) — used by tool nodes, not prompt nodes

Dynamic variables returned by `refill-webhook` (all strings):
- `trace_id`, `is_known_caller`, `patient_first_name`, `greeting_suffix`
- `call_count`, `last_intent`, `account_locked`, `refills_enabled`
- `after_hours_mode`, `open_refill_count`, `pharmacy_hours`
