# RefillLine Smoke Test (PowerShell)
# Tests: refill-mcp, refill-webhook, caller-session
# Run from repo root: .\scripts\smoke.ps1

$ErrorActionPreference = "Stop"

$MCP_URL = "https://refill-mcp-6a4810fb-9.telnyxcompute.com"
$WEBHOOK_URL = "https://refill-webhook-8d5c4fc7-b.telnyxcompute.com"
$GATEWAY_URL = "https://caller-session-51645523-7.telnyxcompute.com"
$MCP_TOKEN = "REPLACE_WITH_ENV_MCP_TOKEN"
$INTERNAL_TOKEN = (Get-Content ~/.telnyx-edge/config.toml | Select-String "api_key").Line.Split('"')[1]

function Test-Health($name, $url) {
    Write-Host -NoNewline "Health $name ... "
    if ($name -eq "refill-webhook") {
        # Webhook only has POST /, not GET /health
        Write-Host "SKIP (no /health)" -ForegroundColor Yellow
        return $true
    }
    $resp = Invoke-RestMethod -Uri "$url/health" -TimeoutSec 5
    if ($resp.ok -eq $true) {
        Write-Host "OK (kv=$($resp.kv), gateway=$($resp.gateway))" -ForegroundColor Green
        return $true
    } else {
        Write-Host "FAIL" -ForegroundColor Red
        return $false
    }
}

function Test-McpInitialize() {
    Write-Host -NoNewline "MCP initialize ... "
    $body = @{
        jsonrpc = "2.0"
        id = "smoke-init"
        method = "initialize"
        params = @{
            protocolVersion = "2024-11-05"
            capabilities = @{}
            clientInfo = @{ name = "smoke"; version = "1.0" }
        }
    } | ConvertTo-Json -Depth 5

    $resp = Invoke-RestMethod -Uri "$MCP_URL/mcp" -Method Post -Headers @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $MCP_TOKEN"
    } -Body $body

    if ($resp.result.serverInfo.name -eq "refill-mcp") {
        Write-Host "OK" -ForegroundColor Green
        return $true
    } else {
        Write-Host "FAIL" -ForegroundColor Red
        return $false
    }
}

function Test-McpToolsList() {
    Write-Host -NoNewline "MCP tools/list ... "
    $body = @{
        jsonrpc = "2.0"
        id = "smoke-tools"
        method = "tools/list"
        params = @{}
    } | ConvertTo-Json -Depth 3

    $resp = Invoke-RestMethod -Uri "$MCP_URL/mcp" -Method Post -Headers @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $MCP_TOKEN"
    } -Body $body

    $toolNames = $resp.result.tools | ForEach-Object { $_.name }
    $expected = @("verify_identity", "list_prescriptions", "request_refill", "get_refill_status", "get_medication_info", "get_pharmacy_info")
    $missing = $expected | Where-Object { $_ -notin $toolNames }

    if ($missing.Count -eq 0) {
        Write-Host "OK (6 tools)" -ForegroundColor Green
        return $true
    } else {
        Write-Host "FAIL (missing: $($missing -join ', '))" -ForegroundColor Red
        return $false
    }
}

function Test-McpPharmacyInfo() {
    Write-Host -NoNewline "MCP get_pharmacy_info ... "
    $body = @{
        jsonrpc = "2.0"
        id = "smoke-pharmacy"
        method = "tools/call"
        params = @{
            name = "get_pharmacy_info"
            arguments = @{ trace_id = "tr_smoke" }
        }
    } | ConvertTo-Json -Depth 5

    $resp = Invoke-RestMethod -Uri "$MCP_URL/mcp" -Method Post -Headers @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $MCP_TOKEN"
    } -Body $body

    if ($resp.result.isError -eq $false) {
        Write-Host "OK" -ForegroundColor Green
        return $true
    } else {
        Write-Host "FAIL" -ForegroundColor Red
        return $false
    }
}

