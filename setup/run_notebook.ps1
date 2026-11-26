param(
    [Parameter(Mandatory)][string]$Notebook,
    [string]$Parameters = "",
    [string]$Workspace = "nyc-urban-analytics",
    [int]$WaitMinutes = 180
)

. (Join-Path $PSScriptRoot "common.ps1")

Write-Host "$(Get-Date -Format HH:mm:ss) $Notebook started"
Invoke-Notebook $Workspace $Notebook $Parameters $WaitMinutes
Write-Host "$(Get-Date -Format HH:mm:ss) $Notebook finished"
