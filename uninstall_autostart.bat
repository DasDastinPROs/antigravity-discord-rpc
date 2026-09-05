@echo off
setlocal
set STARTUP_SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AntigravityDiscordRPC.lnk
if exist "%STARTUP_SHORTCUT%" (
    del /f /q "%STARTUP_SHORTCUT%"
    echo [+] Successfully removed from Windows Startup.
) else (
    echo [!] Shortcut was not found in Startup folder.
)
pause
