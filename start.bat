@echo off
title M3U8 Downloader Pro
cd /d "%~dp0"

echo ========================================
echo    M3U8 Downloader Pro
echo ========================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo Using virtualenv Python
    .venv\Scripts\python.exe main.py
) else (
    python main.py
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Program exited with error code: %errorlevel%
    echo.
    pause
)