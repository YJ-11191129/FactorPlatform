param(
  [switch]$Lan,
  [switch]$RequireBackend,
  [string]$PublicHost = ""
)

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

function Use-EnvDefault {
  param([string]$Name, [string]$DefaultValue)
  $v = (Get-Item -Path ("env:" + $Name) -ErrorAction SilentlyContinue).Value
  if ([string]::IsNullOrWhiteSpace($v)) { return $DefaultValue }
  return $v
}

function Get-LanIPv4 {
  try {
    $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
      Where-Object {
        $_.IPAddress -notlike "127.*" -and
        $_.IPAddress -notlike "169.254.*" -and
        $_.IPAddress -notlike "172.17.*" -and
        $_.InterfaceOperationalStatus -eq "Up"
      } |
      Sort-Object InterfaceMetric |
      Select-Object -First 1 -ExpandProperty IPAddress
    if (-not [string]::IsNullOrWhiteSpace($ip)) { return $ip }
  } catch {}
  return "127.0.0.1"
}

$databaseUrlVal = Use-EnvDefault -Name "DATABASE_URL" -DefaultValue "postgresql+psycopg://postgres:factorplatform_dev_password@localhost:5432/factor_platform"
$redisUrlVal = Use-EnvDefault -Name "REDIS_URL" -DefaultValue "redis://localhost:6379/0"
$requireDbVal = Use-EnvDefault -Name "FACTOR_PLATFORM_REQUIRE_DB" -DefaultValue "1"
$requireAuthVal = Use-EnvDefault -Name "FACTOR_PLATFORM_REQUIRE_AUTH" -DefaultValue "1"
$apiKeysVal = Use-EnvDefault -Name "FACTOR_PLATFORM_API_KEYS" -DefaultValue "LOCAL_ADMIN_KEY:admin,LOCAL_VIEW_KEY:viewer"
$webApiKey = Use-EnvDefault -Name "NEXT_PUBLIC_API_KEY" -DefaultValue "LOCAL_ADMIN_KEY"
$aiBacktestDataSourceVal = Use-EnvDefault -Name "FACTOR_PLATFORM_AI_BACKTEST_DATA_SOURCE" -DefaultValue "qlib"
$aiBacktestQlibRegionVal = Use-EnvDefault -Name "FACTOR_PLATFORM_AI_BACKTEST_QLIB_REGION" -DefaultValue "cn"
$providerUriVal = Use-EnvDefault -Name "FACTOR_PLATFORM_PROVIDER_URI" -DefaultValue "D:\mcQlib\data\qlib_bin\cn_data"
$usProviderUriVal = Use-EnvDefault -Name "FACTOR_PLATFORM_US_PROVIDER_URI" -DefaultValue "D:\mcQlib\data\qlib_bin\us_data"
$apiHostVal = Use-EnvDefault -Name "FACTOR_PLATFORM_API_HOST" -DefaultValue "127.0.0.1"
$webBindHost = if ($Lan) { "0.0.0.0" } else { "127.0.0.1" }
$lanHost = if (-not [string]::IsNullOrWhiteSpace($PublicHost)) { $PublicHost } else { Get-LanIPv4 }
$webDisplayHost = if ($Lan) { $lanHost } else { "127.0.0.1" }

