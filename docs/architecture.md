# Architecture

## Component Diagram

```
┌─────────────────────────────────────────────┐
│              Caller (Phone)                  │
│              +44 20 4520 2115                │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│          Telnyx AI Assistant                 │
│                                              │
│  ┌───────────────────────────────────────┐   │
│  │      Conversation Workflow             │   │
│  │                                        │   │
│  │  n_disclosure (speak)                  │   │
│  │      → compliance greeting             │   │
│  │      → {{greeting_suffix}}               │   │
│  │                                        │   │
│  │  n_triage (prompt)                     │   │
│  │      ├── e_triage_after_hours          │   │
│  │      │   (expr: after_hours==true)     │   │
│  │      │   → n_after_hours               │   │
│  │      ├── e_triage_locked               │   │
│  │      │   (expr: account_locked==true)   │   │
│  │      │   → n_locked                    │   │
│  │      ├── e_triage_timeout              │   │
│  │      │   (expr: duration>=300)          │   │
│  │      │   → n_transfer                  │   │
│  │      ├── e_triage_human                │   │
│  │      │   (LLM: pharmacist)              │   │
│  │      │   → n_transfer_prompt           │   │
│  │      ├── e_triage_refill               │   │
│  │      │   (LLM: refill intent)           │   │
│  │      │   → n_verify                    │   │
│  │      └── e_triage_faq                  │   │
│  │          (LLM: hours/location)          │   │
│  │          → n_faq                       │   │
│  │                                        │   │
│  │  n_verify (prompt)                     │   │
│  │      → DOB verification (3 attempts)    │   │
│  │      → MCP: verify_identity            │   │
│  │                                        │   │
│  │  n_refill (prompt)                     │   │
│  │      → MCP: list_prescriptions         │   │
│  │                                        │   │
│  │  n_confirm (prompt)                    │   │
│  │      → MCP: request_refill             │   │
│  │                                        │   │
│  │  n_status (prompt)                     │   │
│  │      → MCP: get_refill_status          │   │
│  │                                        │   │
│  │  n_faq (prompt)                        │   │
│  │      → MCP: get_pharmacy_info          │   │
│  │      → MCP: get_medication_info        │   │
│  │                                        │   │
│  │  n_transfer (tool)                     │   │
│  │      → warm transfer to +15550000001  │   │
│  │                                        │   │
│  │  n_closing (speak)                     │   │
│  │      → {{closing_message}}              │   │
│  │                                        │   │
│  │  n_hangup (tool)                       │   │
│  │      → end call                        │   │
│  └───────────────────────────────────────┘   │
│           │                  │                │
│     Dynamic Vars         MCP Tools           │
│     Webhook              (6 tools)           │
└───────┼──────────────────┼──────────────────┘
        │                  │
        ▼                  ▼
┌───────────────┐  ┌──────────────┐
│ refill-webhook│  │  refill-mcp  │
│ (Python/ASGI) │  │ (Python/ASGI)│
│               │  │              │
│ ┌─────┐       │  │              │
│ │ KV  │       │  │ verify_id    │
│ │     │       │  │ list_rx      │
│ └─────┘       │  │ request_ref  │
│               │  │ get_status   │
│ ┌─────────────┐│  │ pharmacy_inf │
│ │ Actor       ││  │ medication   │
│ │ gateway     ││  │              │
│ └─────────────┘│  └──────────────┘
└───────┬────────┘
        │
        ▼
┌───────────────┐
│caller-session │
│(TypeScript)   │
│               │
│ Stateful Actor│
│ CallerSession │
│               │
│- recordCall   │
│- recordVerify │
│- addRefill    │
│- getRefills   │
│- getStatus    │
└───────────────┘
```

## Primitive Choices

| State Need | Primitive | Why |
|---|---|---|
| **Feature flags** (after-hours, refills enabled) | **KV** | Simple key-value, shared read across all calls, no write contention |
| **Per-caller state** (call count, failed attempts, open refills, lock status) | **Stateful Actor** | Single-threaded per caller prevents race conditions on read-modify-write (increment call count, decrement attempts) |
| **Webhook computation** (name resolution, greeting assembly) | **Edge Function** | Stateless, fast request/response, caches KV reads per container |
| **MCP tools** (FDA lookup, pharmacy info) | **Edge Function** | Stateless, HTTP interface, KV cache for FDA lookups |

## Data Flow for a Call

1. **Inbound PSTN call** → Telnyx platform connects to assistant `assistant-9befc905...`
2. **`assistant.initialization` webhook** → `refill-webhook` receives `call_control_id` and `telnyx_end_user_target`
3. **Name resolution** → Map `+15550000001` → "Maria" via local `_PATIENTS` dict (instant, no I/O)
4. **KV read** → Fetch `flag/after_hours_mode` and `flag/refills_enabled` from KV (cached per container)
5. **Actor call** → `POST /rpc` to `caller-session` with `recordCall(caller)` → increments `callCount`, returns state
6. **Compute dynamic variables** → Build `greeting_suffix`, `closing_message`, `attempts_left`, `account_locked`
7. **Return to assistant** → Assistant renders `n_disclosure` with `{{greeting_suffix}}`
8. **Workflow routing** → `n_triage` evaluates expression edges first (after_hours? locked? timeout?), then LLM edges
9. **MCP calls** → `refill-mcp` handles verification, listing, refilling via openFDA + KV cache
10. **Actor persistence** → Verification state and refill state survive across calls

## Deterministic Routing

Expression edges are evaluated **before** any LLM turn begins. This means:

- `after_hours_mode == "true"` → route to `n_after_hours` **without invoking the LLM**
- `account_locked == "true"` → route to `n_locked` **without invoking the LLM**
- Only when all expression edges are false does the LLM get involved for intent classification

This gives us predictable, auditable routing behavior that doesn't depend on model inference.

## Observability Surface

| Service | Log Format | Key Fields |
|---|---|---|
| `refill-webhook` | JSON | `event`, `trace_id`, `caller_key`, `dv_after_hours_mode`, `total_ms`, `outcome` |
| `refill-mcp` | JSON | `tool`, `trace_id`, `caller_key`, `outcome`, `isError` |
| `caller-session` | JSON | `method`, `trace_id`, `status`, `caller_key`, `state_keys` |

All three services share `trace_id` for distributed tracing. A single `grep tr_xxx` reconstructs the full call path.
