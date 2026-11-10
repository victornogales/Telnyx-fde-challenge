# RefillLine Voice Workflow — Test Scenarios

> **Prerequisites**
> - Your calling phone (`+15550000001`) is verified in the Telnyx portal
> - You dial `+442045202115`
> - You have 3 terminal windows open (see §Log Monitoring below)

---

## Pre-Test Reset (Run Before Every Scenario)

These commands reset actor state and KV flags so tests are independent.

```powershell
# 1. Reset actor state for your caller key (Maria = +15550000001)
# The caller_key is the first 16 chars of SHA256(+15550000001)
$e164 = "+15550000001"
$callerKey = ([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($e164)) | ForEach-Object { $_.ToString("x2") }) -join "" | ForEach-Object { $_.Substring(0,16) }

# Reset the actor by calling alarm (wakes it) then ensuring clean state
Invoke-RestMethod -Uri "https://api.telnyx.com/v2/edge/functions/caller-session/rpc" `
  -Method POST `
  -Headers @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Content-Type" = "application/json"
    "X-Internal-Token" = $env:INTERNAL_TOKEN
    "X-Trace-Id" = "reset_$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
  } `
  -Body (@{
    method = "recordVerificationAttempt"
    caller_key = $callerKey
    args = @{ success = $true; traceId = "reset" }
  } | ConvertTo-Json) -ErrorAction SilentlyContinue

# 2. Reset feature flags to defaults
Invoke-RestMethod -Uri "https://api.telnyx.com/v2/storage/kvs/$env:KV_NAMESPACE_ID/keys/flag%2Frefills_enabled" `
  -Method PUT `
  -Headers @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Content-Type" = "application/json"
  } `
  -Body (@{ value = "true" } | ConvertTo-Json)

Invoke-RestMethod -Uri "https://api.telnyx.com/v2/storage/kvs/$env:KV_NAMESPACE_ID/keys/flag%2Fafter_hours_mode" `
  -Method PUT `
  -Method PUT `
  -Headers @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Content-Type" = "application/json"
  } `
  -Body (@{ value = "false" } | ConvertTo-Json)

# 3. Verify reset
Write-Host "Caller key: $callerKey"
Write-Host "Flags reset: refills=true, after_hours=false"
```

---

## Scenario 1: Happy Path — Maria Verifies and Refills Lisinopril

**Setup:** Run Pre-Test Reset above.

