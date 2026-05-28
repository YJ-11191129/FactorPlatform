param(
  [string]$PublicHost = "",
  [switch]$DemoFallback,
  [switch]$OpenFirewall
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$webRoot = Join-Path $root "web"
$logDir = Join-Path $root "logs"
$runtimeDir = Join-Path $root "data\runtime"
$pidPath = Join-Path $runtimeDir "demo_lan.pids.json"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
Set-Location $root

function Import-DotEnvFile {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return }
  foreach ($line in Get-Content -Path $Path -ErrorAction SilentlyContinue) {
    $text = ($line -as [string])
    if ($null -eq $text) { continue }
    $text = $text.Trim()
    if (-not $text -or $text.StartsWith("#") -or $text.IndexOf("=") -lt 1) { continue }
    $key = $text.Substring(0, $text.IndexOf("=")).Trim()
    $value = $text.Substring($text.IndexOf("=") + 1).Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
      if ($value.Length -ge 2) { $value = $value.Substring(1, $value.Length - 2) }
    }
    if ($key) { Set-Item -Path ("env:" + $key) -Value $value }
  }
}

function Use-EnvDefault {
  param([string]$Name, [string]$DefaultValue)
  $value = (Get-Item -Path ("env:" + $Name) -ErrorAction SilentlyContinue).Value
  if ([string]::IsNullOrWhiteSpace($value)) { return $DefaultValue }
  return $value
}

function Env-Enabled {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
  return @("0", "false", "no", "off") -notcontains $Value.ToLowerInvariant()
}

function Get-LanIPv4 {
  if (-not [string]::IsNullOrWhiteSpace($PublicHost)) { return $PublicHost }
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

function Test-DockerReady {
  try {
    & docker info *> $null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function Get-QlibLatestDate {
  param([string]$ProviderUri)
  try {
    $calendarPath = Join-Path $ProviderUri "calendars\day.txt"
    if (-not (Test-Path $calendarPath)) { return $null }
    $latest = Get-Content -Path $calendarPath -Tail 1 -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace($latest)) { return $null }
    return [datetime]::Parse($latest.Trim()).Date
  } catch {
    return $null
  }
}

function Test-QlibFresh {
  param([string]$ProviderUri, [int]$FreshnessDays = 5)
  $latest = Get-QlibLatestDate -ProviderUri $ProviderUri
  if ($null -eq $latest) {
    return [PSCustomObject]@{ ok = $false; latest = $null; days = $null; message = "calendar latest date is unreadable" }
  }
  $days = ([datetime]::Today - $latest).Days
  return [PSCustomObject]@{
    ok = $days -le $FreshnessDays
    latest = $latest.ToString("yyyy-MM-dd")
    days = $days
    message = "latest=$($latest.ToString("yyyy-MM-dd")), days_since_latest=$days, threshold=$FreshnessDays"
  }
}

function Test-HttpOk {
  param(
    [string]$Url,
    [hashtable]$Headers = @{},
    [int]$TimeoutSec = 5
  )
  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec -Headers $Headers
    return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
  } catch {
    return $false
  }
}

function Get-Json {
  param(
    [string]$Url,
    [hashtable]$Headers = @{},
    [int]$TimeoutSec = 8
  )
  try {
    return Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSec -Headers $Headers
  } catch {
    return $null
  }
}

function Wait-HttpOk {
  param(
    [string]$Url,
    [hashtable]$Headers = @{},
    [int]$TimeoutSec = 180
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    if (Test-HttpOk -Url $Url -Headers $Headers -TimeoutSec 5) { return $true }
    Start-Sleep -Seconds 1
  }
  return $false
}

function Get-PortPid {
  param([int]$Port)
  try {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $conn) { return $null }
    return $conn.OwningProcess
  } catch {
    return $null
  }
}

