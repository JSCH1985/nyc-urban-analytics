param(
    [string]$Workspace = "nyc-urban-analytics",
    [string]$Pipeline = "pl_daily",
    [switch]$Run
)

. (Join-Path $PSScriptRoot "common.ps1")

$ws = "$Workspace.Workspace"
$content = Get-Content (Join-Path $Root "orchestration\$Pipeline\pipeline-content.json") -Raw
$content = $content.Replace("{{WORKSPACE_ID}}", (Get-FabValue $ws "id"))
foreach ($notebook in [regex]::Matches($content, "\{\{(NB_[A-Z_]+)_ID\}\}") | ForEach-Object { $_.Groups[1].Value.ToLower() } | Select-Object -Unique) {
    $folder = $notebook.Split("_")[1]
    $lakehouse = if ($folder -eq "bronze") { "lh_bronze" } else { "lh_silver" }
    & (Join-Path $PSScriptRoot "deploy_notebook.ps1") -Notebook $notebook -Folder $folder -Lakehouse $lakehouse -Workspace $Workspace
}
$types = @{ PL = "DataPipeline"; DF = "Dataflow"; NB = "Notebook" }
foreach ($token in [regex]::Matches($content, "\{\{((PL|DF|NB)_[A-Z_]+)_ID\}\}") | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique) {
    $item = "$ws/$($token.ToLower()).$($types[$token.Substring(0, 2)])"
    $id = Get-FabValue $item "id"
    if ($id -notmatch "^[0-9a-f-]{36}$") {
        throw "$item has no id"
    }
    $content = $content.Replace("{{$($token)_ID}}", $id)
}
if ($content -match "\{\{[A-Z_]+\}\}") {
    throw "Unresolved placeholder: $($Matches[0])"
}

$build = Join-Path $Root "build\$Pipeline.DataPipeline"
if (Test-Path $build) {
    Remove-Item $build -Recurse -Force
}
New-Item -ItemType Directory $build | Out-Null
Write-Utf8 (Join-Path $build "pipeline-content.json") $content
$platform = [ordered]@{
    '$schema' = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
    metadata  = [ordered]@{ type = "DataPipeline"; displayName = $Pipeline }
    config    = [ordered]@{ version = "2.0"; logicalId = "00000000-0000-0000-0000-000000000000" }
}
Write-Utf8 (Join-Path $build ".platform") ($platform | ConvertTo-Json -Depth 5)
Invoke-Checked $Fab @("import", "$ws/$Pipeline.DataPipeline", "-i", $build, "-f")
Write-Host "Pipeline $Pipeline : $(Get-FabValue "$ws/$Pipeline.DataPipeline" "id")"

if ($Run) {
    Write-Host "$(Get-Date -Format HH:mm:ss) $Pipeline started"
    Invoke-Checked $Fab @("job", "run", "$ws/$Pipeline.DataPipeline")
    Write-Host "$(Get-Date -Format HH:mm:ss) $Pipeline finished"
}
