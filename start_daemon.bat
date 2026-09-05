@echo off
setlocal
cd /d "%~dp0"
echo [*] Starting Antigravity Discord RPC Daemon in background...
where pythonw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pythonw scripts\discord_daemon.py
) else (
    start "" python scripts\discord_daemon.py
)
timeout /t 2 /nobreak >nul
echo [+] Daemon started. Rich Presence is active on Discord.
pause
