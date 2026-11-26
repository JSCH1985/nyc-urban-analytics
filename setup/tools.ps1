param(
    [string]$PythonVersion
)

. (Join-Path $PSScriptRoot "common.ps1")

if ($PythonVersion -and (Test-Path $Python)) {
    $current = & $Python -c "import sys; print('%d.%d' % sys.version_info[:2])"
    if ($current -ne $PythonVersion) {
        Remove-Item $Venv -Recurse -Force
    }
}

if (-not (Test-Path $Python)) {
    if ($PythonVersion) {
        Invoke-Checked "py" @("-$PythonVersion", "-m", "venv", $Venv)
    }
    else {
        Invoke-Checked "python" @("-m", "venv", $Venv)
    }
}

Invoke-Checked $Python @("-m", "pip", "install", "--upgrade", "--quiet", "pip", "ms-fabric-cli>=1.5", "sqlalchemy>=2.0", "pyodbc", "azure-identity")
Invoke-Checked $Fab @("--version")
Invoke-Checked $Fab @("auth", "login")
Invoke-Checked $Fab @("ls", ".capacities")
