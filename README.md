# RefillLine — Telnyx FDE Challenge

Voice assistant for prescription refills on Telnyx AI Assistants, Conversation Workflows, Edge Functions, KV, Stateful Actors and a custom MCP server.

Languages: **Python** (webhook + MCP server) and a small **TypeScript** actor gateway (Stateful Actors are TypeScript-only on Telnyx Edge).

Built with **Telnyx Inference via OpenCode** — see `opencode.json`.

---

## Try it

| Component | URL / Number |
|---|---|
| **Phone number** | `+442045202115` |
| **Webhook (dynamic variables)** | `https://refill-webhook-8d5c4fc7-b.telnyxcompute.com` |
| **MCP server** | `https://refill-mcp-6a4810fb-9.telnyxcompute.com/mcp` |
| **Actor gateway** | `https://caller-session-51645523-7.telnyxcompute.com/rpc` |

Call `+442045202115` and say "I want to refill my prescription."

> Patient lookup matches on the caller's E.164. The sample table uses the synthetic
> number `+15550000001`; replace it in `functions/_shared/patients.py` with your own
> verified test number locally (run `scripts/sync-shared.sh`, never commit the real number).

---

## Use case

RefillLine handles prescription refill and "is my order ready?" calls for small pharmacies — end to end, with identity verification, compliance disclosure, and a guaranteed path to a human.

See [`docs/use-case.md`](docs/use-case.md) for the full problem statement.

---

## Architecture

```
Caller (Phone +442045202115)
    │
    ▼
Telnyx AI Assistant (Conversation Workflow)
    ├── speak: n_disclosure — compliance greeting + personalized suffix
    ├── prompt: n_triage — intent routing (after-hours, locked, refill, status, FAQ)
    ├── prompt: n_verify — DOB verification (3 attempts, actor-backed)
    ├── prompt: n_refill — list prescriptions via MCP
    ├── prompt: n_confirm — explicit confirmation + submit refill via MCP
    ├── prompt: n_status — check refill status via MCP
    ├── prompt: n_faq — pharmacy info via MCP
    ├── prompt: n_after_hours — closed-hours message (expression-gated)
    ├── speak: n_locked — lockout notice
    ├── tool: n_transfer — warm transfer to pharmacist
    └── speak: n_closing — contextual goodbye via dynamic variable
    │
    ├── Dynamic Variables Webhook ──► refill-webhook (Edge Function)
    │                                      ├── KV: feature flags (after_hours, refills_enabled)
    │                                      ├── Actor: recordCall, recordVerification (caller-session)
    │                                      └── Personalized greeting + attempts_left
    │
    └── MCP Server ──────────────────► refill-mcp (Edge Function)
                                          ├── verify_identity
                                          ├── list_prescriptions
                                          ├── request_refill
                                          ├── get_refill_status
                                          ├── get_pharmacy_info
                                          └── get_medication_info
```

See [`docs/architecture.md`](docs/architecture.md) for component details and primitive choices.

---

## Dynamic Variable Routing Matrix

Dynamic variables returned by the webhook **deterministically influence routing** via expression edges:

| Variable | Condition Type | Edge | Target |
|---|---|---|---|
| `after_hours_mode` | **Expression:** `== "true"` | `e_triage_after_hours` | `n_after_hours` |
| `account_locked` | **Expression:** `== "true"` | `e_triage_locked` | `n_locked` |
| `telnyx_conversation_duration_secs` | **Expression:** `>= 300` | `e_triage_timeout` | `n_transfer` |
| Intent (refill / status / hours) | LLM condition | `e_triage_*` | `n_verify` / `n_faq` |

Expression edges are evaluated **before** LLM turns begin, making routing deterministic.

---

## Setup & deploy

### Prerequisites

- Telnyx account with API key
- `telnyx-edge` CLI authenticated
- Python 3.12+ (for local pytest)
- Node.js 20+ (for caller-session typecheck)

### Environment variables

```powershell
$env:TELNYX_API_KEY    = "KEY018_..."
$env:INTERNAL_TOKEN    = "S-..."
$env:KV_NAMESPACE_ID   = "3208b4c8-7ac1-4f42-a73d-ab9bfd4fc8ee"
```

### Deploy all functions

```powershell
# 1. Ship Python functions
cd functions\refill-webhook
telnyx-edge ship
cd ..\..\functions\refill-mcp
telnyx-edge ship

# 2. Ship TypeScript actor
cd ..\..\functions\caller-session
telnyx-edge ship

# 3. Verify
 telnyx-edge list
```

