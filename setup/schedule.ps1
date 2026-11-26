param(
    [string]$Workspace = "nyc-urban-analytics",
    [string]$Pipeline = "pl_daily",
    [string]$Time = "03:00",
    [string]$TimeZone = "West Asia Standard Time",
    [string]$EndDate = "2027-01-21"
)

. (Join-Path $PSScriptRoot "common.ps1")

$ws = "$Workspace.Workspace"
$workspaceId = Get-FabValue $ws "id"
$pipelineId = Get-FabValue "$ws/$Pipeline.DataPipeline" "id"
$schedules = "workspaces/$workspaceId/items/$pipelineId/jobs/Pipeline/schedules"

$start = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, $TimeZone).AddMinutes(5)
$body = [ordered]@{
    enabled       = $true
    configuration = [ordered]@{
        startDateTime   = $start.ToString("yyyy-MM-dd'T'HH:mm:ss")
        endDateTime     = "$($EndDate)T23:59:00"
        localTimeZoneId = $TimeZone
        type            = "Daily"
        times           = @($Time)
    }
}
$request = Join-Path $env:TEMP "pipeline_schedule.json"
Write-Utf8 $request ($body | ConvertTo-Json -Depth 5)

$existing = @((Invoke-FabApi @($schedules)).value)
if ($existing.Count -gt 0) {
    Invoke-FabApi @("$schedules/$($existing[0].id)", "-X", "patch", "-i", $request) | Out-Null
}
else {
    Invoke-FabApi @($schedules, "-X", "post", "-i", $request) | Out-Null
}

(Invoke-FabApi @($schedules)).value | ForEach-Object {
    [pscustomobject]@{
        enabled  = $_.enabled
        type     = $_.configuration.type
        times    = $_.configuration.times -join ", "
        timeZone = $_.configuration.localTimeZoneId
        start    = $_.configuration.startDateTime
        end      = $_.configuration.endDateTime
    }
} | Format-Table -AutoSize
