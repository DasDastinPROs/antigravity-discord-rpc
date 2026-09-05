# Antigravity Discord RPC - PowerShell Installer
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "     Antigravity CLI Discord RPC & Activity Logger Installer    " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# 1. Check Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[!] Python 3.8+ is required. Please install Python from https://python.org" -ForegroundColor Red
    exit 1
}

$targetDir = Join-Path $env:USERPROFILE ".gemini\config\plugins\discord-rpc"
$pluginsDir = Join-Path $env:USERPROFILE ".gemini\config\plugins"

if (-not (Test-Path $pluginsDir)) {
    New-Item -ItemType Directory -Path $pluginsDir -Force | Out-Null
}

if ($PSScriptRoot -and ($PSScriptRoot -ne $targetDir)) {
    Write-Host "[*] Copying files to $targetDir..." -ForegroundColor Gray
    Copy-Item -Path "$PSScriptRoot\*" -Destination $targetDir -Recurse -Force
}

Set-Location $targetDir

$settingsPath = Join-Path $targetDir "settings.json"
$exampleSettings = Join-Path $targetDir "settings.example.json"
if (-not (Test-Path $settingsPath) -and (Test-Path $exampleSettings)) {
    Copy-Item $exampleSettings $settingsPath
    Write-Host "[+] Initialized settings.json from template." -ForegroundColor Green
}

python (Join-Path $targetDir "scripts\setup_plugin.py")

Write-Host "`n================================================================" -ForegroundColor Cyan
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "  - Settings:  $targetDir\settings.bat"
Write-Host "  - Logs:      $targetDir\view_logs.bat"
Write-Host "================================================================`n" -ForegroundColor Cyan
