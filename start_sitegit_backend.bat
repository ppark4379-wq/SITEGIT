@echo off
setlocal
cd /d "%~dp0"

echo [SiteGit Backend] Starting Backend, local Ollama, and the web page...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\scripts\start_sitegit_backend_portable.ps1" %*
if errorlevel 1 goto failed
goto end

:failed
echo.
echo [SiteGit Backend] Startup failed. Run start_sitegit_portable.bat first.
pause
exit /b 1

:end
endlocal
