. (Join-Path $PSScriptRoot "common.ps1")

Push-Location $Root
try {
    Invoke-Checked $Python @("-m", "docs.build_lineage")
    Invoke-Checked $Python @("-m", "docs.build_dictionary")
}
finally {
    Pop-Location
}
