param()

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pidPath = Join-Path $root "data\runtime\stack.pids.json"

if (-not (Test-Path $pidPath)) {
    Write-Host "No PID file found: $pidPath"
    exit 0
}

$json = Get-Content $pidPath -Raw | ConvertFrom-Json

if ($json.backend.pid) {
    try {
        Stop-Process -Id ([int]$json.backend.pid) -Force -ErrorAction Stop
        Write-Host "Stopped backend PID=$($json.backend.pid)"
    } catch {
        Write-Host "Backend PID already stopped: $($json.backend.pid)"
    }
}

if ($json.frontend.mode -eq "wsl") {
    if ($json.frontend.wsl_pid) {
        try {
            wsl.exe bash -lc "kill -9 $($json.frontend.wsl_pid) || true"
            Write-Host "Stopped WSL frontend PID=$($json.frontend.wsl_pid)"
        } catch {
        }
    }
    try {
        Stop-Process -Id ([int]$json.frontend.pid) -Force -ErrorAction Stop
        Write-Host "Stopped WSL host PID=$($json.frontend.pid)"
    } catch {
        Write-Host "WSL host PID already stopped: $($json.frontend.pid)"
    }
    try {
        wsl.exe bash -lc "pkill -f 'next dev' || true"
    } catch {
    }
} else {
    if ($json.frontend.pid) {
        try {
            Stop-Process -Id ([int]$json.frontend.pid) -Force -ErrorAction Stop
            Write-Host "Stopped frontend PID=$($json.frontend.pid)"
        } catch {
            Write-Host "Frontend PID already stopped: $($json.frontend.pid)"
        }
    }
}

Remove-Item $pidPath -Force
Write-Host "Stopped stack and removed PID file."