### Configure the assistant

```powershell
# Set assistant defaults (after_hours_mode=false for normal operation)
python scripts\reset_after_hours.py

# Enable after-hours for testing
python scripts\enable_after_hours.py
```

### Run tests locally

```powershell
cd functions\refill-webhook
pytest

cd ..\..\functions\refill-mcp
pytest

cd ..\..\functions\caller-session
npm run typecheck
```

---

## Observability: how I'd know it's broken within a minute

Every request logs exactly **one JSON line** with `trace_id`:

```json
{
  "ts": "2026-11-11T19:02:00Z",
  "level": "info",
  "fn": "refill-webhook",
  "event": "webhook",
  "trace_id": "tr_8368f9002b13",
  "caller_key": "8e89f1d43d07b82d",
  "dv_after_hours_mode": "true",
  "degraded": false,
  "kv_ms": 1224,
  "gateway_ms": 366,
  "total_ms": 1227,
  "outcome": "ok"
}
```

**Within 1 minute I'd check:**

1. `telnyx-edge logs refill-webhook --since 1m` — look for `outcome=fetch_error` or `degraded=true`
2. `telnyx-edge logs refill-mcp --since 1m` — look for `isError=true`
3. `telnyx-edge actors logs CallerSession --since 1m` — look for actor exceptions

**Correlate across systems:** All three services share the same `trace_id`, so a single `grep tr_xxx` reconstructs the full call path.

---

## Debugging story: the 50% after-hours failure

**Symptom:** ~50% of real calls during after-hours skipped the closed message and went straight to DOB verification.

**Evidence:**
- Webhook logs showed `dv_after_hours_mode="true"` in 100% of responses
- But some callers still heard "Please tell me your date of birth"
- Synthetic tests (`scripts/quick-test.py`) showed 50% returned `after_hours=false`

**Root cause:** KV GET to `api.telnyx.com/v2/storage/kvs/.../flag/after_hours_mode` takes ~900-1100ms consistently. The original timeout was **0.9s** (`asyncio.wait_for`). Right on the edge. When KV was slow, the inner flag read timed out silently, and the webhook fell back to the static default `"false"`.

**Fix:**
1. Increased KV timeout: **0.9s → 1.5s**
2. Increased assistant webhook timeout: **1500ms → 5000ms**
3. Ensured partial defaults always include `greeting_suffix` even on timeout

**Proof:** After the fix, 10/10 synthetic requests returned `after_hours=true`. Real calls stopped routing to DOB verification during after-hours.

**Lesson:** Measure the total round-trip, not just function execution time. Platform overhead (DNS + TLS handshake from Telnyx to the Edge Function on cold containers) adds 200-400ms that doesn't show up in function-level timers.

---

## Stretch goals completed

| Stretch Goal | Implementation |
|---|---|
| Variable comparison edges | `e_triage_after_hours` (expression on custom variable) |
| KV-based feature flags | `flag/after_hours_mode`, `flag/refills_enabled` |
| Custom dynamic variables webhook | `refill-webhook` returns `closing_message`, `attempts_left`, `open_refill_count` |
| Distributed tracing | `trace_id` shared across Assistant → Webhook → Actor → MCP |
| Alarms in Stateful Actors | `CallerSession` calls `setAlarm()` on `request_refill`; ~2 minutes later `alarm()` marks the refill "ready" (retries with backoff on failure) |

---

## Built with Telnyx Inference (OpenCode)

See `opencode.json` for the active Telnyx plugin configuration.

Model used: `telnyx/moonshotai/Kimi-K2.6` via the OpenCode plugin. (`Kimi-K3`, the example in the brief, wasn't available on this account and returned a generic `UnknownError`. `opencode models telnyx` lists what is actually available. See `DOGFOOD.md`.)

---

## Repository structure

```
RefillLine/
├── assistant/
│   └── workflow.json          # Conversation flow (14 nodes, 33 edges)
├── functions/
│   ├── refill-webhook/        # Dynamic variables webhook (Python)
│   ├── refill-mcp/            # MCP server (Python, 6 tools)
│   └── caller-session/        # Stateful Actor gateway (TypeScript)
├── docs/
│   ├── architecture.md        # Component diagrams
│   ├── TEST_GUIDE.md          # Full test procedures
│   └── use-case.md            # Problem statement
├── scripts/                   # Utilities (toggle flags, test calls)
├── opencode.json              # OpenCode Telnyx plugin config
└── README.md                  # This file
```
