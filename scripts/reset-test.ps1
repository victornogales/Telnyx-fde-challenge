# Pre-Test Reset Script for RefillLine Voice Tests
# Run this before each independent test scenario to reset actor state and flags
#
# Usage: .\scripts\reset-test.ps1
# Requires: $env:TELNYX_API_KEY, $env:INTERNAL_TOKEN, $env:KV_NAMESPACE_ID

$ErrorActionPreference = "Stop"

if (!$env:INTERNAL_TOKEN) {
    Write-Host "WARNING: INTERNAL_TOKEN not set. Actor reset may fail." -ForegroundColor Yellow
    $token = ""
} else {
    $token = $env:INTERNAL_TOKEN
}
# -------------------------------------------------------------
$e164 = "+15550000001"
$bytes = [System.Text.Encoding]::UTF8.GetBytes($e164)
$hash = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
$hex = ($hash | ForEach-Object { $_.ToString("x2") }) -join ""
$callerKey = $hex.Substring(0, 16)

Write-Host "Caller key: $callerKey" -ForegroundColor Cyan

# -------------------------------------------------------------
# 2. Reset actor state (clear failed attempts, refills, lock)
# -------------------------------------------------------------
Write-Host -NoNewline "Resetting actor state ... "

try {
    Invoke-RestMethod -Uri "https://api.telnyx.com/v2/edge/functions/caller-session/rpc" `
      -Method POST `
      -Headers @{
        "Authorization"      = "Bearer $env:TELNYX_API_KEY"
        "Content-Type"       = "application/json"
        "X-Internal-Token"   = $token
        "X-Trace-Id"         = "reset_test_$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
      } `
      -Body (@{
        method      = "recordVerificationAttempt"
        caller_key  = $callerKey
        args        = @{
          success      = $true
          traceId      = "reset"
          maxAttempts  = 3
        }
      } | ConvertTo-Json) | Out-Null

    Write-Host "OK" -ForegroundColor Green
} catch {
    Write-Host "WARN ($($_.Exception.Message))" -ForegroundColor Yellow
}

# -------------------------------------------------------------
# 3. Reset feature flags to defaults
# -------------------------------------------------------------
Write-Host -NoNewline "Resetting flags (refills_enabled=true, after_hours=false) ... "

try {
    Invoke-RestMethod `
      -Uri "https://api.telnyx.com/v2/storage/kvs/$($env:KV_NAMESPACE_ID)/keys/flag%2Frefills_enabled" `
      -Method PUT `
      -Headers @{
        "Authorization" = "Bearer $env:TELNYX_API_KEY"
        "Content-Type"  = "application/json"
      } `
      -Body (@{ value = "true" } | ConvertTo-Json) | Out-Null

    Invoke-RestMethod `
      -Uri "https://api.telnyx.com/v2/storage/kvs/$($env:KV_NAMESPACE_ID)/keys/flag%2Fafter_hours_mode" `
      -Method PUT `
      -Headers @{
        "Authorization" = "Bearer $env:TELNYX_API_KEY"
        "Content-Type"  = "application/json"
      } `
      -Body (@{ value = "false" } | ConvertTo-Json) | Out-Null

    Write-Host "OK" -ForegroundColor Green
} catch [System.Net.WebException] {
    # 404 means the key doesn't exist yet - that's fine, we just need to create it
    if ($_.Exception.Response.StatusCode -eq 404) {
        Write-Host "OK (keys not yet created, will be set on first use)" -ForegroundColor Green
    } else {
        Write-Host "FAIL ($($_.Exception.Message))" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "FAIL ($($_.Exception.Message))" -ForegroundColor Red
    exit 1
}

Write-Host "`nReset complete. Ready to test.`n" -ForegroundColor Cyan