function Get-ProcessCommandLine {
  param([int]$ProcessIdValue)
  try {
    return (Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessIdValue" -ErrorAction SilentlyContinue).CommandLine
  } catch {
    return ""
  }
}

function Test-FactorPlatformProcess {
  param([int]$ProcessId, [string]$Kind)
  if (Test-Path $pidPath) {
    try {
      $record = Get-Content -Path $pidPath -Raw | ConvertFrom-Json
      if ($Kind -eq "api" -and [int]$record.api_pid -eq $ProcessId) { return $true }
      if ($Kind -eq "web" -and [int]$record.web_pid -eq $ProcessId) { return $true }
    } catch {}
  }
  $cmd = Get-ProcessCommandLine -ProcessIdValue $ProcessId
  if ([string]::IsNullOrWhiteSpace($cmd)) { return $false }
  $normalized = $cmd.ToLowerInvariant()
  if ($Kind -eq "api" -and $normalized.Contains("run_local_api.py")) { return $true }
  if ($Kind -eq "web" -and $normalized.Contains("node_modules/next") -and ($normalized.Contains("--port 3001") -or $normalized.Contains("--port 3002"))) { return $true }
  $inRepo = $normalized.Contains("factorplatform") -or $normalized.Contains("d:\factorplatform")
  if (-not $inRepo) { return $false }
  if ($Kind -eq "api") {
    return ($normalized.Contains("run_local_api.py") -or $normalized.Contains("app.api.app") -or $normalized.Contains("uvicorn"))
  }
  if ($Kind -eq "web") {
    return ($normalized.Contains("next") -or $normalized.Contains("npm") -or $normalized.Contains("start-server.js"))
  }
  return $false
}

function Stop-FactorPlatformPort {
  param([int]$Port, [string]$Kind)
  $owningPid = Get-PortPid -Port $Port
  if ($null -eq $owningPid) { return $true }
  if (-not (Test-FactorPlatformProcess -ProcessId $owningPid -Kind $Kind)) {
    Write-Host " - Port $Port is occupied by a non-FactorPlatform process; skipping it."
    return $false
  }
  try {
    Stop-Process -Id $owningPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 700
    return $true
  } catch {
    Write-Host " - Could not stop FactorPlatform process on port $Port`: $($_.Exception.Message)"
    return $false
  }
}

function Select-Port {
  param([int[]]$Candidates, [string]$Kind)
  foreach ($port in $Candidates) {
    $owningPid = Get-PortPid -Port $port
    if ($null -eq $owningPid) { return $port }
    if (Test-FactorPlatformProcess -ProcessId $owningPid -Kind $Kind) {
      if (Stop-FactorPlatformPort -Port $port -Kind $Kind) { return $port }
    } else {
      Write-Host " - Port $port is already in use by another process."
    }
  }
  return $null
}

function Set-DemoEnvironment {
  param(
    [string]$Mode,
    [int]$ApiPort,
    [string]$ApiKey
  )
  Set-Item -Path "env:NEXT_TELEMETRY_DISABLED" -Value "1"
  Set-Item -Path "env:NEXT_PUBLIC_API_KEY" -Value $ApiKey
  if ($Mode -eq "DEMO_FALLBACK") {
    Set-Item -Path "env:BACKEND_ORIGIN" -Value "http://127.0.0.1:65535"
    Set-Item -Path "env:NEXT_PUBLIC_ALLOW_MOCK_FALLBACK" -Value "1"
    Set-Item -Path "env:FACTOR_PLATFORM_ALLOW_MOCK_FALLBACK" -Value "1"
    Set-Item -Path "env:NEXT_PUBLIC_MOCK_BACKEND" -Value "1"
    Set-Item -Path "env:FACTOR_PLATFORM_MOCK_BACKEND" -Value "1"
    Set-Item -Path "env:NEXT_PUBLIC_DEMO_READONLY" -Value "1"
    Set-Item -Path "env:FACTOR_PLATFORM_DEMO_READONLY" -Value "1"
  } else {
    Set-Item -Path "env:BACKEND_ORIGIN" -Value "http://127.0.0.1:$ApiPort"
    Set-Item -Path "env:NEXT_PUBLIC_ALLOW_MOCK_FALLBACK" -Value "0"
    Set-Item -Path "env:FACTOR_PLATFORM_ALLOW_MOCK_FALLBACK" -Value "0"
    Set-Item -Path "env:NEXT_PUBLIC_MOCK_BACKEND" -Value "0"
    Set-Item -Path "env:FACTOR_PLATFORM_MOCK_BACKEND" -Value "0"
    Set-Item -Path "env:NEXT_PUBLIC_DEMO_READONLY" -Value "0"
    Set-Item -Path "env:FACTOR_PLATFORM_DEMO_READONLY" -Value "0"
  }
}

function Add-FirewallRule {
  param([int]$Port)
  $name = "FactorPlatform Demo Web $Port"
  try {
    $existing = Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $existing) {
      New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private | Out-Null
      Write-Host "Firewall rule added: $name"
    } else {
      Write-Host "Firewall rule already exists: $name"
    }
  } catch {
    Write-Host "Firewall rule was not added: $($_.Exception.Message)"
  }
}

Import-DotEnvFile -Path (Join-Path $root ".env.local")
Import-DotEnvFile -Path (Join-Path $root ".env")

