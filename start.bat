@echo off
title M3U8 Downloader Pro
cd /d "%~dp0"

echo ========================================
echo    M3U8 Downloader Pro
echo ========================================
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Program exited with error code: %errorlevel%
    echo.
    pause
)