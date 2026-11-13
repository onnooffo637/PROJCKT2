@echo off
chcp 65001 > nul
title Project Aether-Human Core Engine (24/7 Supervisor Mode)

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

:RunLoop
echo ===================================================
echo   Starting Project Aether-Human Core Engine...
echo ===================================================

:: Free port 8000 if occupied by a previous orphaned run
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo [INFO] Releasing port 8000 from previous process PID %%a
    taskkill /F /PID %%a >nul 2>&1
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)

set EXITCODE=%ERRORLEVEL%

if "%EXITCODE%"=="0" goto CleanExit
if "%EXITCODE%"=="-1073741510" goto UserStopped
if "%EXITCODE%"=="3221225786" goto UserStopped

echo.
echo ===================================================
echo [WARNING] The engine stopped with code %EXITCODE%.
echo Auto-restarting in 4 seconds to maintain 24/7 uptime...
echo (Press Ctrl+C to cancel auto-restart)
echo ===================================================
timeout /t 4 /nobreak > nul
goto RunLoop

:UserStopped
echo.
echo [INFO] Stopped by user (Ctrl+C).
pause
goto End

:CleanExit
echo.
echo [INFO] Program stopped cleanly.
pause
goto End

:End
