$ErrorActionPreference = "Stop"

$Root = Split-Path $PSScriptRoot -Parent
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Fab = Join-Path $Venv "Scripts\fab.exe"

function Invoke-Checked {
    param(
        [Parameter(Mandatory)][string]$Exe,
        [string[]]$Arguments
    )
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$(Split-Path $Exe -Leaf) $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Test-FabPath([string]$Path) {
    [bool]((& $Fab exists $Path) -match "true")
}

function Get-FabValue([string]$Path, [string]$Query) {
    $value = (& $Fab get $Path -q $Query) -join ""
    if ($LASTEXITCODE -ne 0) {
        throw "fab get $Path -q $Query failed with exit code $LASTEXITCODE"
    }
    $value.Trim().Trim('"')
}

function Invoke-FabApi([string[]]$Arguments) {
    $raw = (& $Fab api @Arguments) -join "`n"
    if ($LASTEXITCODE -ne 0) {
        throw "fab api $($Arguments -join ' ') failed: $raw"
    }
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return $null
    }
    $response = $raw | ConvertFrom-Json
    if ($response.PSObject.Properties.Name -notcontains "status_code") {
        return $response
    }
    $body = $response.text
    if ($body -is [string] -and ($body.Trim().StartsWith("{") -or $body.Trim().StartsWith("["))) {
        $body = $body | ConvertFrom-Json
    }
    if ([int]$response.status_code -ge 400) {
        throw "fab api $($Arguments -join ' ') returned $($response.status_code): $($body | ConvertTo-Json -Depth 20 -Compress)"
    }
    $body
}

function Write-Utf8([string]$Path, [string]$Text) {
    [IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding $false))
}

function Get-ConnectionType([string]$Type) {
    $types = @()
    $endpoint = "connections/supportedConnectionTypes"
    do {
        $page = Invoke-FabApi @($endpoint)
        $types += $page.value
        $endpoint = if ($page.continuationToken) {
            "connections/supportedConnectionTypes?continuationToken=$([uri]::EscapeDataString($page.continuationToken))"
        }
    } while ($endpoint)

    $match = $types | Where-Object { $_.type -eq $Type } | Select-Object -First 1
    if (-not $match) {
        throw "Connection type $Type is not offered"
    }
    if ($match.supportedCredentialTypes -notcontains "Anonymous") {
        throw "$Type does not accept Anonymous credentials"
    }
    $match
}

function Get-AnonymousConnection([string]$Name, [string]$Type, [string]$Url) {
    $item = ".connections/$Name.Connection"
    if (Test-FabPath $item) {
        return Get-FabValue $item "id"
    }

    $definition = Get-ConnectionType $Type
    $method = $definition.creationMethods | Select-Object -First 1
    $parameter = @($method.parameters | Where-Object { $_.required }) + @($method.parameters) | Select-Object -First 1
    $encryption = @($definition.supportedConnectionEncryptionTypes) + @("NotEncrypted") | Where-Object { $_ } | Select-Object -First 1

    $body = [ordered]@{
        connectivityType  = "ShareableCloud"
        displayName       = $Name
        connectionDetails = [ordered]@{
            type           = $definition.type
            creationMethod = $method.name
            parameters     = @([ordered]@{ dataType = $parameter.dataType; name = $parameter.name; value = $Url })
        }
        privacyLevel      = "Public"
        credentialDetails = [ordered]@{
            singleSignOnType     = "None"
            connectionEncryption = $encryption
            skipTestConnection   = $false
            credentials          = @{ credentialType = "Anonymous" }
        }
    }

    $request = Join-Path $env:TEMP "$Name.json"
    Write-Utf8 $request ($body | ConvertTo-Json -Depth 10)
    (Invoke-FabApi @("connections", "-X", "post", "-i", $request)).id
}

function Invoke-Notebook([string]$Workspace, [string]$Notebook, [string]$Parameters = "", [int]$WaitMinutes = 180) {
    $item = "$Workspace.Workspace/$Notebook.Notebook"
    $workspaceId = Get-FabValue "$Workspace.Workspace" "id"
    $notebookId = Get-FabValue $item "id"
    $jobArguments = @("job", "run", $item)
    if ($Parameters) {
        $jobArguments += @("-P", $Parameters)
    }
    $deadline = (Get-Date).AddMinutes($WaitMinutes)
    while ($true) {
        & $Fab @jobArguments | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        $run = (Invoke-FabApi @("workspaces/$workspaceId/items/$notebookId/jobs/instances")).value | Sort-Object startTimeUtc -Descending | Select-Object -First 1
        $reason = "$($run.failureReason.message)"
        if ($reason -notmatch "TooManyRequestsForCapacity" -or (Get-Date) -gt $deadline) {
            throw "$Notebook failed: $reason"
        }
        Write-Host "$(Get-Date -Format HH:mm:ss) capacity busy, $Notebook retries in 2 minutes"
        Start-Sleep -Seconds 120
    }
}
