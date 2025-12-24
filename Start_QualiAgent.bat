@echo off
title QualiAgent Launcher

echo =================================================
echo       Starting QualiAgent (Safe Mode V4.0)
echo =================================================

:: 1. Define variables for paths (Robust against spaces)
set "ROOT_DIR=%~dp0"
set "FRONTEND_DIR=%ROOT_DIR%frontend-web"

:: Ensure we are in root
cd /d "%ROOT_DIR%"

:: 2. Launch Backend
echo [1/3] Starting Backend...
start "QualiAgent Backend" cmd /k "python -m backend.main"

:: 3. Launch Frontend (Using /D switch - The Magic Fix)
echo [2/3] Starting Frontend...

if exist "%FRONTEND_DIR%" (
    :: /D switch forces the starting directory.
    :: We run "npm run dev" directly inside that directory.
    start "QualiAgent Frontend" /D "%FRONTEND_DIR%" cmd /k "npm run dev"
) else (
    echo.
    echo [ERROR] Folder 'frontend-web' NOT found!
    echo Looked in: "%FRONTEND_DIR%"
    pause
    exit
)

:: 4. Open Browser
echo [3/3] Opening Browser...
timeout /t 5 /nobreak >nul
start http://localhost:5173

echo.
echo Done.