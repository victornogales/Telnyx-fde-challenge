# Toggle after-hours mode KV flag for RefillLine testing
# Usage: .\scripts\toggle-after-hours.ps1
# Requires $env:TELNYX_API_KEY and $env:KV_NAMESPACE_ID to be set

param()

$ErrorActionPreference = "Stop"

if (-not $env:TELNYX_API_KEY) {
    Write-Host "ERROR: TELNYX_API_KEY environment variable is not set." -ForegroundColor Red
    Write-Host "Run first: `$env:TELNYX_API_KEY = 'KEY018_...'"
    exit 1
}

if (-not $env:KV_NAMESPACE_ID) {
    Write-Host "ERROR: KV_NAMESPACE_ID environment variable is not set." -ForegroundColor Red
    Write-Host "Run first: `$env:KV_NAMESPACE_ID = '3208b4c8-7ac1-4f42-a73d-ab9bfd4fc8ee'"
    exit 1
}

$uri = "https://api.telnyx.com/v2/storage/kvs/$env:KV_NAMESPACE_ID/keys/flag%2Fafter_hours_mode"
$headers = @{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Accept"        = "application/json"
}

# Read current value
try {
    $resp = Invoke-RestMethod -Uri $uri -Method Get -Headers $headers -TimeoutSec 10
    $current = $resp.data.value
    Write-Host "Current after_hours_mode flag value: $current"
} catch {
    Write-Host "Could not read current value (flag may not exist yet). Assuming false." -ForegroundColor Yellow
    $current = "false"
}

# Determine target value
$target = if ($current -eq "true") { "false" } else { "true" }
$label  = if ($target -eq "true") { "AFTER-HOURS (closed)" } else { "NORMAL HOURS (open)" }

Write-Host ""
Write-Host "This will set after_hours_mode to $target ($label)."
$confirm = Read-Host "Confirm? [y/N]"

if ($confirm -notin @("y","Y")) {
    Write-Host "Aborted. No changes made."
    exit 0
}

# Write new value
$body = @{ value = $target } | ConvertTo-Json
Invoke-RestMethod -Uri $uri -Method Put -Headers (@{
    "Authorization" = "Bearer $env:TELNYX_API_KEY"
    "Content-Type"  = "application/json"
}) -Body $body -TimeoutSec 10 | Out-Null

Write-Host ""
Write-Host "SUCCESS! after_hours_mode set to $target ($label)" -ForegroundColor Green

if ($target -eq "true") {
    Write-Host ""
    Write-Host "Next: call +442045202115. The assistant should say:"
    Write-Host '"Maple Pharmacy is currently closed. Our hours are 8am to 8pm, Monday to Saturday."'
} else {
    Write-Host ""
    Write-Host "Next: call +442045202115. The assistant should behave normally."
}
