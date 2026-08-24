@echo off
setlocal
cd /d "%~dp0"

echo [SiteGit Setup] Checking this PC and installing missing requirements...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\scripts\start_sitegit_portable.ps1" %*
if errorlevel 1 goto failed
goto end

:failed
echo.
echo [SiteGit Setup] Setup is incomplete. Check the diagnostics above.
pause
exit /b 1

:end
echo.
echo [SiteGit Setup] Environment check finished. Backend and Isaac Sim were not started.
pause
endlocal
