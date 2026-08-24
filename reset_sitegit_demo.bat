@echo off
setlocal
cd /d "%~dp0"

echo [SiteGit Demo Reset] Close Isaac Sim and the Backend before continuing.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\scripts\reset_sitegit_demo_state.ps1" %*
if errorlevel 1 goto failed
goto end

:failed
echo.
echo [SiteGit Demo Reset] Reset failed. Check the message above.
pause
exit /b 1

:end
echo.
echo [SiteGit Demo Reset] Start start_sitegit_backend.bat, then start_sitegit_isaac.bat.
endlocal

