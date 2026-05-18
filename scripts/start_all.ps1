$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

function Import-DotEnvFile {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return }
  $lines = Get-Content -Path $Path -ErrorAction SilentlyContinue
  foreach ($line in $lines) {
    $x = ($line -as [string])
    if ($null -eq $x) { continue }
    $x = $x.Trim()
    if (-not $x) { continue }
    if ($x.StartsWith("#")) { continue }
    $eq = $x.IndexOf("=")
    if ($eq -lt 1) { continue }
    $k = $x.Substring(0, $eq).Trim()
    $v = $x.Substring($eq + 1).Trim()
    if (-not $k) { continue }
    if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'")) -or ($v.StartsWith('`') -and $v.EndsWith('`'))) {
      if ($v.Length -ge 2) { $v = $v.Substring(1, $v.Length - 2) }
    }
    Set-Item -Path ("env:" + $k) -Value $v
  }
}

Import-DotEnvFile -Path (Join-Path $root ".env.local")
Import-DotEnvFile -Path (Join-Path $root ".env")

Write-Host "[1/5] Starting Postgres/Redis (Docker)..."
$dockerOk = $false
try {
  & docker info *> $null
  if ($LASTEXITCODE -eq 0) {
    $dockerOk = $true
  }
} catch {
  $dockerOk = $false
}

if ($dockerOk) {
  docker compose up -d postgres redis | Out-Null
} else {
  Write-Host " - Docker is not available. Starting in no-DB/no-worker mode."
}

$noBackend = -not $dockerOk

try { Add-Type -AssemblyName System.Net.Http } catch {}

$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Test-PortOpen {
  param([int]$Port)
  try {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    return [bool]$c
  } catch {
    return $false
  }
}

function Get-PortPid {
  param([int]$Port)
  try {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $c) { return $null }
    return $c.OwningProcess
  } catch {
    return $null
  }
}

function Stop-PortProcess {
  param([int]$Port)
  $procId = Get-PortPid -Port $Port
  if ($null -eq $procId) { return $false }
  try {
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300
    return $true
  } catch {
    return $false
  }
}

function Test-HttpOk {
  param([string]$Url)
  $client = New-Object System.Net.Http.HttpClient
  $client.Timeout = [TimeSpan]::FromSeconds(2)
  try {
    $resp = $client.GetAsync($Url).Result
    return $resp.IsSuccessStatusCode
  } catch {
    return $false
  } finally {
    $client.Dispose()
  }
}

function Test-HttpStatusOk {
  param([string]$Url)
  $client = New-Object System.Net.Http.HttpClient
  $client.Timeout = [TimeSpan]::FromSeconds(3)
  try {
    $resp = $client.GetAsync($Url).Result
    return [int]$resp.StatusCode
  } catch {
    return -1
  } finally {
    $client.Dispose()
  }
}


Write-Host "[2/5] Starting API (Python, port 8002)..."
$apiPort = 8002
$apiHealthUrl = "http://127.0.0.1:$apiPort/health"

$forceRestartApi = $false
if (-not [string]::IsNullOrWhiteSpace($env:FACTOR_PLATFORM_FORCE_RESTART_API)) {
  $v = $env:FACTOR_PLATFORM_FORCE_RESTART_API.ToString().Trim().ToLower()
  if ($v -in @("1","true","yes","on")) { $forceRestartApi = $true }
}

if ($noBackend) {
  Write-Host " - Skipping API (no DB)."
} else {
$apiPortCandidates = @(8003, 8004, 8002)

if ($forceRestartApi) {
  foreach ($p in $apiPortCandidates) {
    if (Test-PortOpen -Port $p) {
      Stop-PortProcess -Port $p | Out-Null
    }
  }
}

$apiPort = $null
foreach ($p in $apiPortCandidates) {
  if (Test-HttpOk -Url "http://127.0.0.1:$p/health") {
    $apiPort = $p
    break
  }
}

if ($null -eq $apiPort) {
  $apiPort = ($apiPortCandidates | Where-Object { -not (Test-PortOpen -Port $_) } | Select-Object -First 1)
}

if ($null -eq $apiPort) {
  Write-Host " - Ports 8002-8004 are all in use. Pick a free port and re-run."
  exit 1
}

$apiHealthUrl = "http://127.0.0.1:$apiPort/health"
if (-not (Test-HttpOk -Url $apiHealthUrl)) {
  $apiOut = Join-Path $logDir "api.out.log"
  $apiErr = Join-Path $logDir "api.err.log"
  $requireAuthVal = if ([string]::IsNullOrWhiteSpace($env:FACTOR_PLATFORM_REQUIRE_AUTH)) { "1" } else { $env:FACTOR_PLATFORM_REQUIRE_AUTH }
  $apiKeysVal = if ([string]::IsNullOrWhiteSpace($env:FACTOR_PLATFORM_API_KEYS)) { "dev-key-123:admin" } else { $env:FACTOR_PLATFORM_API_KEYS }
  $apiCmd = @(
    "`$env:FACTOR_PLATFORM_API_PORT='$apiPort'"
    "`$env:FACTOR_PLATFORM_REQUIRE_AUTH='$requireAuthVal'"
    "`$env:FACTOR_PLATFORM_API_KEYS='$apiKeysVal'"
  )

  foreach ($k in @(
    "LLM_PROVIDER",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_TIMEOUT_SECONDS",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "FACTOR_PLATFORM_LLM_MODEL"
  )) {
    $v = (Get-Item -Path ("env:" + $k) -ErrorAction SilentlyContinue).Value
    if (-not [string]::IsNullOrWhiteSpace($v)) {
      $apiCmd += "`$env:$k='$($v -replace "'", "''")'"
    }
  }

  $apiCmd += "python scripts/run_local_api.py"
  $apiPs = ($apiCmd -join "; ")
  Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", $apiPs) -WorkingDirectory $root -WindowStyle Minimized -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr | Out-Null
} else {
  Write-Host " - API already running on port $apiPort."
}
}

