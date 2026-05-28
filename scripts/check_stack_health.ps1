param(
    [int]$BackendPort = 8002,
    [int]$FrontendPort = 3000,
    [string]$BackendHost = "127.0.0.1",
    [string]$FrontendHost = "127.0.0.1",
    [string]$LanHost = "",
    [ValidateSet("auto","real","demo")]
    [string]$Mode = "auto",
    [switch]$UseWslProbe
)

$ErrorActionPreference = "Continue"

function Check-Url {
    param([string]$Name, [string]$Url, [int]$TimeoutSec = 8, [hashtable]$Headers = @{})
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec -Headers $Headers
        [PSCustomObject]@{
            name = $Name
            url = $Url
            ok = $true
            status = [int]$r.StatusCode
            note = ""
        }
    } catch {
        [PSCustomObject]@{
            name = $Name
            url = $Url
            ok = $false
            status = 0
            note = $_.Exception.Message
        }
    }
}

function Get-Json {
    param([string]$Url, [int]$TimeoutSec = 8, [hashtable]$Headers = @{})
    try {
        Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSec -Headers $Headers
    } catch {
        $null
    }
}

function Env-Enabled {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    return @("0", "false", "no", "off") -notcontains $Value.ToLowerInvariant()
}

$backendBase = "http://$BackendHost`:$BackendPort"
$frontendBase = "http://$FrontendHost`:$FrontendPort"
$lanBase = if ([string]::IsNullOrWhiteSpace($LanHost)) { $null } else { "http://$LanHost`:$FrontendPort" }
$apiKey = if (-not [string]::IsNullOrWhiteSpace($env:NEXT_PUBLIC_API_KEY)) { $env:NEXT_PUBLIC_API_KEY } else { "LOCAL_ADMIN_KEY" }
$apiHeaders = @{ "X-API-Key" = $apiKey }
$healthJson = Get-Json -Url "$backendBase/health"
$latestSignals = Get-Json -Url "$backendBase/api/v1/signals/live?page=1&page_size=1" -Headers $apiHeaders
$shadowSignals = Get-Json -Url "$backendBase/api/v1/signals/shadow?page=1&page_size=1" -Headers $apiHeaders
$performance = Get-Json -Url "$backendBase/api/v1/signals/performance/summary?execution_mode=live" -Headers $apiHeaders
$shadowPerformance = Get-Json -Url "$backendBase/api/v1/signals/performance/summary?execution_mode=shadow" -Headers $apiHeaders
$providers = Get-Json -Url "$frontendBase/backend/api/v1/strategy-ai/providers"
$dataPaths = Get-Json -Url "$backendBase/api/data-maintenance/paths" -Headers $apiHeaders -TimeoutSec 90
if (-not $dataPaths) {
    $dataPaths = Get-Json -Url "$frontendBase/backend/api/data-maintenance/paths" -TimeoutSec 90
}
$dataMaintenance = if ($dataPaths) { $dataPaths } else { Get-Json -Url "$frontendBase/backend/api/data-maintenance/latest" -TimeoutSec 12 }
$proxyHealth = Get-Json -Url "$frontendBase/backend/health"
$proxySignals = Get-Json -Url "$frontendBase/backend/api/v1/signals/live?page=1&page_size=1"
$mockMode = if ((Env-Enabled $env:NEXT_PUBLIC_ALLOW_MOCK_FALLBACK) -or (Env-Enabled $env:FACTOR_PLATFORM_ALLOW_MOCK_FALLBACK)) { "DEMO_FALLBACK" } else { "REAL" }
if ($Mode -eq "demo") { $mockMode = "DEMO_FALLBACK" }
if ($Mode -eq "real") { $mockMode = "REAL" }
$requireBackend = $mockMode -eq "REAL"
if (-not $latestSignals -and $proxySignals) { $latestSignals = $proxySignals }

$sources = @()
if ($dataMaintenance -and $dataMaintenance.audit -and $dataMaintenance.audit.sources) {
    $sources = @($dataMaintenance.audit.sources)
} elseif ($dataMaintenance -and $dataMaintenance.sources) {
    $sources = @($dataMaintenance.sources)
}
$cnSource = $sources | Where-Object { $_.source_id -eq "qlib_cn_daily" } | Select-Object -First 1
$usSource = $sources | Where-Object { $_.source_id -eq "qlib_us_daily" } | Select-Object -First 1
$providerItems = if ($providers -and $providers.providers) { @($providers.providers) } else { @() }
$providerReadyCount = @($providerItems | Where-Object { $_.ready }).Count

