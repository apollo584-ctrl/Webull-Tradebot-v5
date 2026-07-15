@echo off
setlocal
cd /d "%~dp0"

set "PORT=%DISCORD_DEBUG_PORT%"
if "%PORT%"=="" set "PORT=9227"
set "URL=%DISCORD_CHANNEL_URL%"
if "%URL%"=="" set "URL=https://discord.com/channels/@me"
for %%I in ("%~dp0..\Webull Tradebot v6\local_state\edge_discord_profile_v6_readonly") do set "PROFILE=%%~fI"

set "EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" (
  echo ERROR: Microsoft Edge was not found.
  exit /b 1
)

start "" "%EDGE%" --remote-debugging-port=%PORT% --remote-allow-origins=http://127.0.0.1:%PORT% --user-data-dir="%PROFILE%" --no-first-run --no-default-browser-check "%URL%"
