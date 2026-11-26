param(
    [string]$Workspace = "nyc-urban-analytics",
    [string]$ConnectionName = "tlc_cloudfront",
    [string]$Url = "https://d37ci6vzurychx.cloudfront.net",
    [string]$Pipeline = "pl_taxi_copy"
)

. (Join-Path $PSScriptRoot "common.ps1")

$ws = "$Workspace.Workspace"
$guid = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

$connectionId = Get-AnonymousConnection $ConnectionName "HttpServer" $Url
$workspaceId = Get-FabValue $ws "id"
$lakehouseId = Get-FabValue "$ws/lh_bronze.Lakehouse" "id"

foreach ($id in $connectionId, $workspaceId, $lakehouseId) {
    if ($id -notmatch $guid) {
        throw "Expected an id but got '$id'"
    }
}

$template = Get-Content (Join-Path $Root "bronze\$Pipeline\pipeline-content.json") -Raw
$content = $template.Replace("{{CONNECTION_ID}}", $connectionId).Replace("{{WORKSPACE_ID}}", $workspaceId).Replace("{{LAKEHOUSE_ID}}", $lakehouseId)

$build = Join-Path $Root "build\$Pipeline.DataPipeline"
New-Item -ItemType Directory -Force $build | Out-Null
Write-Utf8 (Join-Path $build "pipeline-content.json") $content

$platform = [ordered]@{
    '$schema' = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
    metadata  = [ordered]@{ type = "DataPipeline"; displayName = $Pipeline }
    config    = [ordered]@{ version = "2.0"; logicalId = "00000000-0000-0000-0000-000000000000" }
}
Write-Utf8 (Join-Path $build ".platform") ($platform | ConvertTo-Json -Depth 5)

Invoke-Checked $Fab @("import", "$ws/$Pipeline.DataPipeline", "-i", $build, "-f")
Write-Host "Connection $ConnectionName : $connectionId"
Write-Host "Pipeline $Pipeline : $(Get-FabValue "$ws/$Pipeline.DataPipeline" "id")"
