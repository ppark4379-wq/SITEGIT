$ErrorActionPreference = "SilentlyContinue"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot "resolve_data_root.ps1")
$server = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -TimeoutSec 2
Write-Host ("SiteGit API       " + $(if($server){"RUNNING"}else{"STOPPED"}))
try {
  $dataRoot = Get-SiteGitDataRoot -RepoRoot $RepoRoot
  Write-Host ("Data root         " + $(if(Test-Path $dataRoot){"CONNECTED"}else{"NOT FOUND"}) + "  " + $dataRoot)
} catch {
  Write-Host ("Data root         UNKNOWN  " + $_.Exception.Message)
}
$cloudflared = Get-Process cloudflared -ErrorAction SilentlyContinue
Write-Host ("Cloudflare Tunnel " + $(if($cloudflared){"RUNNING"}else{"STOPPED"}))
