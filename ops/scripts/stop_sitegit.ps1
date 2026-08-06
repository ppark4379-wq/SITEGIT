$connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $connections) { Write-Host "SiteGit server is not listening on port 8000."; exit 0 }
$connections | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Write-Host "SiteGit server stopped." -ForegroundColor Green
