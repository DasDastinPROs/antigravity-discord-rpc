@echo off
setlocal
set PID_FILE=%USERPROFILE%\.gemini\antigravity-cli\discord-rpc\daemon.pid
if not exist "%PID_FILE%" (
    echo [!] No active daemon PID file found.
    pause
    exit /b
)

set /p DAEMON_PID=<"%PID_FILE%"
echo [*] Stopping Discord RPC Daemon (PID %DAEMON_PID%)...
taskkill /F /PID %DAEMON_PID% >nul 2>nul
if exist "%PID_FILE%" del /f /q "%PID_FILE%"
echo [+] Daemon stopped successfully.
pause
