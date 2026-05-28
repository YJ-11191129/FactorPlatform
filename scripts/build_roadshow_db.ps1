param(
  [string]$ComposeFile = "docker-compose.roadshow.yml",
  [string]$DumpPath = "data\db_dumps\roadshow_demo.dump",
  [string]$Markets = "cn,us,wind,structured",
  [int]$QlibBatchSize = 100,
  [int]$ParquetBatchSize = 100000,
  [int]$InstrumentLimit = 0,
  [int]$StructuredRowLimit = 0
)

$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$PathValue) {
  $dir = Split-Path -Parent $PathValue
  if ($dir -and -not (Test-Path $dir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }
}

function Assert-LastExit([string]$Step) {
  if ($LASTEXITCODE -ne 0) {
    throw "$Step failed with exit code $LASTEXITCODE"
  }
}

Ensure-Dir $DumpPath

Write-Host "[1/4] Starting roadshow PostgreSQL..."
docker compose -f $ComposeFile up -d postgres
Assert-LastExit "docker compose up postgres"

Write-Host "[1.5/4] Building backend image with current scripts..."
docker compose -f $ComposeFile build backend
Assert-LastExit "docker compose build backend"

Write-Host "[2/4] Importing portable data into PostgreSQL..."
$importArgs = @(
  "run", "--rm", "backend",
  "python", "scripts/import_roadshow_data.py",
  "--portable-root", "/app/data/portable",
  "--markets", $Markets,
  "--qlib-batch-size", "$QlibBatchSize",
  "--parquet-batch-size", "$ParquetBatchSize"
)
if ($InstrumentLimit -gt 0) {
  $importArgs += @("--instrument-limit", "$InstrumentLimit")
}
if ($StructuredRowLimit -gt 0) {
  $importArgs += @("--structured-row-limit", "$StructuredRowLimit")
}
docker compose -f $ComposeFile @importArgs
Assert-LastExit "roadshow data import"

Write-Host "[3/4] Writing PostgreSQL custom dump inside the postgres container..."
$dumpDir = "data\db_dumps"
if (-not (Test-Path $dumpDir)) {
  New-Item -ItemType Directory -Force -Path $dumpDir | Out-Null
}
$dumpFile = Split-Path -Leaf $DumpPath
docker compose -f $ComposeFile exec -T postgres sh -lc "mkdir -p /db_dumps && pg_dump -U `$POSTGRES_USER -d `$POSTGRES_DB -Fc -f /db_dumps/$dumpFile"
Assert-LastExit "pg_dump"

Write-Host "[4/4] Verifying dump exists..."
if (-not (Test-Path $DumpPath)) {
  throw "Dump was not created: $DumpPath"
}
$hash = (Get-FileHash -Algorithm SHA256 $DumpPath).Hash.ToLowerInvariant()
Write-Host "Roadshow dump ready: $DumpPath"
Write-Host "SHA256: $hash"
