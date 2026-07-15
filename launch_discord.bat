@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

set "PORT=%DISCORD_DEBUG_PORT%"
if "%PORT%"=="" set "PORT=9227"
set "URL=%DISCORD_CHANNEL_URL%"
if "%URL%"=="" set "URL=https://discord.com/channels/@me"
set "V6_DIR=%~dp0..\Webull Tradebot v6"
if not exist "%V6_DIR%\operator\start_edge_discord.ps1" (
  echo ERROR: V6 Edge launcher was not found.
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%V6_DIR%\operator\start_edge_discord.ps1" -ChannelUrl "%URL%" -Port %PORT%
if errorlevel 1 (
  echo ERROR: The dedicated V6 Edge profile was not ready.
  exit /b 1
)