Set-Item -Path "env:DATABASE_URL" -Value $databaseUrlVal
Set-Item -Path "env:REDIS_URL" -Value $redisUrlVal
Set-Item -Path "env:FACTOR_PLATFORM_REQUIRE_DB" -Value $requireDbVal
Set-Item -Path "env:FACTOR_PLATFORM_REQUIRE_AUTH" -Value $requireAuthVal
Set-Item -Path "env:FACTOR_PLATFORM_API_KEYS" -Value $apiKeysVal
Set-Item -Path "env:NEXT_PUBLIC_API_KEY" -Value $webApiKey
Set-Item -Path "env:FACTOR_PLATFORM_AI_BACKTEST_DATA_SOURCE" -Value $aiBacktestDataSourceVal
Set-Item -Path "env:FACTOR_PLATFORM_AI_BACKTEST_QLIB_REGION" -Value $aiBacktestQlibRegionVal
Set-Item -Path "env:FACTOR_PLATFORM_PROVIDER_URI" -Value $providerUriVal
Set-Item -Path "env:FACTOR_PLATFORM_US_PROVIDER_URI" -Value $usProviderUriVal
Set-Item -Path "env:FACTOR_PLATFORM_API_HOST" -Value $apiHostVal

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
  $depsDeadline = (Get-Date).AddSeconds(60)
  $postgresReady = $false
  $redisReady = $false
  while ((Get-Date) -lt $depsDeadline) {
    docker compose exec -T postgres pg_isready -U postgres -d factor_platform *> $null
    $postgresReady = ($LASTEXITCODE -eq 0)
    docker compose exec -T redis redis-cli ping *> $null
    $redisReady = ($LASTEXITCODE -eq 0)
    if ($postgresReady -and $redisReady) { break }
    Start-Sleep -Seconds 1
  }
  if (-not ($postgresReady -and $redisReady)) {
    Write-Host " - Postgres/Redis did not become ready within 60 seconds."
    exit 1
  }
} else {
  if ($RequireBackend) {
    throw "Docker is not available, but backend is required for this startup mode. Start Docker Desktop and re-run."
  }
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

function Test-PortLanReady {
  param([int]$Port)
  try {
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
      $addr = [string]$listener.LocalAddress
      if ($addr -in @("0.0.0.0", "::", "[::]")) { return $true }
      if ($addr -eq $lanHost) { return $true }
    }
  } catch {}
  return $false
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


Write-Host "[2/5] Starting API (Python, port 8003 preferred)..."
$apiPort = 8003
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
  Write-Host " - Ports 8003, 8004, and 8002 are all in use. Pick a free port and re-run."
  exit 1
}