function Test-McpVerifyAndRefill() {
    Write-Host -NoNewline "MCP verify_identity (Maria) ... "
    $body = @{
        jsonrpc = "2.0"
        id = "smoke-verify"
        method = "tools/call"
        params = @{
            name = "verify_identity"
            arguments = @{
                caller = "+15550000001"
                dob = "1962-03-15"
                trace_id = "tr_smoke"
            }
        }
    } | ConvertTo-Json -Depth 5

    $resp = Invoke-RestMethod -Uri "$MCP_URL/mcp" -Method Post -Headers @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $MCP_TOKEN"
    } -Body $body

    if ($resp.result.isError -eq $false) {
        Write-Host "OK" -ForegroundColor Green
    } else {
        Write-Host "FAIL" -ForegroundColor Red
        return $false
    }

    Write-Host -NoNewline "MCP list_prescriptions (after verify) ... "
    $body = @{
        jsonrpc = "2.0"
        id = "smoke-list"
        method = "tools/call"
        params = @{
            name = "list_prescriptions"
            arguments = @{
                caller = "+15550000001"
                trace_id = "tr_smoke"
            }
        }
    } | ConvertTo-Json -Depth 5

    $resp = Invoke-RestMethod -Uri "$MCP_URL/mcp" -Method Post -Headers @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $MCP_TOKEN"
    } -Body $body

    if ($resp.result.isError -eq $false) {
        Write-Host "OK" -ForegroundColor Green
    } else {
        Write-Host "FAIL" -ForegroundColor Red
        return $false
    }

    Write-Host -NoNewline "MCP request_refill (Lisinopril) ... "
    $body = @{
        jsonrpc = "2.0"
        id = "smoke-refill"
        method = "tools/call"
        params = @{
            name = "request_refill"
            arguments = @{
                caller = "+15550000001"
                rx_id = "rx-mar-001"
                trace_id = "tr_smoke"
            }
        }
    } | ConvertTo-Json -Depth 5

    $resp = Invoke-RestMethod -Uri "$MCP_URL/mcp" -Method Post -Headers @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $MCP_TOKEN"
    } -Body $body

    if ($resp.result.isError -eq $false) {
        Write-Host "OK" -ForegroundColor Green
    } else {
        Write-Host "FAIL" -ForegroundColor Red
        return $false
    }

    Write-Host -NoNewline "MCP get_refill_status ... "
    $body = @{
        jsonrpc = "2.0"
        id = "smoke-status"
        method = "tools/call"
        params = @{
            name = "get_refill_status"
            arguments = @{
                caller = "+15550000001"
                trace_id = "tr_smoke"
            }
        }
    } | ConvertTo-Json -Depth 5

    $resp = Invoke-RestMethod -Uri "$MCP_URL/mcp" -Method Post -Headers @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $MCP_TOKEN"
    } -Body $body

    if ($resp.result.isError -eq $false) {
        Write-Host "OK" -ForegroundColor Green
        return $true
    } else {
        Write-Host "FAIL" -ForegroundColor Red
        return $false
    }
}

function Test-McpMedicationInfo() {
    Write-Host -NoNewline "MCP get_medication_info (Lisinopril) ... "
    $body = @{
        jsonrpc = "2.0"
        id = "smoke-medication"
        method = "tools/call"
        params = @{
            name = "get_medication_info"
            arguments = @{
                name = "Lisinopril"
                trace_id = "tr_smoke"
            }
        }
    } | ConvertTo-Json -Depth 5

    $resp = Invoke-RestMethod -Uri "$MCP_URL/mcp" -Method Post -Headers @{
        "Content-Type" = "application/json"
        "Authorization" = "Bearer $MCP_TOKEN"
    } -Body $body

    if ($resp.result.isError -eq $false) {
        Write-Host "OK" -ForegroundColor Green
        return $true
    } else {
        Write-Host "FAIL" -ForegroundColor Red
        return $false
    }
}

function Test-GatewayRecordCall() {
    Write-Host -NoNewline "Gateway recordCall ... "
    Write-Host "SKIP (internal endpoint)" -ForegroundColor Yellow
    return $true
}

function Test-Webhook() {
    Write-Host -NoNewline "Webhook dynamic variables ... "
    $payload = @{
        data = @{
            event_type = "assistant.initialization"
            id = "evt_smoke"
            payload = @{
                telnyx_conversation_channel = "phone_call"
                telnyx_agent_target = "+442045202115"
                telnyx_end_user_target = "+15550000001"
                call_control_id = "cc_smoke"
                assistant_id = "assistant_smoke"
            }
        }
    } | ConvertTo-Json -Depth 5

    try {
        $resp = Invoke-RestMethod -Uri "$WEBHOOK_URL/" -Method Post -Headers @{
            "Content-Type" = "application/json"
        } -Body $payload -TimeoutSec 5

        if ($resp.dynamic_variables.is_known_caller -eq "true") {
            Write-Host "OK (known=$($resp.dynamic_variables.is_known_caller))" -ForegroundColor Green
            return $true
        } else {
            Write-Host "FAIL (not known)" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "FAIL ($($_.Exception.Message))" -ForegroundColor Red
        return $false
    }
}

# ── Run all tests ──
Write-Host "`n=== RefillLine Smoke Tests ===`n" -ForegroundColor Cyan

$results = @()
$results += Test-Health "refill-mcp" $MCP_URL
$results += Test-Health "refill-webhook" $WEBHOOK_URL
$results += Test-Health "caller-session" $GATEWAY_URL
$results += Test-McpInitialize
$results += Test-McpToolsList
$results += Test-McpPharmacyInfo
$results += Test-McpVerifyAndRefill
$results += Test-McpMedicationInfo
$results += Test-GatewayRecordCall
$results += Test-Webhook

$passed = ($results | Where-Object { $_ -eq $true }).Count
$total = $results.Count

Write-Host "`n=== Results: $passed / $total passed ===`n" -ForegroundColor $(if ($passed -eq $total) { "Green" } else { "Yellow" })

if ($passed -eq $total) {
    exit 0
} else {
    exit 1
}
