param(
    [Parameter(Mandatory)][string]$Notebook,
    [Parameter(Mandatory)][string]$Folder,
    [string]$Lakehouse = "lh_bronze",
    [string]$Workspace = "nyc-urban-analytics"
)

. (Join-Path $PSScriptRoot "common.ps1")

$ws = "$Workspace.Workspace"
$workspaceId = Get-FabValue $ws "id"
$lakehouseId = Get-FabValue "$ws/$Lakehouse.Lakehouse" "id"

$source = Join-Path $Root "$Folder\$Notebook.Notebook\notebook-content.py"
$content = (Get-Content $source -Raw).Replace("{{WORKSPACE_ID}}", $workspaceId).Replace("{{LAKEHOUSE_ID}}", $lakehouseId).Replace("{{LAKEHOUSE_NAME}}", $Lakehouse)
foreach ($token in [regex]::Matches($content, "\{\{(LH_[A-Z]+)_ID\}\}") | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique) {
    $content = $content.Replace("{{$($token)_ID}}", (Get-FabValue "$ws/$($token.ToLower()).Lakehouse" "id"))
}
foreach ($token in [regex]::Matches($content, "\{\{WH_([A-Z]+)_SERVER\}\}") | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique) {
    $warehouseId = Get-FabValue "$ws/wh_$($token.ToLower()).Warehouse" "id"
    $server = (Invoke-FabApi @("workspaces/$workspaceId/warehouses/$warehouseId")).properties.connectionString
    $content = $content.Replace("{{WH_$($token)_SERVER}}", $server)
}
if ($content -match "\{\{[A-Z_]+\}\}") {
    throw "Unresolved placeholder in $source : $($Matches[0])"
}

$build = Join-Path $Root "build\$Notebook.Notebook"
if (Test-Path $build) {
    Remove-Item $build -Recurse -Force
}
New-Item -ItemType Directory $build | Out-Null
Write-Utf8 (Join-Path $build "notebook-content.py") $content

$platform = [ordered]@{
    '$schema' = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
    metadata  = [ordered]@{ type = "Notebook"; displayName = $Notebook }
    config    = [ordered]@{ version = "2.0"; logicalId = "00000000-0000-0000-0000-000000000000" }
}
Write-Utf8 (Join-Path $build ".platform") ($platform | ConvertTo-Json -Depth 5)

Invoke-Checked $Fab @("import", "$ws/$Notebook.Notebook", "-i", $build, "--format", ".py", "-f")
Write-Host "Notebook $Notebook : $(Get-FabValue "$ws/$Notebook.Notebook" "id")"
