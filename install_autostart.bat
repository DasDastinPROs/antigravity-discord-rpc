@echo off
setlocal
cd /d "%~dp0"

echo [*] Installing Antigravity Discord RPC to Windows Startup...

set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set VBS_SCRIPT=%TEMP%\create_shortcut.vbs

where pythonw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    for /f "tokens=*" %%i in ('where pythonw') do set PYTHONW_PATH=%%i
) else (
    for /f "tokens=*" %%i in ('where python') do set PYTHONW_PATH=%%i
)

set DAEMON_SCRIPT=%~dp0scripts\discord_daemon.py

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS_SCRIPT%"
echo sLinkFile = "%STARTUP_DIR%\AntigravityDiscordRPC.lnk" >> "%VBS_SCRIPT%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%VBS_SCRIPT%"
echo oLink.TargetPath = "%PYTHONW_PATH%" >> "%VBS_SCRIPT%"
echo oLink.Arguments = """%DAEMON_SCRIPT%""" >> "%VBS_SCRIPT%"
echo oLink.WorkingDirectory = "%~dp0" >> "%VBS_SCRIPT%"
echo oLink.WindowStyle = 7 >> "%VBS_SCRIPT%"
echo oLink.Description = "Antigravity CLI Discord Rich Presence Daemon" >> "%VBS_SCRIPT%"
echo oLink.Save >> "%VBS_SCRIPT%"

cscript /nologo "%VBS_SCRIPT%"
del /f /q "%VBS_SCRIPT%"

echo [+] Successfully added to Windows Startup!
echo [+] The Discord RPC daemon will now automatically start when Windows boots up.
pause