$lanHost = Get-LanIPv4
$databaseUrl = Use-EnvDefault -Name "DATABASE_URL" -DefaultValue "postgresql+psycopg://postgres:factorplatform_dev_password@localhost:5432/factor_platform"
$redisUrl = Use-EnvDefault -Name "REDIS_URL" -DefaultValue "redis://localhost:6379/0"
$apiKeys = Use-EnvDefault -Name "FACTOR_PLATFORM_API_KEYS" -DefaultValue "LOCAL_ADMIN_KEY:admin,LOCAL_VIEW_KEY:viewer"
$webApiKey = Use-EnvDefault -Name "NEXT_PUBLIC_API_KEY" -DefaultValue "LOCAL_ADMIN_KEY"
$cnProvider = Use-EnvDefault -Name "FACTOR_PLATFORM_PROVIDER_URI" -DefaultValue "D:\mcQlib\data\qlib_bin\cn_data"
$usProvider = Use-EnvDefault -Name "FACTOR_PLATFORM_US_PROVIDER_URI" -DefaultValue "D:\mcQlib\data\qlib_bin\us_data"
$apiHeaders = @{ "X-API-Key" = $webApiKey }

$mode = "REAL"
$realFailure = ""
if ($DemoFallback) {
  $mode = "DEMO_FALLBACK"
  $realFailure = "DemoFallback parameter was supplied."
}

Write-Host "[1/7] Preflight"
Write-Host " - Public host: $lanHost"
Write-Host " - DeepSeek key: $(if ([string]::IsNullOrWhiteSpace($env:LLM_API_KEY) -and [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) { '<missing>' } else { '<set>' })"
Write-Host " - API key: $(if ([string]::IsNullOrWhiteSpace($webApiKey)) { '<missing>' } else { '<set>' })"

if ($mode -eq "REAL") {
  if (-not (Test-Path $cnProvider)) { $realFailure = "CN qlib provider is missing: $cnProvider" }
  if (-not $realFailure -and -not (Test-Path $usProvider)) { $realFailure = "US qlib provider is missing: $usProvider" }
  if (-not $realFailure) {
    $cnFresh = Test-QlibFresh -ProviderUri $cnProvider
    $usFresh = Test-QlibFresh -ProviderUri $usProvider
    Write-Host " - qlib CN: $($cnFresh.message)"
    Write-Host " - qlib US: $($usFresh.message)"
    if (-not $cnFresh.ok) { $realFailure = "CN qlib provider is stale or unreadable: $($cnFresh.message)" }
    if (-not $realFailure -and -not $usFresh.ok) { $realFailure = "US qlib provider is stale or unreadable: $($usFresh.message)" }
  }
  if (-not $realFailure -and -not (Test-DockerReady)) { $realFailure = "Docker Desktop is not available." }
  if ($realFailure) {
    Write-Host " - Real mode preflight failed: $realFailure"
    Write-Host " - Falling back to read-only demo mode."
    $mode = "DEMO_FALLBACK"
  }
}

$apiPort = 0

if ($mode -eq "REAL") {
  Write-Host "[2/7] Starting Docker dependencies"
  try {
    docker compose up -d postgres redis | Out-Null
    $depsDeadline = (Get-Date).AddSeconds(75)
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
      throw "Postgres/Redis did not become ready within 75 seconds."
    }
  } catch {
    $realFailure = $_.Exception.Message
    Write-Host " - Real mode dependency startup failed: $realFailure"
    Write-Host " - Falling back to read-only demo mode."
    $mode = "DEMO_FALLBACK"
  }
} else {
  Write-Host "[2/7] Skipping Docker dependencies for demo fallback"
}

if ($mode -eq "REAL") {
  Write-Host "[3/7] Starting local API"
  $apiPort = Select-Port -Candidates @(8003, 8004) -Kind "api"
  if ($null -eq $apiPort) {
    $realFailure = "No free API port from 8003/8004."
    Write-Host " - $realFailure"
    Write-Host " - Falling back to read-only demo mode."
    $mode = "DEMO_FALLBACK"
  } else {
    Set-Item -Path "env:DATABASE_URL" -Value $databaseUrl
    Set-Item -Path "env:REDIS_URL" -Value $redisUrl
    Set-Item -Path "env:FACTOR_PLATFORM_API_PORT" -Value "$apiPort"
    Set-Item -Path "env:FACTOR_PLATFORM_API_HOST" -Value "127.0.0.1"
    Set-Item -Path "env:FACTOR_PLATFORM_REQUIRE_DB" -Value "1"
    Set-Item -Path "env:FACTOR_PLATFORM_REQUIRE_AUTH" -Value "1"
    Set-Item -Path "env:FACTOR_PLATFORM_API_KEYS" -Value $apiKeys
    Set-Item -Path "env:FACTOR_PLATFORM_AI_BACKTEST_DATA_SOURCE" -Value "qlib"
    Set-Item -Path "env:FACTOR_PLATFORM_AI_BACKTEST_QLIB_REGION" -Value "cn"
    Set-Item -Path "env:FACTOR_PLATFORM_PROVIDER_URI" -Value $cnProvider
    Set-Item -Path "env:FACTOR_PLATFORM_US_PROVIDER_URI" -Value $usProvider

    $apiOut = Join-Path $logDir "demo_api.out.log"
    $apiErr = Join-Path $logDir "demo_api.err.log"
    Start-Process -FilePath "python" -ArgumentList @("scripts/run_local_api.py") -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr | Out-Null

    if (-not (Wait-HttpOk -Url "http://127.0.0.1:$apiPort/health" -TimeoutSec 180)) {
      $realFailure = "API health did not become ready on port $apiPort. See $apiErr"
      Write-Host " - $realFailure"
      Write-Host " - Falling back to read-only demo mode."
      $mode = "DEMO_FALLBACK"
    }
  }
} else {
  Write-Host "[3/7] Skipping local API for demo fallback"
}

