@echo off
setlocal
cd /d "%~dp0"

echo [SiteGit Judge Demo] Archiving the previous run and starting from the initial terrain...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\scripts\start_sitegit_judge_demo.ps1" %*
if errorlevel 1 goto failed
goto end

:failed
echo.
echo [SiteGit Judge Demo] Startup failed. Check the message above.
pause
exit /b 1

:end
endlocal

