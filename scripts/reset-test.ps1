# Pre-Test Reset Script for RefillLine Voice Tests
# Run this before each independent test scenario to reset actor state and flags
#
# Usage: .\scripts\reset-test.ps1                      # synthetic demo caller (+15550000001)
#        .\scripts\reset-test.ps1 -Number +44XXXXXXXXXX # the phone you will actually call from
# Requires: $env:TELNYX_API_KEY, $env:INTERNAL_TOKEN, $env:KV_NAMESPACE_ID
# The actor is keyed by the caller's number, so reset the number you dial from.

param(
    [string]$Number = "+15550000001"
)

$ErrorActionPreference = "Stop"

if ($Number -notmatch '^\+[1-9]\d{6,14}$') {
    Write-Host "ERROR: -Number must be in E.164 format, e.g. +15550000001" -ForegroundColor Red
    exit 1
}

# -------------------------------------------------------------
# 0. Validate required environment variables
# -------------------------------------------------------------
$missing = @()

if (!$env:TELNYX_API_KEY) {
    $missing += "TELNYX_API_KEY"
}

if (!$env:INTERNAL_TOKEN) {
    $missing += "INTERNAL_TOKEN"
}

if (!$env:KV_NAMESPACE_ID) {
    $missing += "KV_NAMESPACE_ID"
}

if ($missing.Count -gt 0) {
    Write-Host "ERROR: Missing environment variables: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "" 
    Write-Host "Set them in PowerShell before running this script:" -ForegroundColor Yellow
    Write-Host "  `$env:TELNYX_API_KEY    = 'YOUR_API_KEY'" -ForegroundColor Cyan
    Write-Host "  `$env:INTERNAL_TOKEN    = 'YOUR_INTERNAL_TOKEN'" -ForegroundColor Cyan
    Write-Host "  `$env:KV_NAMESPACE_ID   = 'YOUR_KV_NAMESPACE'" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To get KV_NAMESPACE_ID, visit: https://portal.telnyx.com/app/storage" -ForegroundColor Yellow
    Write-Host "To get INTERNAL_TOKEN, check your func.toml or run: telnyx-edge secrets list" -ForegroundColor Yellow
    exit 1
}

# -------------------------------------------------------------
# 1. Compute caller key for the given number (sha256 prefix, same as the functions)
# -------------------------------------------------------------
$e164 = $Number
$bytes = [System.Text.Encoding]::UTF8.GetBytes($e164)
$hash = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
$hex = ($hash | ForEach-Object { $_.ToString("x2") }) -join ""
$callerKey = $hex.Substring(0, 16)

Write-Host "Caller key: $callerKey" -ForegroundColor Cyan

# -------------------------------------------------------------
# 2. Reset actor state via RPC (direct function URL)
#    The Telnyx API endpoint does NOT expose actor RPC.
#    We must POST to the function's own invoke URL /rpc.
# -------------------------------------------------------------
Write-Host -NoNewline "Resetting actor state ... "

try {
    # The invoke URL is fixed for this deployment
    $rpcUrl = "https://caller-session-51645523-7.telnyxcompute.com/rpc"

    $resp = Invoke-RestMethod -Uri $rpcUrl `
      -Method POST `
      -Headers @{
        "Content-Type"       = "application/json"
        "X-Internal-Token"   = $env:INTERNAL_TOKEN
        "X-Trace-Id"         = "reset_test_$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
      } `
      -Body (@{
        method      = "resetState"
        caller_key  = $callerKey
        args        = @{
          traceId = "reset"
          full    = $true
        }
      } | ConvertTo-Json)

    if ($resp.ok -eq $true) {
        Write-Host "OK (cleared: $($resp.result.cleared -join ', '))" -ForegroundColor Green
    } else {
        Write-Host "FAIL (actor error: $($resp.error))" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "FAIL ($($_.Exception.Message))" -ForegroundColor Red
    exit 1
}

# -------------------------------------------------------------
# 3. Reset feature flags to defaults via Telnyx KV API
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
