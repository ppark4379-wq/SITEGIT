$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$EnvFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $EnvFile)) { throw ".env not found" }
$rootLine = Get-Content $EnvFile | Where-Object { $_ -match '^SITEGIT_DATA_ROOT=' } | Select-Object -First 1
$DataRoot = ($rootLine -replace '^SITEGIT_DATA_ROOT=', '').Trim()
$Db = Join-Path $DataRoot "database\sitegit.db"
if (-not (Test-Path $Db)) { throw "Database not found: $Db" }
$BackupDir = Join-Path $DataRoot "backups"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$Target = Join-Path $BackupDir ("sitegit_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".db")
Copy-Item $Db $Target
Write-Host "Backup created: $Target" -ForegroundColor Green
