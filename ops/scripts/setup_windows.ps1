$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

if (-not (Test-Path ".env")) {
  Copy-Item "ops\config\sitegit.env.example" ".env"
  Write-Host "[SiteGit] .env created. Edit URL, SSD path, passwords and JWT secret." -ForegroundColor Yellow
}
if (-not (Test-Path ".venv")) { python -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
Write-Host "[SiteGit] Setup complete." -ForegroundColor Green
Write-Host "Run: .\ops\scripts\start_sitegit.ps1"
