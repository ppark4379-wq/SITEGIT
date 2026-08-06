$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "Run ops/scripts/setup_windows.ps1 first." }
if (-not (Test-Path ".env")) { throw "Create .env from ops/config/sitegit.env.example first." }
$env:PYTHONPATH = "$RepoRoot\backend"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
