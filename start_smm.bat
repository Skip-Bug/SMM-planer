@echo off
chcp 65001 >nul
title SMM Planner - Auto Restart

echo.
echo ========================================
echo   SMM Planner - Auto Restart
echo ========================================
echo.

:loop
echo [%date% %time%] Starting SMM Planner...
echo.

REM Check venv
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating venv...
    call venv\Scripts\activate.bat
)

REM Run main script
python core.py

REM Exit code
set EXIT_CODE=%ERRORLEVEL%

echo.
echo ========================================
echo [%date% %time%] Script finished with code %EXIT_CODE%
echo ========================================
echo.

REM If exit code 3221225786 (Ctrl+C) - do NOT restart
if %EXIT_CODE% EQU 3221225786 (
    echo [INFO] Stopped by user. Exiting...
    exit /b 0
)

REM If error - restart after 5 seconds
if %EXIT_CODE% NEQ 0 (
    echo [WARN] Error detected. Restarting in 5 seconds...
    timeout /t 5 /nobreak >nul
    goto loop
)

REM If success - also restart (for production)
echo [INFO] Finished normally. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
