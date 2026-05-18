param(
    [int]$BackendPort = 8002,
    [int]$FrontendPort = 3000,
    [bool]$Strict = $true,
    [ValidateSet("auto","windows","wsl","skip")]
    [string]$FrontendMode = "auto"
)

$ErrorActionPreference = "Stop"

function Resolve-BackendPython {
    $candidates = @()
    if ($env:FACTOR_PLATFORM_BACKEND_PYTHON) {
        $candidates += $env:FACTOR_PLATFORM_BACKEND_PYTHON
    }
    $candidates += @(
        "D:\Download\vnpystudio\python.exe",
        "python"
    )
    foreach ($c in $candidates) {
        try {
            if ($c -eq "python") {
                $cmd = Get-Command python -ErrorAction Stop
                return $cmd.Source
            }
            if (Test-Path $c) {
                return $c
            }
        } catch {
            continue
        }
    }
    throw "No backend python interpreter found. Set FACTOR_PLATFORM_BACKEND_PYTHON."
}

function Resolve-NpmCommand {
    $candidates = @()
    if ($env:FACTOR_PLATFORM_NPM_CMD) {
        $candidates += $env:FACTOR_PLATFORM_NPM_CMD
    }
    $candidates += @(
        "C:\Program Files\nodejs\npm.cmd",
        "C:\Program Files (x86)\nodejs\npm.cmd"
    )
    try {
        $cmd = Get-Command npm -ErrorAction Stop
        $candidates += $cmd.Source
    } catch {
    }
    foreach ($c in $candidates | Select-Object -Unique) {
        if ([string]::IsNullOrWhiteSpace($c)) { continue }
        if (Test-Path $c) { return $c }
    }
    return $null
}

function Test-WslAvailable {
    try {
        $out = wsl.exe bash -lc "echo ok" 2>$null
        return ($out -match "ok")
    } catch {
        return $false
    }
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [int]$Retry = 25,
        [int]$SleepSec = 1
    )
    for ($i = 0; $i -lt $Retry; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Seconds $SleepSec
        }
    }
    return $false
}

function Convert-ToWslPath {
    param([string]$WindowsPath)
    $resolved = (Resolve-Path $WindowsPath).Path
    if ($resolved -match '^([A-Za-z]):\\(.*)$') {
        $drive = $matches[1].ToLower()
        $rest = $matches[2] -replace '\\','/'
        return "/mnt/$drive/$rest"
    }
    throw "Cannot convert to WSL path: $WindowsPath"
}