**Call from:** `+15550000001` (Maria's phone)

| Step | You Say / Do | Expected Assistant Response | System Action |
|---|---|---|---|
| 1 | Dial `+442045202115` | "Hello. This call may be recorded for quality assurance…" | Webhook fires; `recordCall` increments to 1 |
| 2 | "I want to refill my prescription" | "I can help with that. For security, please tell me your date of birth." | `get_prescriptions` returns Maria's list |
| 3 | "My date of birth is March 15 1962" or "1962-03-15" | "Thank you Maria. I've verified your identity." | `verify_identity` checks DOB → success; actor locks verification |
| 4 | "I need a refill for Lisinopril" | "I've submitted a refill request for Lisinopril 10 mg…" | `add_refill` writes to actor; openRefills = 1 |
| 5 | "That's all, goodbye" | "Goodbye Maria. Your pharmacy is open 8am to 8pm…" | Call ends |

**Verify in logs:**
- `refill-webhook`: `outcome=ok`, `call_count=1`
- `refill-mcp`: `tool=verify_identity`, `outcome=success`
- `refill-mcp`: `tool=add_refill`, `outcome=success`, `medication=Lisinopril`
- `caller-session`: `method=recordVerificationAttempt`, `success=true`
- `caller-session`: `method=addRefill`, result has `refillId`

---

## Scenario 2: Maria Calls Back (Already Verified)

**Setup:** Run Scenario 1 first. Do NOT reset.

| Step | You Say / Do | Expected Response | System Action |
|---|---|---|---|
| 1 | Dial again | Same greeting | `recordCall` increments to 2 |
| 2 | "I want to refill" | "Welcome back Maria. You're already verified…" | `isVerified` → true; skips DOB step |
| 3 | "Refill Metformin" | Confirms refill | `add_refill` for Metformin |

**Key insight:** Verification persists 30 minutes in the actor. You should NOT be asked for DOB again.

---

## Scenario 3: Transfer to Pharmacist

**Setup:** Pre-Test Reset.

| Step | You Say / Do | Expected Response | System Action |
|---|---|---|---|
| 1 | Dial | Greeting plays | — |
| 2 | "Speak to a pharmacist" | "I'll transfer you now. Please hold." | `transfer_call` tool invoked |
| 3 | Hold | Ringing sound, then your phone `+15550000001` rings | Telnyx dials `+15550000001` |
| 4 | Answer transfer | Connected to live person | Original AI call continues bridged |

**Verify:** Your mobile (`+15550000001`) should ring with a second incoming call.

**Note:** If you're calling FROM `+15550000001`, you may get busy because your line is already on the first call. This is expected. Test with a second phone, or:
- Call from `+15550000001`
- When transfer happens, it VoIP-dials the same number
- Most phones show "call waiting" or the second call goes to voicemail

---

## Scenario 4: Verification Failure (Wrong DOB)

**Setup:** Pre-Test Reset.

| Step | You Say / Do | Expected Response | System Action |
|---|---|---|---|
| 1 | Dial | Greeting | — |
| 2 | "I want to refill" | "Please tell me your date of birth." | — |
| 3 | "My DOB is January 1 1990" (wrong) | "That doesn't match our records. Please try again." | `verify_identity` → `outcome=wrong_dob` |
| 4 | "Ok, it's March 15 1962" (correct) | "Thank you Maria. Verified." | `verify_identity` → success |

**Key insight:** Actor tracks failed attempts but does NOT lock on first failure. You get multiple chances.

---

## Scenario 5: Account Lock After 3 Failed DOBs

**Setup:** Pre-Test Reset.

| Step | You Say / Do | Expected Response | System Action |
|---|---|---|---|
| 1-2 | Dial, request refill | Asks for DOB | — |
| 3 | Give wrong DOB (1st) | "Doesn't match. Try again." | `recordVerificationAttempt` success=false |
| 4 | Give wrong DOB (2nd) | "Doesn't match. Try again." | attempt 2 |
| 5 | Give wrong DOB (3rd) | "Account locked for security. Transferring to pharmacist." | `locked=true`; auto-transfer or hangup |

**Verify in logs:**
- `caller-session`: `method=recordVerificationAttempt`, 3 failures
- `caller-session`: `account_locked=true`

---

## Scenario 6: After-Hours Mode

**Setup:** Enable after-hours BEFORE calling.

```powershell
Invoke-RestMethod -Uri "https://api.telnyx.com/v2/storage/kvs/$env:KV_NAMESPACE_ID/keys/flag%2Fafter_hours_mode" `
  -Method PUT `
  -Headers @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Content-Type" = "application/json"
  } `
  -Body (@{ value = "true" } | ConvertTo-Json)
```

| Step | You Say / Do | Expected Response |
|---|---|---|
| 1 | Dial | Greeting + "Our pharmacy is now closed…" |
| 2 | "I want to refill" | "We can't process refills after hours. I can transfer you…" or similar |

**Note:** Current workflow logic may vary based on how `after_hours_mode` is consumed in the AI instructions.

---

## Scenario 7: Refills Disabled

**Setup:** Disable refills.

```powershell
Invoke-RestMethod -Uri "https://api.telnyx.com/v2/storage/kvs/$env:KV_NAMESPACE_ID/keys/flag%2Frefills_enabled" `
  -Method PUT `
  -Method PUT `
  -Headers @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Content-Type" = "application/json"
  } `
  -Body (@{ value = "false" } | ConvertTo-Json)
```

| Step | You Say / Do | Expected Response |
|---|---|---|
| 1 | Dial | Greeting |
| 2 | "I want to refill" | "I'm sorry, refills are temporarily unavailable. I can transfer you to a pharmacist." |

---

## Scenario 8: Unknown Caller (New Number)

**Setup:** Pre-Test Reset. Call from a DIFFERENT number (not +15550000001). If you only have one phone, use a friend's or a VoIP app.

| Step | You Say / Do | Expected Response |
|---|---|---|
| 1 | Dial from unregistered number | Greeting |
| 2 | "I want to refill" | "I don't have a record for this number. Let me connect you with a pharmacist." |

**Why:** The `telnyx_end_user_target` in the webhook payload is your caller ID. If it's not in `_PATIENTS`, `get_prescriptions` returns `isError`.

---

## Log Monitoring

Open 3 PowerShell windows and run:

```powershell
# Window 1: MCP logs
while ($true) { telnyx-edge logs refill-mcp --tail -n 5; Start-Sleep -Seconds 2 }

# Window 2: Webhook logs
while ($true) { telnyx-edge logs refill-webhook --tail -n 5; Start-Sleep -Seconds 2 }

# Window 3: Actor logs
while ($true) { telnyx-edge actors logs CallerSession --tail -n 5; Start-Sleep -Seconds 2 }
```

Or one-shot after each test:
```powershell
telnyx-edge logs refill-mcp -n 20
telnyx-edge logs refill-webhook -n 20
telnyx-edge actors logs CallerSession -n 20
```

---

## Test Data Reference

| Phone Number | Patient Name | DOB | Medications |
|---|---|---|---|
| `+15550000001` | Maria | 1962-03-15 | Lisinopril 10mg (2 left), Oxycodone 5mg (0 left), Metformin 500mg (1 left) |
| `+442045202115` | James | 1985-07-22 | Atorvastatin 20mg (3 left), Amoxicillin 500mg (0 left) |
| `+15551112222` | David | 1978-11-03 | Sertraline 50mg (2 left), Albuterol inhaler (1 left) |
| `+15552223333` | Sarah | 1991-06-08 | Levothyroxine 75mcg (5 left), Ibuprofen 400mg (2 left), Lorazepam 1mg (1 left) |
| `+15553334444` | Robert | 1955-09-19 | Warfarin 5mg (0 left), Furosemide 40mg (3 left) |

---

## Quick Command Reference

```powershell
# Check actor state for a caller key
$callerKey = "..."
Invoke-RestMethod -Uri "https://api.telnyx.com/v2/edge/functions/caller-session/rpc" `
  -Method POST `
  -Headers @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "X-Internal-Token" = $env:INTERNAL_TOKEN
    "X-Trace-Id" = "debug"
  } `
  -Body (@{
    method = "getRefills"
    caller_key = $callerKey
    args = @{} }
  | ConvertTo-Json)

# Check number of calls recorded
Invoke-RestMethod -Uri ".../caller-session/rpc" `
  -Body (@{
    method = "recordCall"
    caller_key = $callerKey
    args = @{ traceId = "debug" }
  } | ConvertTo-Json)
```

---

## Exit Criteria

A successful test session means:

- [ ] Scenario 1 works (happy path refill)
- [ ] Scenario 2 works (verification persists)
- [ ] Scenario 3 works (transfer rings pharmacist phone)
- [ ] Scenario 4 or 5 shows correct lockout behavior
- [ ] Scenario 6 shows after-hours message
- [ ] Scenario 7 shows refills disabled message
- [ ] All logs show `trace_id` propagation end-to-end
- [ ] No stack traces or 500s in any function log
