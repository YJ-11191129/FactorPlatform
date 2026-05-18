param(
    [int]$BackendPort = 8002,
    [int]$FrontendPort = 3000,
    [string]$BackendHost = "127.0.0.1",
    [string]$FrontendHost = "127.0.0.1",
    [switch]$UseWslProbe
)

$ErrorActionPreference = "Continue"

function Check-Url {
    param([string]$Name, [string]$Url, [int]$TimeoutSec = 8)
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
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
    param([string]$Url, [int]$TimeoutSec = 8)
    try {
        Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSec
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
$healthJson = Get-Json -Url "$backendBase/health"
$latestSignals = Get-Json -Url "$backendBase/api/v1/signals/live?page=1&page_size=1"
$shadowSignals = Get-Json -Url "$backendBase/api/v1/signals/shadow?page=1&page_size=1"
$performance = Get-Json -Url "$backendBase/api/v1/signals/performance/summary?execution_mode=live"
$shadowPerformance = Get-Json -Url "$backendBase/api/v1/signals/performance/summary?execution_mode=shadow"
$mockMode = if ((Env-Enabled $env:NEXT_PUBLIC_ALLOW_MOCK_FALLBACK) -or (Env-Enabled $env:FACTOR_PLATFORM_ALLOW_MOCK_FALLBACK)) { "DEMO" } else { "PRODUCTION" }

[PSCustomObject]@{
    backend_port = $BackendPort
    frontend_port = $FrontendPort
    backend_status = if ($healthJson) { $healthJson.status } else { "UNAVAILABLE" }
    backend_version = if ($healthJson.version) { $healthJson.version } else { "n/a" }
    signal_snapshot_status = if ($latestSignals) { $latestSignals.status } else { "UNAVAILABLE" }
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
    (Check-Url -Name "backend_health" -Url "$backendBase/health"),
    (Check-Url -Name "backend_signals_live" -Url "$backendBase/api/v1/signals/live?page=1&page_size=1"),
    (Check-Url -Name "backend_signals_shadow" -Url "$backendBase/api/v1/signals/shadow?page=1&page_size=1"),
    (Check-Url -Name "backend_performance_summary_live" -Url "$backendBase/api/v1/signals/performance/summary?execution_mode=live"),
    (Check-Url -Name "backend_performance_summary_shadow" -Url "$backendBase/api/v1/signals/performance/summary?execution_mode=shadow"),
    (Check-Url -Name "frontend_home" -Url "$frontendBase"),
    (Check-Url -Name "frontend_signal_center" -Url "$frontendBase/signal-center"),
    (Check-Url -Name "frontend_proxy_signals" -Url "$frontendBase/backend/api/v1/signals/live?page=1&page_size=1")
)

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
