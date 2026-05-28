param(
  [string]$SourceMcQlibRoot = "D:\mcQlib\data",
  [string]$SourceKaggleRoot = "D:\Kaggle\data",
  [string]$TargetRoot = "",
  [switch]$CreateArchive
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($TargetRoot)) {
  $TargetRoot = Join-Path $repoRoot "data\portable"
}

function Require-Path {
  param([string]$Path, [string]$Label)
  if (-not (Test-Path -LiteralPath $Path)) {
    throw "$Label not found: $Path"
  }
}

function Ensure-Dir {
  param([string]$Path)
  New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Copy-Tree {
  param([string]$Source, [string]$Destination)
  Require-Path -Path $Source -Label "Source directory"
  Ensure-Dir -Path $Destination
  & robocopy $Source $Destination /E /R:2 /W:1 /NFL /NDL /NP /NJH /NJS | Out-Host
  if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed from $Source to $Destination with exit code $LASTEXITCODE"
  }
}

function Copy-OneFile {
  param([string]$Source, [string]$Destination)
  Require-Path -Path $Source -Label "Source file"
  Ensure-Dir -Path (Split-Path -Parent $Destination)
  Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Measure-PortablePath {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    return [ordered]@{ path = $Path; files = 0; bytes = 0 }
  }
  $m = Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum
  return [ordered]@{
    path = $Path
    files = [int]$m.Count
    bytes = [int64]($m.Sum)
  }
}

$mcqlibTarget = Join-Path $TargetRoot "mcqlib"
$kaggleTarget = Join-Path $TargetRoot "kaggle"

Write-Host "[1/5] Preparing portable data directory: $TargetRoot"
Ensure-Dir -Path $TargetRoot

Write-Host "[2/5] Copying qlib CN/US providers..."
Copy-Tree -Source (Join-Path $SourceMcQlibRoot "qlib_bin\cn_data") -Destination (Join-Path $mcqlibTarget "qlib_bin\cn_data")
Copy-Tree -Source (Join-Path $SourceMcQlibRoot "qlib_bin\us_data") -Destination (Join-Path $mcqlibTarget "qlib_bin\us_data")

Write-Host "[3/5] Copying Wind/Kaggle research data..."
Copy-Tree -Source (Join-Path $SourceKaggleRoot "wind_data\01_master") -Destination (Join-Path $kaggleTarget "wind_data\01_master")
Copy-Tree -Source (Join-Path $SourceKaggleRoot "wind_data\03_market_state") -Destination (Join-Path $kaggleTarget "wind_data\03_market_state")
Copy-Tree -Source (Join-Path $SourceKaggleRoot "wind_data\05_shock_intraday") -Destination (Join-Path $kaggleTarget "wind_data\05_shock_intraday")
Copy-OneFile -Source (Join-Path $SourceKaggleRoot "wind_data\02_daily_stock\stock_daily_ohlcv.parquet") -Destination (Join-Path $kaggleTarget "wind_data\02_daily_stock\stock_daily_ohlcv.parquet")
Copy-OneFile -Source (Join-Path $SourceKaggleRoot "wind_data\02_daily_stock\stock_daily_basic.parquet") -Destination (Join-Path $kaggleTarget "wind_data\02_daily_stock\stock_daily_basic.parquet")
Copy-Tree -Source (Join-Path $SourceKaggleRoot "processed") -Destination (Join-Path $kaggleTarget "processed")

Write-Host "[4/5] Writing manifest..."
$manifest = [ordered]@{
  generated_at = (Get-Date).ToString("s")
  repo_root = $repoRoot
  target_root = (Resolve-Path $TargetRoot).Path
  source_mcqlib_root = $SourceMcQlibRoot
  source_kaggle_root = $SourceKaggleRoot
  docker_mounts = [ordered]@{
    FACTOR_PLATFORM_HOST_MCQLIB_DATA = "./data/portable/mcqlib"
    FACTOR_PLATFORM_HOST_KAGGLE_DATA = "./data/portable/kaggle"
  }
  contents = @(
    (Measure-PortablePath (Join-Path $mcqlibTarget "qlib_bin\cn_data"))
    (Measure-PortablePath (Join-Path $mcqlibTarget "qlib_bin\us_data"))
    (Measure-PortablePath (Join-Path $kaggleTarget "wind_data"))
    (Measure-PortablePath (Join-Path $kaggleTarget "processed"))
  )
}
$manifestPath = Join-Path $TargetRoot "manifest.json"
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $manifestPath -Encoding UTF8

if ($CreateArchive) {
  Write-Host "[5/5] Creating archive..."
  $archivePath = Join-Path (Split-Path -Parent $TargetRoot) ("factorplatform-portable-data-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".zip")
  if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
  }
  Compress-Archive -Path (Join-Path $TargetRoot "*") -DestinationPath $archivePath -Force
  Write-Host "Archive: $archivePath"
} else {
  Write-Host "[5/5] Archive skipped. Use -CreateArchive if you want a zip for transfer."
}

Write-Host "Portable data ready: $TargetRoot"
Write-Host "Manifest: $manifestPath"
