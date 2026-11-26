param(
    [Parameter(Mandatory)][string]$Capacity,
    [string]$Workspace = "nyc-urban-analytics"
)

. (Join-Path $PSScriptRoot "common.ps1")

$ws = "$Workspace.Workspace"

if (-not (Test-FabPath $ws)) {
    Invoke-Checked $Fab @("create", $ws, "-P", "capacityname=$Capacity")
}

foreach ($item in "lh_bronze.Lakehouse", "lh_silver.Lakehouse", "wh_gold.Warehouse") {
    if (-not (Test-FabPath "$ws/$item")) {
        Invoke-Checked $Fab @("create", "$ws/$item")
    }
}

Invoke-Checked $Fab @("ls", $ws, "-l")
