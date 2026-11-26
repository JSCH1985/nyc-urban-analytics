param(
    [string]$Workspace = "nyc-urban-analytics",
    [switch]$Full
)

. (Join-Path $PSScriptRoot "common.ps1")

$ws = "$Workspace.Workspace"

foreach ($folder in "$ws/lh_silver.Lakehouse/Files/code", "$ws/lh_silver.Lakehouse/Files/code/gold") {
    if (-not (Test-FabPath $folder)) {
        Invoke-Checked $Fab @("mkdir", $folder)
    }
}
foreach ($file in Get-ChildItem (Join-Path $Root "gold") -Filter "*.py") {
    Invoke-Checked $Fab @("cp", $file.FullName, "$ws/lh_silver.Lakehouse/Files/code/gold/$($file.Name)", "-f")
}
& (Join-Path $PSScriptRoot "deploy_notebook.ps1") -Notebook nb_gold_load -Folder gold -Lakehouse lh_silver -Workspace $Workspace

try {
    Invoke-Notebook $Workspace "nb_gold_load" "full:string=$($Full.IsPresent.ToString().ToLower())"
}
catch {
    $remote = "$ws/lh_silver.Lakehouse/Files/reports/gold_load_error.txt"
    $errorFile = Join-Path $Root "build\gold_load_error.txt"
    if (Test-FabPath $remote) {
        if (Test-Path $errorFile) {
            Remove-Item $errorFile -Force
        }
        Invoke-Checked $Fab @("cp", $remote, $errorFile)
        Get-Content $errorFile
    }
    throw
}
& (Join-Path $PSScriptRoot "show_audit.ps1") -Name gold_load -Lakehouse lh_silver -Workspace $Workspace
