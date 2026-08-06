$ErrorActionPreference = "SilentlyContinue"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$EnvFile = Join-Path $RepoRoot ".env"
$server = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -TimeoutSec 2
Write-Host ("SiteGit API       " + $(if($server){"RUNNING"}else{"STOPPED"}))
if (Test-Path $EnvFile) {
  $rootLine = Get-Content $EnvFile | Where-Object { $_ -match '^SITEGIT_DATA_ROOT=' } | Select-Object -First 1
  $dataRoot = ($rootLine -replace '^SITEGIT_DATA_ROOT=', '').Trim()
  Write-Host ("External SSD      " + $(if(Test-Path $dataRoot){"CONNECTED"}else{"NOT FOUND"}) + "  " + $dataRoot)
}
$cloudflared = Get-Process cloudflared -ErrorAction SilentlyContinue
Write-Host ("Cloudflare Tunnel " + $(if($cloudflared){"RUNNING"}else{"STOPPED"}))
