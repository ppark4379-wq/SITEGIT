$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot "resolve_data_root.ps1")
$DataRoot = Get-SiteGitDataRoot -RepoRoot $RepoRoot
$Db = Join-Path $DataRoot "database\sitegit.db"
if (-not (Test-Path $Db)) { throw "Database not found: $Db" }
$BackupDir = Join-Path $DataRoot "backups"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$Target = Join-Path $BackupDir ("sitegit_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".db")
Copy-Item $Db $Target
Write-Host "Backup created: $Target" -ForegroundColor Green
Write-Host "주의: 이 백업은 데이터와 같은 디스크에 있습니다. SSD 분실·고장에 대비해 다른 디스크로도 복사하세요." -ForegroundColor Yellow
