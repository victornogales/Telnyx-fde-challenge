# Demo Script — RefillLine (~10 minutes)

## 1. Introduction (30 seconds)

"RefillLine is a voice assistant for small pharmacies. It handles prescription refills, checks order status, answers pharmacy questions, and always provides a path to a human pharmacist."

**Show the architecture diagram** (`docs/architecture.md` §Component Diagram).

---

## 2. Happy Path Refill (~3 minutes)

**Action:** Dial `+442045202115`.

| Step | Caller Says | Assistant Response |
|---|---|---|
| 1 | *(dial)* | "Thanks for calling Maple Pharmacy. This call may be recorded. Say pharmacist at any time to speak with a person. Hi Maria, how can I help you today?" |
| 2 | "I want to refill" | "I can help with that." → "Please tell me your date of birth." |
| 3 | "15 March 1962" | "You said 15 March 1962. Is that correct?" |
| 4 | "Yes" | "Thank you, you're all set. What would you like to refill?" → "You have Lisinopril 10mg and Metformin 500mg." |
| 5 | "Lisinopril" | "You want to refill Lisinopril 10mg. Is that correct?" |
| 6 | "Yes" | "Your refill for Lisinopril is submitted. It will be ready in about 10 minutes. Do you need anything else?" |
| 7 | "No, thanks" | "Thanks for calling Maple Pharmacy. We appreciate your call. Take care, and have a great day." → hangup |

**What to highlight:**
- Personalized greeting via dynamic variables (`patient_first_name` → "Maria")
- DOB verification with 3-attempt limit (actor tracks `failedAttempts`)
- MCP integration (`list_prescriptions`, `request_refill`)
- Contextual closing message (`closing_message` dynamic variable)

---

## 3. After-Hours Deterministic Routing (~2 minutes)

**Setup:** Open terminal, show the KV flag.

```powershell
Invoke-RestMethod -Uri "https://api.telnyx.com/v2/storage/kvs/$env:KV_NAMESPACE_ID/keys/flag%2Fafter_hours_mode" `
  -Method PUT -Headers @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Content-Type" = "application/json"
  } -Body (@{ value = "true" } | ConvertTo-Json)
```

**Action:** Dial `+442045202115` again.

| Step | Caller Says | Assistant Response |
|---|---|---|
| 1 | *(dial)* | "Thanks for calling Maple Pharmacy... Hi Maria... Please note, Maple Pharmacy is currently closed. Our hours are 8am to 8pm, Monday to Saturday." |
| 2 | "I want to refill" | "Maple Pharmacy is currently closed, so prescription refills, prescription lookups, and in-store pickup are unavailable right now. Please call back during business hours." |
| 3 | "Bye" | "Thanks for calling Maple Pharmacy. We're currently closed. Please call back during business hours... Take care." → hangup |

**What to highlight:**
- **Deterministic routing:** The platform evaluates `after_hours_mode == "true"` as an **expression edge** before the LLM turn begins. No inference. No guessing.
- The LLM is never asked to decide whether it's after-hours — the workflow does.

**Reset after demo:**
```powershell
Invoke-RestMethod -Uri "https://api.telnyx.com/v2/storage/kvs/$env:KV_NAMESPACE_ID/keys/flag%2Fafter_hours_mode" `
  -Method PUT ... -Body (@{ value = "false" } | ConvertTo-Json)
```

---

## 4. Debugging Story: The 50% After-Hours Failure (~2 minutes)

**The bug:** ~50% of after-hours calls skipped the closed message and went to DOB verification.

**Evidence trail (show in terminal):**

```powershell
# Show webhook logs
 telnyx-edge logs refill-webhook -n 20 --since 1h
```

**Key log lines to point out:**
- `total_ms: 1307` — the function completed but was very close to the 1500ms timeout
- `degraded: "TimeoutError: "` — some requests hit the timeout
- `dv_after_hours_mode: "true"` vs `"false"` — inconsistent

**Root cause:**
```
KV GET latency: ~900-1100ms
Original timeout: 0.9s (asyncio.wait_for)
Result: 50% of KV reads timed out silently
Fallback: static default "after_hours_mode=false"
```

**Fix:**
1. Increased KV timeout: `0.9s → 1.5s`
2. Increased assistant webhook timeout: `1500ms → 5000ms`
3. Added partial defaults with `greeting_suffix` even on timeout

**Proof:** `scripts/quick-test.py` — 10/10 requests returned `after_hours=true` after the fix.

**Lesson:** "Measure the total round-trip, not just function execution. Platform overhead (DNS + TLS handshake on cold containers) adds 200-400ms that doesn't show up in your function timer."

---

## 5. Observability Surface (~1.5 minutes)

**Show the three log streams:**

```powershell
# Webhook
 telnyx-edge logs refill-webhook -n 5

# MCP
 telnyx-edge logs refill-mcp -n 5

# Actor
 telnyx-edge actors logs CallerSession -n 5
```

**Highlight:**
- All three services log with the same `trace_id`
- A single `grep tr_xxx` reconstructs the full call path
- `total_ms`, `kv_ms`, `gateway_ms` show latency breakdown per request

---

## 6. Wrap-Up (30 seconds)

**Stretch goals completed:**
- ✅ Variable comparison edges (`after_hours_mode`, `account_locked`)
- ✅ KV-based feature flags (toggle after-hours without redeploying)
- ✅ Custom dynamic variables webhook (`closing_message`, `attempts_left`)
- ✅ Distributed tracing (`trace_id` across Assistant → Function → Actor → MCP)

**Why these primitives:**
- **KV** for shared read-heavy flags (no write contention)
- **Stateful Actor** for per-caller read-modify-write state (call count, failed attempts)
- **Edge Function** for stateless request/response (webhook, MCP)

---

## Fallback Plans

| If this happens... | Do this... |
|---|---|
| Call doesn't connect | Show telnyx-edge list, confirm all functions deploy_ok |
| After-hours doesn't trigger | Show `scripts/verify_after_hours.py` output, check KV value |
| Assistant routes to n_verify during after-hours | Check workflow version — expression edge must be first |
| MCP tool fails | Check `refill-mcp` logs for `isError=true` with trace_id |
