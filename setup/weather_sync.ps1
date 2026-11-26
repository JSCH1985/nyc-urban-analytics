param(
    [string]$Workspace = "nyc-urban-analytics",
    [string]$At = "04:00",
    [switch]$Full
)

. (Join-Path $PSScriptRoot "common.ps1")

$workspaceId = Get-FabValue "$Workspace.Workspace" "id"
$warehouseId = Get-FabValue "$Workspace.Workspace/wh_gold.Warehouse" "id"
$server = (Invoke-FabApi @("workspaces/$workspaceId/warehouses/$warehouseId")).properties.connectionString

Push-Location $Root
try {
    $arguments = @("-m", "integrations.weather_sync", "--server", $server)
    if ($Full) {
        $arguments += "--full"
    }
    Invoke-Checked $Python $arguments
}
finally {
    Pop-Location
}

$logs = Join-Path $Root "build\logs"
New-Item -ItemType Directory $logs -Force | Out-Null
$action = New-ScheduledTaskAction -Execute (Join-Path $Venv "Scripts\pythonw.exe") -Argument "-m integrations.weather_sync --server $server --unattended --log `"$(Join-Path $logs 'weather_sync.log')`"" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "nyc-urban-analytics weather sync" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Get-ScheduledTask -TaskName "nyc-urban-analytics weather sync" | Get-ScheduledTaskInfo | Select-Object TaskName, NextRunTime | Format-Table -AutoSize
