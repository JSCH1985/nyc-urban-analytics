param(
    [string]$Workspace = "nyc-urban-analytics",
    [int]$FromYear = 2019,
    [int]$ToYear = (Get-Date).Year,
    [string]$Notebook = "nb_bronze_openaq_backfill"
)

. (Join-Path $PSScriptRoot "common.ps1")

if (-not $env:OPENAQ_API_KEY) {
    $env:OPENAQ_API_KEY = [Environment]::GetEnvironmentVariable("OPENAQ_API_KEY", "User")
}
if (-not $env:OPENAQ_API_KEY) {
    throw "OPENAQ_API_KEY is not set"
}

& (Join-Path $PSScriptRoot "deploy_notebook.ps1") -Notebook $Notebook -Folder bronze -Lakehouse lh_bronze -Workspace $Workspace
foreach ($year in $FromYear..$ToYear) {
    Write-Host "$(Get-Date -Format HH:mm:ss) $year started"
    Invoke-Notebook $Workspace $Notebook "years:string=$year,api_key:string=$($env:OPENAQ_API_KEY)"
    Write-Host "$(Get-Date -Format HH:mm:ss) $year finished"
}

& (Join-Path $PSScriptRoot "show_audit.ps1") -Name openaq_backfill -Lakehouse lh_bronze -Workspace $Workspace
