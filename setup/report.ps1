param(
    [string]$Workspace = "nyc-urban-analytics",
    [string]$Report = "rpt_nyc_urban"
)

. (Join-Path $PSScriptRoot "common.ps1")

$ws = "$Workspace.Workspace"
$source = Join-Path $Root "report\$Report.Report"
foreach ($required in "definition.pbir", "definition\report.json", "definition\version.json", "StaticResources") {
    if (-not (Test-Path (Join-Path $source $required))) {
        throw "report\$Report.Report\$required is missing"
    }
}

$build = Join-Path $Root "build\$Report.Report"
if (Test-Path $build) {
    Remove-Item $build -Recurse -Force
}
Copy-Item $source $build -Recurse
$platform = [ordered]@{
    '$schema' = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
    metadata  = [ordered]@{ type = "Report"; displayName = $Report }
    config    = [ordered]@{ version = "2.0"; logicalId = "00000000-0000-0000-0000-000000000000" }
}
Write-Utf8 (Join-Path $build ".platform") ($platform | ConvertTo-Json -Depth 5)
Invoke-Checked $Fab @("import", "$ws/$Report.Report", "-i", $build, "-f")

$workspaceId = Get-FabValue $ws "id"
$reportId = Get-FabValue "$ws/$Report.Report" "id"
Write-Host "https://app.fabric.microsoft.com/groups/$workspaceId/reports/$reportId"