[PSCustomObject]@{
    backend_port = $BackendPort
    frontend_port = $FrontendPort
    local_frontend = "$frontendBase/dashboard"
    lan_frontend = if ($lanBase) { "$lanBase/dashboard" } else { $null }
    proxy_health = if ($proxyHealth) { $proxyHealth.status } else { "UNAVAILABLE" }
    backend_status = if ($healthJson) { $healthJson.status } else { "UNAVAILABLE" }
    backend_version = if ($healthJson.version) { $healthJson.version } else { "n/a" }
    qlib_cn_status = if ($cnSource) { $cnSource.status } else { "UNAVAILABLE" }
    qlib_cn_latest = if ($cnSource) { $cnSource.end_date } else { $null }
    qlib_us_status = if ($usSource) { $usSource.status } else { "UNAVAILABLE" }
    qlib_us_latest = if ($usSource) { $usSource.end_date } else { $null }
    ai_default_provider = if ($providers) { $providers.default_provider } else { "UNAVAILABLE" }
    ai_provider_ready = $providerReadyCount
    signal_snapshot_status = if ($latestSignals -and $latestSignals.status) { $latestSignals.status } elseif ($mockMode -eq "DEMO_FALLBACK" -and $latestSignals) { "DEMO" } else { "UNAVAILABLE" }
    signal_snapshot_generated_at = if ($latestSignals) { $latestSignals.generated_at } else { $null }
    signal_date = if ($latestSignals) { $latestSignals.signal_date } else { $null }
    signal_source_run_id = if ($latestSignals) { $latestSignals.source_run_id } else { $null }
    router_block_reason = if ($latestSignals -and $latestSignals.router_decision) { $latestSignals.router_decision.block_reason } else { $null }
    regime_freshness_lag_days = if ($latestSignals -and $latestSignals.regime_freshness) { $latestSignals.regime_freshness.freshness_lag_days } else { $null }
    shadow_count = if ($latestSignals -and $latestSignals.counts) { $latestSignals.counts.shadow_count } elseif ($shadowSignals) { $shadowSignals.total } else { $null }
    performance_data_source = if ($performance) { $performance.data_source } else { "UNAVAILABLE" }
    performance_execution_mode = if ($performance) { $performance.execution_mode } else { "UNAVAILABLE" }
    performance_computed_at = if ($performance) { $performance.computed_at } else { $null }
    shadow_performance_data_source = if ($shadowPerformance) { $shadowPerformance.data_source } else { "UNAVAILABLE" }
    shadow_performance_execution_mode = if ($shadowPerformance) { $shadowPerformance.execution_mode } else { "UNAVAILABLE" }
    mock_mode = $mockMode
} | Format-List

$checks = @(
    (Check-Url -Name "frontend_home" -Url "$frontendBase"),
    (Check-Url -Name "frontend_signal_center" -Url "$frontendBase/signal-center"),
    (Check-Url -Name "frontend_proxy_health" -Url "$frontendBase/backend/health"),
    (Check-Url -Name "frontend_proxy_signals" -Url "$frontendBase/backend/api/v1/signals/live?page=1&page_size=1"),
    (Check-Url -Name "frontend_proxy_ai_providers" -Url "$frontendBase/backend/api/v1/strategy-ai/providers")
)

if ($requireBackend) {
    $checks += (Check-Url -Name "backend_health" -Url "$backendBase/health")
    $checks += (Check-Url -Name "backend_signals_live" -Url "$backendBase/api/v1/signals/live?page=1&page_size=1" -Headers $apiHeaders)
    $checks += (Check-Url -Name "backend_signals_shadow" -Url "$backendBase/api/v1/signals/shadow?page=1&page_size=1" -Headers $apiHeaders)
    $checks += (Check-Url -Name "backend_performance_summary_live" -Url "$backendBase/api/v1/signals/performance/summary?execution_mode=live" -Headers $apiHeaders)
    $checks += (Check-Url -Name "backend_performance_summary_shadow" -Url "$backendBase/api/v1/signals/performance/summary?execution_mode=shadow" -Headers $apiHeaders)
}

if ($lanBase) {
    $checks += (Check-Url -Name "lan_frontend_dashboard" -Url "$lanBase/dashboard")
    $checks += (Check-Url -Name "lan_frontend_proxy_health" -Url "$lanBase/backend/health")
}

if ($UseWslProbe) {
    try {
        $wslFront = wsl.exe bash -lc "curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:$FrontendPort'" 2>$null
        $wslText = (($wslFront | Select-Object -First 1) -as [string]).Trim()
        $checks += [PSCustomObject]@{
            name = "wsl_frontend_home"
            url = "http://127.0.0.1:$FrontendPort (WSL)"
            ok = [bool]($wslText -match '^(2|3|4)\d\d$')
            status = if ($wslText -match '^\d{3}$') { [int]$wslText } else { 0 }
            note = ""
        }
    } catch {
        $checks += [PSCustomObject]@{
            name = "wsl_frontend_home"
            url = "http://127.0.0.1:$FrontendPort (WSL)"
            ok = $false
            status = 0
            note = $_.Exception.Message
        }
    }
}

$checks | Format-Table -AutoSize

$allOk = ($checks | Where-Object { -not $_.ok }).Count -eq 0
if ($allOk) {
    Write-Host "STACK_HEALTH=PASS"
    exit 0
}

Write-Host "STACK_HEALTH=FAIL"
exit 1
