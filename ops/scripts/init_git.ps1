$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot
git init
git add .
git status
Write-Host "Review the staged files, then commit and connect a private remote." -ForegroundColor Yellow
