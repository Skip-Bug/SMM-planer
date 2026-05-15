@echo off
chcp 65001 >nul
title SMM Planner

echo.
echo ========================================
echo   SMM Planner
echo ========================================
echo.
echo Choose mode:
echo   1 - Run once
echo   2 - Run in infinite loop (auto restart)
echo.
set /p MODE="Enter 1 or 2: "

if "%MODE%"=="1" goto run_once
if "%MODE%"=="2" goto run_loop

echo Invalid choice. Exiting.
exit /b 1

:run_once
echo.
echo [INFO] Running script once...
if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat
python core.py
echo [INFO] Script finished.
pause
exit /b 0

:run_loop
echo.
echo [INFO] Running in loop mode (auto restart)...
:loop
echo [%date% %time%] Starting SMM Planner...
if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat
python core.py
set EXIT_CODE=%ERRORLEVEL%
echo.
echo [%date% %time%] Script finished with code %EXIT_CODE%

if %EXIT_CODE% EQU 3221225786 (
    echo [INFO] Stopped by user. Exiting...
    exit /b 0
)

if %EXIT_CODE% NEQ 0 (
    echo [WARN] Error detected. Restarting in 5 seconds...
) else (
    echo [INFO] Finished normally. Restarting in 5 seconds...
)
timeout /t 5 /nobreak >nul
goto loop
