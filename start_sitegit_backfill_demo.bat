@echo off
setlocal
cd /d "%~dp0"

echo [SiteGit Demo] Starting three excavators returning spoil to the installed pipeline trench...
echo [SiteGit Demo] Backend and web services are not used.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\scripts\start_sitegit_backfill_demo.ps1" %*
if errorlevel 1 goto failed
goto end

:failed
echo.
echo [SiteGit Demo] Startup failed. Run excavation and pipe demos first.
pause
exit /b 1

:end
endlocal
