@echo off
setlocal
title Antigravity Discord RPC - Installer

echo =================================================================
echo       Antigravity CLI Discord RPC ^& Activity Logger
echo =================================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] Python was not found in your PATH.
    echo     Please install Python 3.8+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

set "TARGET_DIR=%USERPROFILE%\.gemini\config\plugins\discord-rpc"
if not exist "%USERPROFILE%\.gemini\config\plugins" mkdir "%USERPROFILE%\.gemini\config\plugins"

if /i not "%~dp0"=="%TARGET_DIR%\" (
    echo [*] Copying plugin files to %TARGET_DIR%...
    if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
    xcopy /E /I /Y "%~dp0*" "%TARGET_DIR%\" >nul
)

cd /d "%TARGET_DIR%"

if not exist "settings.json" (
    if exist "settings.example.json" (
        copy /y "settings.example.json" "settings.json" >nul
        echo [+] Created settings.json from template.
    )
)

python scripts\setup_plugin.py

echo.
echo =================================================================
echo   Installation Complete!
echo   - Configure settings: double-click settings.bat
echo   - View live logs:     double-click view_logs.bat
echo =================================================================
echo.
pause