if ($mode -eq "REAL") {
  Write-Host "[4/7] Checking qlib and AI providers"
  $providers = Get-Json -Url "http://127.0.0.1:$apiPort/api/v1/strategy-ai/providers" -Headers $apiHeaders -TimeoutSec 10
  if ($providers -and $providers.providers) {
    foreach ($provider in $providers.providers) {
      $readyText = if ($provider.ready) { "READY" } else { "NOT_READY" }
      Write-Host " - $($provider.name): $readyText / $($provider.model)"
    }
  } else {
    Write-Host " - Provider status unavailable; continuing because API health is OK."
  }
} else {
  Write-Host "[4/7] Demo fallback provider check skipped"
}

Write-Host "[5/7] Building production frontend"
$webPort = Select-Port -Candidates @(3001, 3002) -Kind "web"
if ($null -eq $webPort) {
  throw "No free frontend port from 3001/3002. Close the conflicting process or pass a clean environment."
}

Set-DemoEnvironment -Mode $mode -ApiPort $apiPort -ApiKey $webApiKey
Push-Location $webRoot
try {
  & npm.cmd run build
  if ($LASTEXITCODE -ne 0) { throw "npm build failed" }
} finally {
  Pop-Location
}

Write-Host "[6/7] Starting production frontend"
$webOut = Join-Path $logDir "demo_web.out.log"
$webErr = Join-Path $logDir "demo_web.err.log"
Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "start", "--", "--hostname", "0.0.0.0", "--port", "$webPort") -WorkingDirectory $webRoot -WindowStyle Hidden -RedirectStandardOutput $webOut -RedirectStandardError $webErr | Out-Null

if (-not (Wait-HttpOk -Url "http://127.0.0.1:$webPort/backend/health" -TimeoutSec 120)) {
  throw "Frontend proxy health did not become ready on port $webPort. See $webErr"
}

if ($OpenFirewall) {
  Write-Host "[7/7] Opening Windows Firewall for frontend"
  Add-FirewallRule -Port $webPort
} else {
  Write-Host "[7/7] Firewall unchanged"
}

$apiPid = if ($mode -eq "REAL") { Get-PortPid -Port $apiPort } else { $null }
$webPid = Get-PortPid -Port $webPort
[PSCustomObject]@{
  started_at = (Get-Date).ToString("s")
  mode = $mode
  api_port = $apiPort
  api_pid = $apiPid
  web_port = $webPort
  web_pid = $webPid
  lan_host = $lanHost
} | ConvertTo-Json -Depth 4 | Set-Content -Path $pidPath -Encoding UTF8

$localWeb = "http://127.0.0.1:$webPort"
$lanWeb = "http://$lanHost`:$webPort"

Write-Host ""
Write-Host "MODE=$mode"
if ($realFailure) { Write-Host "FALLBACK_REASON=$realFailure" }
Write-Host "LOCAL Web: $localWeb/dashboard"
Write-Host "LAN Dashboard: $lanWeb/dashboard"
Write-Host "LAN Signal Center: $lanWeb/signal-center"
Write-Host "LAN AI Strategy Builder: $lanWeb/ai-strategy-builder"
if ($mode -eq "REAL") {
  Write-Host "API local only: http://127.0.0.1:$apiPort"
} else {
  Write-Host "API local only: not started in demo fallback"
}
Write-Host "Share only the LAN frontend URLs during the roadshow."
Write-Host "If another computer cannot open it, re-run with -OpenFirewall or allow inbound TCP $webPort on Private networks."

try { Start-Process "$localWeb/dashboard" | Out-Null } catch {}
