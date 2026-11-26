param(
    [string]$Workspace = "nyc-urban-analytics",
    [string]$Model = "sm_nyc_urban"
)

. (Join-Path $PSScriptRoot "common.ps1")

$ws = "$Workspace.Workspace"
$workspaceId = Get-FabValue $ws "id"
$warehouseId = Get-FabValue "$ws/wh_gold.Warehouse" "id"
$server = (Invoke-FabApi @("workspaces/$workspaceId/warehouses/$warehouseId")).properties.connectionString

$build = Join-Path $Root "build\$Model.SemanticModel"
if (Test-Path $build) {
    Remove-Item $build -Recurse -Force
}
Copy-Item (Join-Path $Root "semantic\$Model.SemanticModel") $build -Recurse
foreach ($file in Get-ChildItem $build -Recurse -File) {
    $text = [IO.File]::ReadAllText($file.FullName).Replace("{{WH_GOLD_SERVER}}", $server).Replace("{{WH_GOLD_ID}}", $warehouseId)
    if ($text -match "\{\{[A-Z_]+\}\}") {
        throw "Unresolved placeholder in $($file.Name): $($Matches[0])"
    }
    Write-Utf8 $file.FullName $text
}
$platform = [ordered]@{
    '$schema' = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
    metadata  = [ordered]@{ type = "SemanticModel"; displayName = $Model }
    config    = [ordered]@{ version = "2.0"; logicalId = "00000000-0000-0000-0000-000000000000" }
}
Write-Utf8 (Join-Path $build ".platform") ($platform | ConvertTo-Json -Depth 5)
Invoke-Checked $Fab @("import", "$ws/$Model.SemanticModel", "-i", $build, "-f")
$modelId = Get-FabValue "$ws/$Model.SemanticModel" "id"
$dataset = "groups/$workspaceId/datasets/$modelId"

$request = Join-Path $env:TEMP "model_refresh.json"
Write-Utf8 $request '{"type":"full"}'
Invoke-FabApi @("$dataset/refreshes", "-A", "powerbi", "-X", "post", "-i", $request) | Out-Null
$deadline = (Get-Date).AddMinutes(15)
do {
    Start-Sleep -Seconds 10
    $refresh = (Invoke-FabApi @("$dataset/refreshes?`$top=1", "-A", "powerbi")).value | Select-Object -First 1
    Write-Host "$(Get-Date -Format HH:mm:ss) refresh $($refresh.status)"
} while ($refresh.status -eq "Unknown" -and (Get-Date) -lt $deadline)
if ($refresh.status -ne "Completed") {
    throw "Refresh ended as $($refresh.status): $($refresh.serviceExceptionJson)"
}

function Invoke-Dax([string]$Query) {
    $request = Join-Path $env:TEMP "model_query.json"
    Write-Utf8 $request (@{ queries = @(@{ query = $Query }); serializerSettings = @{ includeNulls = $true } } | ConvertTo-Json -Depth 5)
    (Invoke-FabApi @("$dataset/executeQueries", "-A", "powerbi", "-X", "post", "-i", $request)).results[0].tables[0].rows
}

Invoke-Dax 'EVALUATE ROW("Trips", [Trips], "Hourly Trips", [Hourly Trips], "Revenue USD", [Revenue USD], "Revenue EUR", [Revenue EUR], "Tip Rate", [Tip Rate], "Avg PM2.5", [Avg PM2.5 ug/m3], "Avg NO2", [Avg NO2 ppb], "Avg O3", [Avg O3 ppb], "Monitors", [Monitors], "GDP 2024", CALCULATE([GDP USD], DimDate[Year] = 2024))' | Format-List
Invoke-Dax 'EVALUATE SUMMARIZECOLUMNS(DimZone[Borough], "Trips", [Trips], "Monitors", [Monitors], "Avg PM2.5", [Avg PM2.5 ug/m3], "Avg NO2", [Avg NO2 ppb])' | Format-Table -AutoSize
$deployed = Join-Path $Root "build\deployed"
if (Test-Path $deployed) {
    Remove-Item $deployed -Recurse -Force
}
New-Item -ItemType Directory $deployed | Out-Null
Invoke-Checked $Fab @("export", "$ws/$Model.SemanticModel", "-o", $deployed, "-f")
Get-ChildItem $deployed -Recurse -Filter "*.tmdl" | Where-Object { $_.Directory.Name -eq "roles" } | Select-String "tablePermission" | ForEach-Object { $_.Line.Trim() }
