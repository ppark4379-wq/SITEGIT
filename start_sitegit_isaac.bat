@echo off
setlocal
cd /d "%~dp0"

echo [SiteGit Isaac] Starting Isaac Sim with SSD assets...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\scripts\start_sitegit_isaac_portable.ps1" %*
if errorlevel 1 goto failed
goto end

:failed
echo.
echo [SiteGit Isaac] Startup failed. Run start_sitegit_portable.bat and Backend first.
pause
exit /b 1

:end
endlocal
