param(
    [string]$Workspace = "nyc-urban-analytics"
)

. (Join-Path $PSScriptRoot "common.ps1")

$ws = "$Workspace.Workspace"

foreach ($name in "df_ecb_fx", "df_worldbank_gdp") {
    $target = "$ws/$name.Dataflow"
    if (Test-FabPath $target) {
        Write-Host "$name already exists and was left unchanged"
        continue
    }
    Invoke-Checked $Fab @("import", $target, "-i", (Join-Path $Root "bronze\$name.Dataflow"), "-f")
}

Invoke-Checked $Fab @("ls", $ws)
