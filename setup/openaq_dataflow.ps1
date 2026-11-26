param(
    [string]$Workspace = "nyc-urban-analytics",
    [string]$Dataflow = "df_openaq",
    [string]$Template = "df_openaq",
    [string]$Reference = "df_ecb_fx",
    [string]$ReferenceQuery = "ecb_usd_eur",
    [string]$ConnectionName = "openaq_api",
    [string]$Url = "https://api.openaq.org/"
)

. (Join-Path $PSScriptRoot "common.ps1")

if (-not $env:OPENAQ_API_KEY) {
    $env:OPENAQ_API_KEY = [Environment]::GetEnvironmentVariable("OPENAQ_API_KEY", "User")
}
if (-not $env:OPENAQ_API_KEY) {
    throw "OPENAQ_API_KEY is not set"
}

$ws = "$Workspace.Workspace"
$connectionId = Get-AnonymousConnection $ConnectionName "Web" $Url

$referenceRoot = Join-Path $Root "build\reference"
if (Test-Path $referenceRoot) {
    Remove-Item $referenceRoot -Recurse -Force
}
New-Item -ItemType Directory $referenceRoot | Out-Null
Invoke-Checked $Fab @("export", "$ws/$Reference.Dataflow", "-o", $referenceRoot, "-f")

$build = Join-Path $Root "build\$Dataflow.Dataflow"
if (Test-Path $build) {
    Remove-Item $build -Recurse -Force
}
$arguments = @(
    (Join-Path $Root "bronze\build_dataflow.py"),
    "--reference", (Join-Path $referenceRoot "$Reference.Dataflow"),
    "--reference-query", $ReferenceQuery,
    "--template", (Join-Path $Root "bronze\$Template.Dataflow"),
    "--name", $Dataflow,
    "--connection-id", $connectionId,
    "--web-path", $Url,
    "--targets", "openaq_sensors,openaq_hours_landing",
    "--out", $build
)
Invoke-Checked $Python $arguments

Invoke-Checked $Fab @("import", "$ws/$Dataflow.Dataflow", "-i", $build, "-f")
Write-Host "Connection $ConnectionName : $connectionId"
Write-Host "Dataflow $Dataflow : $(Get-FabValue "$ws/$Dataflow.Dataflow" "id")"
