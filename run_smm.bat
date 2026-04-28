@echo off
chcp 65001 >nul
title SMM Planner

echo.
echo ========================================
echo   SMM Planner - Running
echo ========================================
echo.

REM Check venv
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating venv...
    call venv\Scripts\activate.bat
)

REM Run main script
python core.py

echo.
echo ========================================
echo   Done. Press any key...
echo ========================================
pause >nul
