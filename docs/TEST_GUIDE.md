# RefillLine Test Guide

> **Last updated:** 2026-11-11
> **Status:** Scenario 1 verified. Scenarios 2-8 pending.
> **Purpose:** Living document capturing architecture decisions, fixes, known issues, and complete test procedures.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Current System State](#current-system-state)
3. [Key Design Decisions & Fixes](#key-design-decisions--fixes)
4. [Test Environment](#test-environment)
5. [Pre-Test Setup](#pre-test-setup)
6. [Test Scenarios](#test-scenarios)
7. [Log Monitoring](#log-monitoring)
8. [Known Issues & Limitations](#known-issues--limitations)
9. [Test Data Reference](#test-data-reference)
10. [Exit Criteria](#exit-criteria)

---

## Architecture Overview

### Component Diagram

```
Telnyx Platform
  - Assistant (WebSocket)
  - PSTN Call +442045202115
       |
       | HTTP webhook
       v
refill-webhook (Python)
  - Receives assistant.initialization
  - Looks up patient by caller ID
  - Pre-computes greeting_suffix
  - Calls caller-session via POST /rpc
       |
       | POST /rpc (X-Internal-Token)
       v
caller-session (TypeScript)
  - Stateful Actor: CallerSession
  - recordCall, recordVerification
  - addRefill, getRefills
       |
       | HTTP
       v
refill-mcp (Python)
  - verify_identity
  - list_prescriptions
  - request_refill
  - get_refill_status
  - get_pharmacy_info
  - get_medication_info
```

### Data Flow for a Call

1. Inbound PSTN call -> Telnyx platform connects to assistant
2. assistant.initialization webhook -> refill-webhook receives caller ID
3. Webhook resolves patient -> looks up telnyx_end_user_target in _PATIENTS dict
4. Webhook resolves name -> creates patient_first_name and greeting_suffix variables
5. Webhook calls actor -> recordCall increments counter, returns state
6. Webhook returns dynamic variables -> assistant uses them in workflow
7. Assistant runs workflow -> n_disclosure speak -> n_triage prompt -> etc.
8. Tools invoked -> refill-mcp handles verification, listing, refilling
9. Actor persists state -> verification, refills stored in Stateful Actor

---

## Current System State

### Functions

| Function | Status | Updated | Notes |
|---|---|---|---|
| refill-webhook | deploy_ok | 2026-11-11 08:56 | KV singleton, name pre-resolution, greeting_suffix |
| caller-session | deploy_ok | 2026-11-05 12:07 | Actor gateway for stateful operations |
| refill-mcp | deploy_ok | 2026-11-10 10:47 | MCP server with 6 tools, retry logic |

### Assistant Configuration

| Property | Value | Notes |
|---|---|---|
| Assistant ID | assistant-9befc905-0e48-42f9-b65f-ae91b269bb65 | -- |
| Phone Number | +442045202115 | Trial verified |
| Greeting | "" | Disabled to prevent double-greeting |
| user_idle_timeout_secs | 45 | Platform-level idle detection |
| time_limit_secs | 300 | Max call duration |

### Workflow Nodes

| Node | Type | Purpose |
|---|---|---|
| n_disclosure | speak | Fixed text with greeting_suffix |
| n_triage | prompt | Wait for caller intent |
| n_verify | prompt | DOB verification |
| n_refill | prompt | List prescriptions |
| n_confirm | prompt | Confirm and submit refill |
| n_status | prompt | Check refill status |
| n_faq | prompt | Pharmacy info |
| n_after_hours | prompt | Closed-hours message |
| n_locked | speak | Lockout notice |
| n_transfer | tool | Transfer call |
| n_closing | speak | Goodbye |
| n_hangup | tool | End call |

---

## Key Design Decisions & Fixes

### Fix 1: Patient Name Pre-Resolution

**Problem:** Webhook timed out before resolving name -> no personalized greeting.

**Root Cause:** _find_patient_name() was called AFTER _fetch_all() RPC. On timeout -> empty name.

**Solution:** Move name resolution BEFORE timeout window.

Before:
  result = await asyncio.wait_for(self._fetch_all(...), timeout=1.0)
  # Name lost on timeout

After:
  patient_name = _find_patient_name(end_user)  # Instant lookup
  PARTIAL_DEFAULTS["patient_first_name"] = patient_name
  # Then try RPC

**Impact:** Name always available, even on gateway timeout.

---

### Fix 2: Greeting Pre-Computation via greeting_suffix

**Problem:** 5 seconds silence before greeting because LLM needed to generate "Hi Maria".

**Root Cause:** n_triage prompt told LLM to generate greeting text, requiring inference.

**The Lesson:** Even simplest LLM prompt requires inference (2-5s). Dynamic variables are INSTANT.

**Solution:** Move greeting text into dynamic variable, interpolated by speak node.

Webhook pre-computes:
  if patient_name:
    "greeting_suffix": " Hi Maria, how can I help you today?"
  else:
    "greeting_suffix": " How can I help you today?"

Speak node says:
  "Thanks for calling... {{greeting_suffix}}"

**Impact:** One TTS pass, zero dead air. Total first audio: under 1 second.

---

### Fix 3: Prompt vs Speak Node Cost Model

Critical insight:

| Node Type | Speed | What happens |
|---|---|---|
| speak | ~0.5s | Direct TTS, no LLM |
| prompt | ~2-5s | LLM inference + TTS |

Mistake: Merged n_disclosure + n_triage into one prompt to "save a TTS cycle."

Result: Worse! LLM ran before ANY audio -> user heard silence -> "I'm still here."

Correct architecture:
  - speak node for fixed text (instant feedback)
  - prompt node for adaptive text (slow, but user already heard something)

---

### Fix 4: KV Singleton Cache

**Problem:** _KV recreated per-request -> KV REST calls every time.

**Solution:** Module-level singleton with _get_kv().

**Impact:** After first warm-up, flag lookups from memory cache (15s TTL). ~200-400ms saved.

---

### Fix 5: Base Instructions Prohibit Phantom Greeting

**Problem:** Assistant inferred it should say "Hello and welcome" before workflow.

**Solution:** Added instruction: "Do NOT greet with Hello or Welcome - the workflow handles it."

---

## Test Environment

### Prerequisites

- Phone +15550000001 is verified in Telnyx portal
- You can dial +442045202115
- Environment variables set:
  TELNYX_API_KEY
  INTERNAL_TOKEN
  KV_NAMESPACE_ID

### Terminal Setup

Open 3 PowerShell windows:

Window 1: MCP logs
  while ($true) { telnyx-edge logs refill-mcp --tail -n 5; Start-Sleep -Seconds 2 }

Window 2: Webhook logs
  while ($true) { telnyx-edge logs refill-webhook --tail -n 5; Start-Sleep -Seconds 2 }

Window 3: Actor logs
  while ($true) { telnyx-edge actors logs CallerSession --tail -n 5; Start-Sleep -Seconds 2 }

---

## Pre-Test Setup

**Quick way:** Run the reset script:

```powershell
.\scripts\reset-test.ps1
```

**What it does:**
1. Computes Maria's caller key from +15550000001
2. Resets actor state (failed attempts, lock status, refills)
3. Resets feature flags: refills_enabled=true, after_hours=false

**Sample output:**
```
Caller key: 8e89f1d43d07b82d
Resetting actor state ... OK
Resetting flags ... OK
Reset complete. Ready to test.
```

---

**Manual way** (if the script doesn't work):

```powershell
$e164 = "+15550000001"
$callerKey = ([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($e164)) | ForEach-Object { $_.ToString("x2") }) -join "" | ForEach-Object { $_.Substring(0,16) }

Invoke-RestMethod -Uri "https://api.telnyx.com/v2/edge/functions/caller-session/rpc" `
  -Method POST `-Headers @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Content-Type" = "application/json"
    "X-Internal-Token" = $env:INTERNAL_TOKEN
    "X-Trace-Id" = "reset_$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
  } `-Body (@{
    method = "recordVerificationAttempt"
    caller_key = $callerKey
    args = @{ success = $true; traceId = "reset" }
  } | ConvertTo-Json) -ErrorAction SilentlyContinue

Invoke-RestMethod -Uri "https://api.telnyx.com/v2/storage/kvs/$env:KV_NAMESPACE_ID/keys/flag%2Frefills_enabled" `
  -Method PUT `-Headers @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Content-Type" = "application/json"
  } `-Body (@{ value = "true" } | ConvertTo-Json)

Invoke-RestMethod -Uri "https://api.telnyx.com/v2/storage/kvs/$env:KV_NAMESPACE_ID/keys/flag%2Fafter_hours_mode" `
  -Method PUT `-Headers @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Content-Type" = "application/json"
  } `-Body (@{ value = "false" } | ConvertTo-Json)

Write-Host "Reset complete. Caller key: $callerKey"

---

## Test Scenarios

### Scenario 1: Happy Path - Maria Refills Lisinopril

Status: VERIFIED (2026-11-11)

Setup: Run Pre-Test Setup.

| Step | You Say | Expected Response |
|---|---|---|
| 1 | Dial +442045202115 | "Thanks for calling Maple Pharmacy. This call may be recorded. Hi Maria, how can I help you today?" |
| 2 | "I want to refill" | "I can help. Please tell me your date of birth." |
| 3 | "March 15 1962" | "You said March 15, 1962. Is that correct?" |
| 3b | "Yes" | "Thank you. You're all set. I can help you refill." (proceeds to listing prescriptions) |
| 4 | "Lisinopril" | "I've submitted a refill for Lisinopril 10 mg..." |
| 5 | "No, goodbye" | "Thanks for calling Maple Pharmacy. Take care." |

What confirms success:
- [x] Opening within 1 second
- [x] "Hi Maria" in opening
- [x] DOB requested
- [x] **Assistant repeats DOB back and asks "Is that correct?"**
- [x] Upon confirmation, assistant verifies and acknowledges prior intent (refill)
- [x] Refill submitted without restating intent
- [x] Graceful closing

---

### Scenario 2: Call Back - Must Verify Again

**Setup:** Run Scenario 1. Immediately call back.

| Step | You Say | Expected Response |
|---|---|---|
| 1 | Dial again | "Thanks for calling... Hi Maria..." |
| 2 | "I want to refill" | "I can help. Please tell me your date of birth." (**Always asked**) |
| 3 | Provide DOB, confirm | "Thank you. You're all set. I can help you refill." |
| 4 | "Refill Metformin" | Confirms refill |

**What confirms success:**
- [ ] Asked for DOB again (even on callback)
- [ ] Verification succeeded
- [ ] Refill submitted

**Key insight:** Verification does NOT persist across calls. Each call requires fresh verification for security.

---

### Scenario 3: Transfer to Pharmacist

Setup: Pre-Test Setup.

| Step | You Say | Expected Response |
|---|---|---|
| 1 | Dial | Greeting |
| 2 | "Pharmacist" | "I'll transfer you now. Please hold." |
| 3 | Hold | Your phone rings with second call |

Note: May get busy on trial account. This is expected.

---

### Scenario 4: Wrong DOB (Graceful Failure)

Setup: Pre-Test Setup.

| Step | You Say | Expected Response |
|---|---|---|
| 1 | Dial | Greeting |
| 2 | "I want to refill" | "I can help. Please tell me your date of birth." |
| 3 | "January 1 1990" (wrong) | "You said January 1, 1990. Is that correct?" |
| 3b | "Yes" (confirming wrong DOB) | "That does not match my records. You have 2 more tries. What is your date of birth?" |
| 4 | "March 15 1962" | "You said March 15, 1962. Is that correct?" |
| 4b | "Yes" | "Thank you. Verified. I can help you refill." |

What confirms success:
- [ ] Assistant repeats DOB and asks for confirmation
- [ ] On wrong DOB: says remaining attempts and asks again
- [ ] On correct DOB: verifies and proceeds

---

### Scenario 5: Account Lock After 3 Failed DOBs

Setup: Pre-Test Setup.

| Step | You Say | Expected Response |
|---|---|---|
| 1 | "I want to refill" | "Please tell me your date of birth." |
| 2 | Wrong DOB #1 | "Does not match. Try again." |
| 3 | Wrong DOB #2 | "Does not match. Try again." |
| 4 | Wrong DOB #3 | "Account locked for security. Transferring to pharmacist." |

---

### Scenario 6: After-Hours Mode

Setup: Enable flag BEFORE calling.

Invoke-RestMethod -Uri "https://api.telnyx.com/v2/storage/kvs/$env:KV_NAMESPACE_ID/keys/flag%2Fafter_hours_mode" `
  -Method PUT `-Headers @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Content-Type" = "application/json"
  } `-Body (@{ value = "true" } | ConvertTo-Json)

| Step | You Say | Expected Response |
|---|---|---|
| 1 | Dial | Greeting + "Maple Pharmacy is currently closed..." |
| 2 | "I want to refill" | "We can't process refills after hours..." |

Reset after test: set flag to false.

---

### Scenario 7: Refills Disabled

Setup: Disable refills flag.

Invoke-RestMethod -Uri "https://api.telnyx.com/v2/storage/kvs/$env:KV_NAMESPACE_ID/keys/flag%2Frefills_enabled" `
  -Method PUT `-Headers @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Content-Type" = "application/json"
  } `-Body (@{ value = "false" } | ConvertTo-Json)

| Step | You Say | Expected Response |
|---|---|---|
| 1 | Dial | Greeting |
| 2 | "I want to refill" | "I'm sorry, refills are temporarily unavailable..." |

Reset after test: set flag to true.

---

### Scenario 8: Unknown Caller

Setup: Pre-Test Setup. Call from different number.

| Step | You Say | Expected Response |
|---|---|---|
| 1 | Dial from unknown number | Greeting without name |
| 2 | "I want to refill" | "I don't have a record for this number..." |

Note: Requires second phone or VoIP app.

---

## Log Monitoring

One-shot after each test:
  telnyx-edge logs refill-webhook -n 20
  telnyx-edge logs refill-mcp -n 20
  telnyx-edge actors logs CallerSession -n 20

What to look for:

| Log | Good Sign | Bad Sign |
|---|---|---|
| refill-webhook | outcome=ok, total_ms < 1000 | outcome=fallback, timeout |
| caller-session | recordCall ok, addRefill ok | Any error |
| refill-mcp | outcome=success, isError=false | isError=true |

---

## Known Issues & Limitations

1. Trial Account Restrictions:
   - Inbound calls ONLY from verified numbers
   - Max 2 concurrent calls, 10 minutes per call
   - Transfer may fail due to single-line limitation

2. DOB Verification Flow:
   - Assistant must repeat DOB back and ask "Is that correct?"
   - On wrong DOB: assistant reports remaining attempts (e.g., "You have 2 more tries")
   - On locked: transfers to pharmacist
   - attempts_left dynamic variable tracks remaining tries per call

3. Webhook Timeout:
   - KV + gateway must complete within 1.0 second
   - On timeout: fallback with greeting_suffix still populated
   - First call may timeout if actor cold starts

4. KV Singleton Cache:
   - First request incurs full REST round-trip (~513ms)
   - Subsequent requests use in-memory cache
   - Containers recycled after idle period

5. TTS Cold Start:
   - First utterance may have ~0.5s generation delay
   - Platform-level behavior, not under our control
   - Mitigated by speak node before prompt node

---

## Test Data Reference

| Phone | Patient | DOB | Medications |
|---|---|---|---|
| +15550000001 | Maria | 1962-03-15 | Lisinopril 10mg (2), Metformin 500mg (1) |
| +442045202115 | James | 1985-07-22 | Atorvastatin 20mg (3) |
| +15551112222 | David | 1978-11-03 | Sertraline 50mg (2) |
| +15552223333 | Sarah | 1991-06-08 | Levothyroxine 75mcg (5) |
| +15553334444 | Robert | 1955-09-19 | Warfarin 5mg (0) |

DOB Formats Accepted:
- March fifteenth nineteen sixty-two
- fifteen oh three sixty-two
- 1962-03-15

---

## Exit Criteria

- [x] Scenario 1: Happy path refill
- [ ] Scenario 2: Call back - must verify again (security policy)
- [ ] Scenario 3: Transfer
- [ ] Scenario 4: Wrong DOB retry
- [ ] Scenario 5: Lockout after 3 failures
- [ ] Scenario 6: After-hours
- [ ] Scenario 7: Refills disabled
- [ ] Scenario 8: Unknown caller
- [ ] Global: No 5-second silence
- [ ] Global: No "I'm still here" on opening
- [ ] Global: trace_id in all logs
- [ ] Global: No 500 errors

### Scenario Status

| Scenario | Date Tested | Status |
|---|---|---|
| 1 Happy Path | 2026-11-11 | VERIFIED |
| 2 Callback (verify again) | -- | PENDING |
| 3 Transfer | -- | PENDING |
| 4 Wrong DOB | -- | PENDING |
| 5 Lockout | -- | PENDING |
| 6 After-Hours | -- | PENDING |
| 7 Refills Disabled | -- | PENDING |
| 8 Unknown Caller | -- | PENDING |
