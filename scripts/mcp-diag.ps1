$MCP_URL = "https://refill-mcp-6a4810fb-9.telnyxcompute.com"
$MCP_TOKEN = $env:MCP_TOKEN
if (-not $MCP_TOKEN) {
    Write-Host "ERROR: set `$env:MCP_TOKEN first (same value as the MCP_TOKEN edge secret)." -ForegroundColor Red
    exit 1
}

Write-Host "=== MCP Server Diagnostics ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Health endpoint
Write-Host "1. Health check (/health):" -ForegroundColor Yellow
$health = & curl.exe -s "$MCP_URL/health"
Write-Host $health
Write-Host ""

# Test 2: initialize
Write-Host "2. MCP initialize:" -ForegroundColor Yellow
$initBody = '{"jsonrpc":"2.0","id":"diag-1","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"diag","version":"1.0"}}}'
$init = & curl.exe -s -X POST "$MCP_URL/mcp" -H "Content-Type: application/json" -H "Authorization: Bearer $MCP_TOKEN" -d $initBody
Write-Host $init | ConvertFrom-Json | ConvertTo-Json
Write-Host ""

# Test 3: tools/list
Write-Host "3. MCP tools/list:" -ForegroundColor Yellow
$toolsBody = '{"jsonrpc":"2.0","id":"diag-2","method":"tools/list","params":{}}'
$tools = & curl.exe -s -X POST "$MCP_URL/mcp" -H "Content-Type: application/json" -H "Authorization: Bearer $MCP_TOKEN" -d $toolsBody
Write-Host $tools | ConvertFrom-Json | ConvertTo-Json
Write-Host ""

# Test 4: get_pharmacy_info
Write-Host "4. Tool get_pharmacy_info:" -ForegroundColor Yellow
$pharmBody = '{"jsonrpc":"2.0","id":"diag-3","method":"tools/call","params":{"name":"get_pharmacy_info","arguments":{"trace_id":"tr_email"}}}'
$pharm = & curl.exe -s -X POST "$MCP_URL/mcp" -H "Content-Type: application/json" -H "Authorization: Bearer $MCP_TOKEN" -d $pharmBody
Write-Host $pharm | ConvertFrom-Json | ConvertTo-Json
Write-Host ""

Write-Host "=== End Diagnostics ===" -ForegroundColor Cyan
