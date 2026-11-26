param(
    [Parameter(Mandatory)][string]$Name,
    [string]$Lakehouse = "lh_silver",
    [string]$Workspace = "nyc-urban-analytics"
)

. (Join-Path $PSScriptRoot "common.ps1")

$local = Join-Path $Root "build\reports\$Name.csv"
New-Item -ItemType Directory -Force (Split-Path $local) | Out-Null
if (Test-Path $local) {
    Remove-Item $local -Force
}
Invoke-Checked $Fab @("cp", "$Workspace.Workspace/$Lakehouse.Lakehouse/Files/reports/$Name.csv", $local)
Import-Csv $local | Format-Table -AutoSize