$apiHealthUrl = "http://127.0.0.1:$apiPort/health"
if (-not (Test-HttpOk -Url $apiHealthUrl)) {
  $apiOut = Join-Path $logDir "api.out.log"
  $apiErr = Join-Path $logDir "api.err.log"
  $apiCmd = @(
    "`$env:DATABASE_URL='$($databaseUrlVal -replace "'", "''")'"
    "`$env:REDIS_URL='$($redisUrlVal -replace "'", "''")'"
    "`$env:FACTOR_PLATFORM_API_PORT='$apiPort'"
    "`$env:FACTOR_PLATFORM_API_HOST='$apiHostVal'"
    "`$env:FACTOR_PLATFORM_REQUIRE_DB='$requireDbVal'"
    "`$env:FACTOR_PLATFORM_REQUIRE_AUTH='$requireAuthVal'"
    "`$env:FACTOR_PLATFORM_API_KEYS='$apiKeysVal'"
    "`$env:FACTOR_PLATFORM_AI_BACKTEST_DATA_SOURCE='$aiBacktestDataSourceVal'"
    "`$env:FACTOR_PLATFORM_AI_BACKTEST_QLIB_REGION='$aiBacktestQlibRegionVal'"
    "`$env:FACTOR_PLATFORM_PROVIDER_URI='$($providerUriVal -replace "'", "''")'"
    "`$env:FACTOR_PLATFORM_US_PROVIDER_URI='$($usProviderUriVal -replace "'", "''")'"
  )

  foreach ($k in @(
    "LLM_PROVIDER",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_TIMEOUT_SECONDS",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
    "LOCAL_LLM_BASE_URL",
    "LOCAL_LLM_MODEL",
    "LOCAL_LLM_API_KEY",
    "LOCAL_LLM_TIMEOUT_SECONDS",
    "LOCAL_LLM_TEMPERATURE",
    "LOCAL_LLM_MAX_TOKENS",
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
  $workerCmd = @(
    "`$env:DATABASE_URL='$($databaseUrlVal -replace "'", "''")'"
    "`$env:REDIS_URL='$($redisUrlVal -replace "'", "''")'"
    "`$env:FACTOR_PLATFORM_REQUIRE_DB='$requireDbVal'"
    "`$env:FACTOR_PLATFORM_REQUIRE_AUTH='$requireAuthVal'"
    "`$env:FACTOR_PLATFORM_API_KEYS='$apiKeysVal'"
    "`$env:FACTOR_PLATFORM_AI_BACKTEST_DATA_SOURCE='$aiBacktestDataSourceVal'"
    "`$env:FACTOR_PLATFORM_AI_BACKTEST_QLIB_REGION='$aiBacktestQlibRegionVal'"
    "`$env:FACTOR_PLATFORM_PROVIDER_URI='$($providerUriVal -replace "'", "''")'"
    "`$env:FACTOR_PLATFORM_US_PROVIDER_URI='$($usProviderUriVal -replace "'", "''")'"
    "python scripts/run_local_worker.py"
  )
  $workerPs = ($workerCmd -join "; ")
  Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", $workerPs) -WorkingDirectory $root -WindowStyle Minimized -RedirectStandardOutput $workerOut -RedirectStandardError $workerErr | Out-Null
} else {
  Write-Host " - Skipping worker (requires Redis)."
}

Write-Host "[4/5] Starting Web (Next dev, port 3000)..."
$webPortCandidates = @(3001, 3002, 3000)
$webPort = $null
foreach ($p in $webPortCandidates) {
  $existingOk = Test-HttpOk -Url "http://127.0.0.1:$p/backend/health"
  if ($existingOk -and ((-not $Lan) -or (Test-PortLanReady -Port $p))) {
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
  if (-not (Test-HttpOk -Url "http://127.0.0.1:$webPort/backend/health")) {
    if (Test-PortOpen -Port $webPort) {
      Write-Host " - Port $webPort is in use, restarting the process..."
      Stop-PortProcess -Port $webPort | Out-Null
    }

    $webOut = Join-Path $logDir "web.out.log"
    $webErr = Join-Path $logDir "web.err.log"
    Set-Item -Path "env:NEXT_TELEMETRY_DISABLED" -Value "1"
    Set-Item -Path "env:NEXT_PUBLIC_API_KEY" -Value $webApiKey
    if ($noBackend) {
      Set-Item -Path "env:FACTOR_PLATFORM_MOCK_BACKEND" -Value "1"
      Set-Item -Path "env:FACTOR_PLATFORM_ALLOW_MOCK_FALLBACK" -Value "1"
    } else {
      Set-Item -Path "env:FACTOR_PLATFORM_MOCK_BACKEND" -Value "0"
      Set-Item -Path "env:FACTOR_PLATFORM_ALLOW_MOCK_FALLBACK" -Value "0"
      Set-Item -Path "env:BACKEND_ORIGIN" -Value "http://127.0.0.1:$apiPort"
    }
    Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev", "--", "--hostname", $webBindHost, "--port", "$webPort") -WorkingDirectory (Join-Path $root "web") -WindowStyle Minimized -RedirectStandardOutput $webOut -RedirectStandardError $webErr | Out-Null
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
    $webOk = Test-HttpOk -Url "http://127.0.0.1:$webPort/backend/health"
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
  if ($Lan) {
    Write-Host "LAN Web: http://$webDisplayHost`:$webPort/signal-center"
    Write-Host "LAN Dashboard: http://$webDisplayHost`:$webPort/dashboard"
    Write-Host "If another computer cannot open it, allow inbound TCP port $webPort in Windows Firewall for Private networks."
  }
}
Write-Host "API: http://127.0.0.1:$apiPort/docs"