Write-Host "[3/5] Starting Worker (Python, Celery)..."
if ($dockerOk) {
  $workerOut = Join-Path $logDir "worker.out.log"
  $workerErr = Join-Path $logDir "worker.err.log"
  Start-Process -FilePath "python" -ArgumentList @("scripts/run_local_worker.py") -WorkingDirectory $root -WindowStyle Minimized -RedirectStandardOutput $workerOut -RedirectStandardError $workerErr | Out-Null
} else {
  Write-Host " - Skipping worker (requires Redis)."
}

Write-Host "[4/5] Starting Web (Next dev, port 3000)..."
$webPortCandidates = @(3001, 3002, 3000)
$webPort = $null
foreach ($p in $webPortCandidates) {
  if (Test-HttpOk -Url "http://127.0.0.1:$p/backend/api/v1/signals/live?page_size=1") {
    $webPort = $p
    break
  }
}

if ($null -eq $webPort) {
  $webPort = ($webPortCandidates | Where-Object { -not (Test-PortOpen -Port $_) } | Select-Object -First 1)
}

if ($null -eq $webPort) {
  Write-Host " - Ports 3000-3002 are all in use and none of them proxy backend correctly. Pick a free port and re-run."
} else {
  if (-not (Test-HttpOk -Url "http://127.0.0.1:$webPort/backend/api/v1/signals/live?page_size=1")) {
    if (Test-PortOpen -Port $webPort) {
      Write-Host " - Port $webPort is in use, restarting the process..."
      Stop-PortProcess -Port $webPort | Out-Null
    }

    $rootWsl = "/mnt/d/FactorPlatform"
    $webLog = "$rootWsl/logs/web.wsl.log"
    $backendOrigin = "http://host.docker.internal:$apiPort"
    $envLine = if ($noBackend) { "export FACTOR_PLATFORM_MOCK_BACKEND=1" } else { "export BACKEND_ORIGIN=$backendOrigin" }

    $webApiKey = if (-not [string]::IsNullOrWhiteSpace($env:NEXT_PUBLIC_API_KEY)) { $env:NEXT_PUBLIC_API_KEY } else { "dev-key-123" }
    $wslCmd = "set -e; mkdir -p ~/factorplatform_web; (cd $rootWsl/web && tar --exclude node_modules --exclude .next -cf - .) | (cd ~/factorplatform_web && tar -xf -); cd ~/factorplatform_web; export CHOKIDAR_USEPOLLING=1 WATCHPACK_POLLING=true NEXT_TELEMETRY_DISABLED=1; export NEXT_PUBLIC_API_KEY=$webApiKey; $envLine; test -d node_modules || npm ci; (pwd; npm run dev -- --hostname 0.0.0.0 --port $webPort) > $webLog 2>&1"
    Start-Process -FilePath "wsl.exe" -ArgumentList @("-d", "Ubuntu", "--", "bash", "-lc", $wslCmd) -WindowStyle Minimized | Out-Null
  } else {
    Write-Host " - Web already running on port $webPort."
  }
}

Write-Host "[5/5] Waiting for services..."
$deadline = (Get-Date).AddSeconds(300)
while ((Get-Date) -lt $deadline) {
  $apiOk = $true
  if (-not $noBackend) {
    $apiOk = Test-HttpOk -Url "http://127.0.0.1:$apiPort/health"
  }
  $webOk = $false
  if ($null -ne $webPort) {
    $webOk = Test-HttpOk -Url "http://127.0.0.1:$webPort/backend/api/v1/signals/live?page_size=1"
  }
  if ($apiOk -and $webOk) { break }
  Start-Sleep -Seconds 1
}

Write-Host "Opening browser..."
if ($null -ne $webPort) {
  try { Start-Process "http://127.0.0.1:$webPort/signal-center" | Out-Null } catch {}
}
try { Start-Process "http://127.0.0.1:$apiPort/docs" | Out-Null } catch {}

Write-Host "Done."
if ($null -ne $webPort) {
  Write-Host "Web: http://127.0.0.1:$webPort/signal-center"
}
Write-Host "API: http://127.0.0.1:$apiPort/docs"
