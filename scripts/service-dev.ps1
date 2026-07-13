[CmdletBinding()]
param(
    [ValidateSet("up", "status", "down")]
    [string]$Action = "up"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $Root ".env.service-dev"
$Python = if (Test-Path (Join-Path $Root ".venv\Scripts\python.exe")) {
    Join-Path $Root ".venv\Scripts\python.exe"
} else {
    "python"
}

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required for service-dev."
    }
}

function Invoke-Compose([string[]]$Arguments) {
    & docker compose --env-file $EnvFile @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed." }
}

Set-Location $Root
Require-Command docker
Require-Command npx
Require-Command $Python

switch ($Action) {
    "up" {
        & npx --yes supabase start --exclude logflare,vector 1>$null
        if ($LASTEXITCODE -ne 0) { throw "Supabase failed to start." }
        & $Python (Join-Path $Root "scripts\write_service_dev_env.py")
        if ($LASTEXITCODE -ne 0) { throw "Could not write .env.service-dev." }
        Invoke-Compose @("up", "--build", "--detach", "--wait")
        Write-Host "service-dev is ready: http://localhost:3000 (API: http://localhost:8000)"
    }
    "status" {
        if (-not (Test-Path $EnvFile)) {
            throw "service-dev has not been initialized. Run .\run-service-dev.bat first."
        }
        Invoke-Compose @("ps")
    }
    "down" {
        if (Test-Path $EnvFile) { Invoke-Compose @("down") }
        & npx --yes supabase stop 1>$null
        if ($LASTEXITCODE -ne 0) { throw "Supabase failed to stop." }
        Write-Host "service-dev is stopped."
    }
}
