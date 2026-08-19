@echo off
setlocal
cd /d "%~dp0"

echo [SiteGit] Preparing local server...

if not exist ".venv\Scripts\python.exe" goto setup
if not exist ".env" goto setup
goto start

:setup
echo [SiteGit] First run detected. Creating .env and installing dependencies...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\scripts\setup_windows.ps1"
if errorlevel 1 goto failed

:start
echo [SiteGit] Starting server: http://127.0.0.1:8000
echo [SiteGit] Stop the server with Ctrl+C.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\scripts\start_sitegit.ps1"
if errorlevel 1 goto failed
goto end

:failed
echo.
echo [SiteGit] Startup failed. Check the message above.
pause
exit /b 1

:end
endlocal
