# run-dev.ps1 - one-command ContextIQ dev environment (Windows).
#
#   .\run-dev.ps1          start backend (:8000) + frontend (:3000)
#   .\run-dev.ps1 -Stop    stop both dev servers
#
# What it guarantees:
#   - Always runs from the project root (anchored to this script's
#     own location, so it works from any current directory).
#   - Ports are DETERMINISTIC: stale dev processes holding 8000/3000
#     are terminated first. That prevents the classic failure chain
#     where Next silently moves to :3001 and every browser request
#     dies on CORS while /docs still "works".
#   - Servers run as detached processes with logs in .dev/, so they
#     survive this console closing.
#   - Waits for real health before declaring success.

param(
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

$BackendPort = 8000
$FrontendPort = 3000

function Free-Port([int]$Port) {
    # Deliberately NOT filtered to -State Listen: a hung process can
    # hold a port in "Bound" state, which answers nothing yet still
    # blocks the next bind with error 10048. Query every TCP state
    # and kill each owner (skipping the System/Idle pseudo-PIDs).
    $conns = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($c in ($conns | Select-Object -Unique OwningProcess)) {
        if ($c.OwningProcess -le 4) { continue }
        try {
            $name = (Get-Process -Id $c.OwningProcess -ErrorAction Stop).ProcessName
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop
            Write-Host "  freed port $Port (was $name, PID $($c.OwningProcess))"
        } catch {}
    }
}

function Wait-ForHttp([string]$Url, [int]$TimeoutSec, [string]$Label) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $null = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            Write-Host "  $Label is up: $Url" -ForegroundColor Green
            return $true
        } catch { Start-Sleep -Seconds 2 }
    }
    Write-Warning "$Label did not respond within ${TimeoutSec}s - check .dev\ logs"
    return $false
}

if ($Stop) {
    Write-Host "Stopping ContextIQ dev servers..."
    Free-Port $BackendPort
    Free-Port $FrontendPort
    Write-Host "Done."
    exit 0
}

Write-Host "ContextIQ dev environment" -ForegroundColor Cyan
Write-Host "=========================="

# --- Preflight checks -------------------------------------------------------
foreach ($tool in @("python", "node", "npm")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Error "'$tool' is not on PATH. Install it, then re-run."
    }
}

try {
    $null = Invoke-RestMethod "http://localhost:11434/api/tags" -TimeoutSec 3
    Write-Host "  Ollama: running" -ForegroundColor Green
} catch {
    Write-Warning "Ollama is not reachable on :11434 - chat answers will fail until it is started."
}

if (-not (Test-Path "$Root\frontend\node_modules")) {
    Write-Host "  frontend/node_modules missing - running npm install..."
    Push-Location "$Root\frontend"
    npm install
    Pop-Location
}

# --- Clean ports, then launch ------------------------------------------------
Write-Host "Cleaning ports..."
Free-Port $BackendPort
Free-Port $FrontendPort

New-Item -ItemType Directory -Force -Path "$Root\.dev" | Out-Null

Write-Host "Starting backend on :$BackendPort ..."
Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "api.main:app", "--port", "$BackendPort" `
    -WorkingDirectory $Root -WindowStyle Hidden `
    -RedirectStandardOutput "$Root\.dev\backend.out.log" `
    -RedirectStandardError "$Root\.dev\backend.err.log"

# Backend warm-up loads the embedding model - allow generous time.
$backendOk = Wait-ForHttp "http://localhost:$BackendPort/health" 120 "Backend"

Write-Host "Starting frontend on :$FrontendPort ..."
Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run", "dev", "--", "-p", "$FrontendPort" `
    -WorkingDirectory "$Root\frontend" -WindowStyle Hidden `
    -RedirectStandardOutput "$Root\.dev\frontend.out.log" `
    -RedirectStandardError "$Root\.dev\frontend.err.log"

$frontendOk = Wait-ForHttp "http://localhost:$FrontendPort" 90 "Frontend"

Write-Host ""
if ($backendOk -and $frontendOk) {
    Write-Host "ContextIQ is running" -ForegroundColor Green
    Write-Host "  App:      http://localhost:$FrontendPort"
    Write-Host "  API:      http://localhost:$BackendPort"
    Write-Host "  API docs: http://localhost:$BackendPort/docs"
    Write-Host "  Logs:     $Root\.dev\"
    Write-Host "  Stop:     .\run-dev.ps1 -Stop"
} else {
    Write-Error "Startup incomplete - see logs in $Root\.dev\"
}
