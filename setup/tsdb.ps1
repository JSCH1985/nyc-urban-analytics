. (Join-Path $PSScriptRoot "common.ps1")

$alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
$random = [Security.Cryptography.RandomNumberGenerator]::Create()
foreach ($name in "TSDB_PASSWORD", "TSDB_READER_PASSWORD", "GRAFANA_ADMIN_PASSWORD") {
    $value = [Environment]::GetEnvironmentVariable($name, "User")
    if (-not $value) {
        $bytes = New-Object byte[] 24
        $random.GetBytes($bytes)
        $value = -join ($bytes | ForEach-Object { $alphabet[$_ % $alphabet.Length] })
        [Environment]::SetEnvironmentVariable($name, $value, "User")
    }
    Set-Item "env:$name" $value
}

$excluded = @(netsh interface ipv4 show excludedportrange protocol=tcp | ForEach-Object { if ($_ -match "^\s*(\d+)\s+(\d+)") { , @([int]$Matches[1], [int]$Matches[2]) } })
foreach ($setting in @(@("TSDB_PORT", 5432, 15432, 25432, 35432), @("GRAFANA_PORT", 3000, 13000, 23000, 33000))) {
    $name = $setting[0]
    $port = [Environment]::GetEnvironmentVariable($name, "User")
    if (-not $port) {
        $port = $setting[1..4] | Where-Object {
            $candidate = $_
            -not ($excluded | Where-Object { $candidate -ge $_[0] -and $candidate -le $_[1] }) -and -not (Get-NetTCPConnection -LocalPort $candidate -State Listen -ErrorAction SilentlyContinue)
        } | Select-Object -First 1
        if (-not $port) {
            throw "No free port for $name among $($setting[1..4] -join ', ')"
        }
        [Environment]::SetEnvironmentVariable($name, "$port", "User")
    }
    Set-Item "env:$name" "$port"
}

Invoke-Checked $Python @("-m", "pip", "install", "--quiet", "-r", (Join-Path $Root "integrations\requirements.txt"))
Invoke-Checked "docker" @("compose", "-f", (Join-Path $Root "integrations\docker-compose.yml"), "up", "-d", "--wait")

Push-Location $Root
try {
    Invoke-Checked $Python @("-m", "integrations.tsdb")
}
finally {
    Pop-Location
}
Write-Host "http://localhost:$($env:GRAFANA_PORT)"