$script:LastWslProbe = ""
function Test-WslHttpOk {
    param(
        [string]$Url,
        [int]$Retry = 25,
        [int]$SleepSec = 1
    )
    for ($i = 0; $i -lt $Retry; $i++) {
        try {
            $out = wsl.exe bash -lc "curl -s -o /dev/null -w '%{http_code}' '$Url'" 2>$null
            $script:LastWslProbe = "$out"
            if ($out -match '^(2|3|4)\d\d$') {
                return $true
            }
        } catch {
        }
        Start-Sleep -Seconds $SleepSec
    }
    return $false
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtime = Join-Path $root "data\runtime"
New-Item -ItemType Directory -Path $runtime -Force | Out-Null

$backendPy = Resolve-BackendPython
$backendOut = Join-Path $runtime "backend.out.log"
$backendErr = Join-Path $runtime "backend.err.log"
$frontendOut = Join-Path $runtime "frontend.out.log"
$frontendErr = Join-Path $runtime "frontend.err.log"
$pidPath = Join-Path $runtime "stack.pids.json"

if (Test-Path $backendOut) { Remove-Item $backendOut -Force }
if (Test-Path $backendErr) { Remove-Item $backendErr -Force }
if (Test-Path $frontendOut) { Remove-Item $frontendOut -Force }
if (Test-Path $frontendErr) { Remove-Item $frontendErr -Force }

Write-Host "[1/3] Starting backend on :$BackendPort ..."
try {
    $backendProc = Start-Process -FilePath $backendPy `
        -ArgumentList "-m","uvicorn","app.api.app:app","--host","0.0.0.0","--port",$BackendPort `
        -WorkingDirectory $root `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr `
        -PassThru
} catch {
    Write-Host "Backend start with redirected logs failed; retrying without redirect."
    $backendProc = Start-Process -FilePath $backendPy `
        -ArgumentList "-m","uvicorn","app.api.app:app","--host","0.0.0.0","--port",$BackendPort `
        -WorkingDirectory $root `
        -PassThru
}

$backendOk = Wait-HttpOk -Url "http://127.0.0.1:$BackendPort/health"
if (-not $backendOk) {
    Write-Host "Backend failed health check. See $backendErr"
    exit 1
}
Write-Host "Backend up. PID=$($backendProc.Id)"

Write-Host "[2/3] Starting frontend on :$FrontendPort ..."
$npmCmd = Resolve-NpmCommand
$frontendProc = $null
$frontendWslPid = $null
$frontendModeUsed = ""

if ($FrontendMode -eq "skip") {
    $frontendModeUsed = "skip"
    Write-Host "Frontend start skipped."
} elseif ($FrontendMode -eq "windows" -or ($FrontendMode -eq "auto" -and $npmCmd)) {
    if (-not $npmCmd) {
        throw "FrontendMode=windows but npm command not found. Set FACTOR_PLATFORM_NPM_CMD."
    }
    $frontendModeUsed = "windows"
    $frontendProc = Start-Process -FilePath $npmCmd `
        -ArgumentList "run","dev","--","--hostname","0.0.0.0","--port",$FrontendPort `
        -WorkingDirectory (Join-Path $root "web") `
        -PassThru
    Write-Host "Frontend started by Windows npm. PID=$($frontendProc.Id)"
} else {
    if (-not (Test-WslAvailable)) {
        if ($Strict) {
            try { Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue } catch {}
            throw "WSL is not available from this shell, and Windows npm is not available. Cannot start frontend."
        }
        Write-Host "WSL unavailable and npm unavailable; frontend not started."
        $frontendModeUsed = "none"
    } else {
        $frontendModeUsed = "wsl"
        $wslRoot = Convert-ToWslPath -WindowsPath $root
        $wslStartScript = "$($wslRoot)/scripts/start_frontend_wsl.sh"
        $wslRuntime = "$($wslRoot)/data/runtime"
        $wslOut = "$($wslRuntime)/frontend.wsl.out.log"
        $wslErr = "$($wslRuntime)/frontend.wsl.err.log"
        $wslCmd = "mkdir -p '$wslRuntime'; nohup bash '$wslStartScript' '$wslRoot' '$FrontendPort' > '$wslOut' 2> '$wslErr' < /dev/null & echo `$!"
        $pidRaw = wsl.exe bash -lc $wslCmd 2>$null
        $pidStr = ($pidRaw | Select-Object -First 1).ToString().Trim()
        if ($pidStr -match '^\d+$') {
            $frontendWslPid = [int]$pidStr
        }
        Write-Host "Frontend started by WSL. Inner PID=$frontendWslPid"
    }
}

$frontendOk = $false
if ($frontendModeUsed -eq "skip") {
    $frontendOk = $true
} elseif ($frontendModeUsed -eq "windows") {
    $frontendOk = Wait-HttpOk -Url "http://127.0.0.1:$FrontendPort"
} elseif ($frontendModeUsed -eq "wsl") {
    $frontendOk = Test-WslHttpOk -Url "http://127.0.0.1:$FrontendPort"
}
if (-not $frontendOk) {
    Write-Host "Frontend did not pass local health check yet. You can inspect:"
    Write-Host "  $frontendOut"
    Write-Host "  $frontendErr"
    if ($frontendModeUsed -eq "wsl") {
        Write-Host "  last WSL probe code: $script:LastWslProbe"
    }
    if ($Strict) {
        try { Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue } catch {}
        if ($frontendProc) {
            try { Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue } catch {}
        }
        Write-Host "Strict mode: startup failed."
        exit 1
    }
}

$pids = [ordered]@{
    started_at = (Get-Date).ToString("s")
    backend = [ordered]@{
        pid = $backendProc.Id
        port = $BackendPort
        python = $backendPy
    }
    frontend = [ordered]@{
        pid = if ($frontendProc) { $frontendProc.Id } else { $null }
        wsl_pid = $frontendWslPid
        port = $FrontendPort
        mode = $frontendModeUsed
    }
}
$pids | ConvertTo-Json -Depth 6 | Set-Content -Path $pidPath -Encoding UTF8

Write-Host "[3/3] Done."
Write-Host "Backend:  http://127.0.0.1:$BackendPort"
Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "PID file: $pidPath"
