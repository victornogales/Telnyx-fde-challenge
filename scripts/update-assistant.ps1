# Update RefillLine assistant via API
# Usage: .\update-assistant.ps1

$assistantId = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"
$apiKey = $env:TELNYX_API_KEY

if (-not $apiKey) {
    Write-Host "ERROR: TELNYX_API_KEY environment variable not set" -ForegroundColor Red
    exit 1
}

# Read the workflow JSON
$workflowPath = Join-Path (Split-Path $MyInvocation.MyCommand.Path -Parent) ".." "assistant" "workflow.json"
$workflowJson = Get-Content -Path (Resolve-Path $workflowPath) -Raw | ConvertFrom-Json

# Build the payload
$payload = @{
    time_limit_secs = 300
    user_idle_timeout_secs = 45
    conversation_flow = $workflowJson.conversation_flow
}

$body = $payload | ConvertTo-Json -Depth 20
$uri = "https://api.telnyx.com/v2/ai/assistants/$assistantId"

Write-Host "Updating assistant $assistantId..." -ForegroundColor Yellow
Write-Host "Body length: $($body.Length) chars"

try {
    $response = Invoke-RestMethod -Uri $uri `
        -Method POST `
        -Headers @{
            "Authorization" = "Bearer $apiKey"
            "Content-Type" = "application/json"
            "Accept" = "application/json"
        } `
        -Body $body

    Write-Host "SUCCESS: Assistant updated" -ForegroundColor Green
    Write-Host "Assistant ID: $($response.data.id)"
    Write-Host "Name: $($response.data.name)"
    Write-Host "Version: $($response.data.version_id)"
} catch {
    Write-Host "ERROR: Failed to update assistant" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $reader.BaseStream.Position = 0
        $reader.DiscardBufferedData()
        $respBody = $reader.ReadToEnd()
        Write-Host "Response: $respBody"
    } else {
        Write-Host $_.Exception.Message
    }
}
