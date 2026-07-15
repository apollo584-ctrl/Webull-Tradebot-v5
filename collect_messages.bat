@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

set "CHANNEL_URL=https://discord.com/channels/988680941406912512/1026241985444593724"
set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
for %%I in ("%~dp0..\Webull Tradebot v6\local_state\discord_listener.pid") do set "V6_LISTENER_PID=%%~fI"

for /f %%D in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd')"') do set "TODAY=%%D"
echo.
set /p "COLLECTION_START=Beginning date [%TODAY%]: "
if "%COLLECTION_START%"=="" set "COLLECTION_START=%TODAY%"
set /p "COLLECTION_END=Ending date [%COLLECTION_START%]: "
if "%COLLECTION_END%"=="" set "COLLECTION_END=%COLLECTION_START%"

set "DATE_START=%COLLECTION_START%"
set "DATE_END=%COLLECTION_END%"
"%PYTHON_EXE%" -c "import os; from datetime import date; start=date.fromisoformat(os.environ['DATE_START']); end=date.fromisoformat(os.environ['DATE_END']); assert start <= end" >nul 2>nul
if errorlevel 1 (
  echo ERROR: Use YYYY-MM-DD dates with beginning date on or before ending date.
  pause
  exit /b 2
)

set "REFRESH_ARG="
"%PYTHON_EXE%" message_operations.py collection-check --start-date "%COLLECTION_START%" --end-date "%COLLECTION_END%"
if errorlevel 3 (
  echo.
  choice /c YN /n /m "This overlaps a completed range. Refresh it anyway? [Y/N]: "
  if errorlevel 2 exit /b 3
  set "REFRESH_ARG=--confirm-refresh"
) else if errorlevel 1 (
  echo ERROR: Could not check completed collection ranges.
  pause
  exit /b 2
)

call :guard_listener
if errorlevel 1 exit /b 2

call :detect_port
if not defined COLLECTOR_PORT (
  set "DISCORD_CHANNEL_URL=%CHANNEL_URL%"
  set "DISCORD_DEBUG_PORT=9227"
  call launch_discord.bat
  if errorlevel 1 (
    echo ERROR: Could not open the shared Discord Edge profile.
    pause
    exit /b 1
  )
)

echo.
echo Sign in if needed and make sure the Casey channel is visible.
echo This collector is read-only and never posts to Discord.
pause

call :detect_port
if not defined COLLECTOR_PORT (
  echo ERROR: The Casey channel was not found on port 9227 or legacy port 9225.
  pause
  exit /b 1
)

:collect
call :guard_listener
if errorlevel 1 exit /b 2
echo.
echo Collecting Discord messages from %COLLECTION_START% through %COLLECTION_END% on Edge port %COLLECTOR_PORT%...
"%PYTHON_EXE%" discord_collector.py collect --channel-url "%CHANNEL_URL%" --port %COLLECTOR_PORT% --start-date "%COLLECTION_START%" --end-date "%COLLECTION_END%" %REFRESH_ARG%
if not errorlevel 1 goto complete

echo.
echo Collection stopped safely. No wrong-channel messages were written.
choice /c RQ /n /m "Press R to retry after fixing Edge, or Q to quit: "
if errorlevel 2 exit /b 1
goto collect

:complete
echo.
echo Collection complete. The shared archive is data\messages.sqlite3.
pause
exit /b 0

:detect_port
set "COLLECTOR_PORT="
set "PORT_RESULT=%TEMP%\discord_port_%RANDOM%.txt"
"%PYTHON_EXE%" discord_collector.py detect-port --channel-url "%CHANNEL_URL%" --ports 9227 9225 > "%PORT_RESULT%" 2>nul
if errorlevel 1 (
  del /q "%PORT_RESULT%" >nul 2>nul
  exit /b 0
)
set /p "COLLECTOR_PORT="<"%PORT_RESULT%"
del /q "%PORT_RESULT%" >nul 2>nul
exit /b 0

:guard_listener
powershell -NoProfile -Command "$path=$env:V6_LISTENER_PID; if (!(Test-Path -LiteralPath $path)) { exit 1 }; $value=(Get-Content -LiteralPath $path -Raw).Trim(); $claimed=0; if (![int]::TryParse($value, [ref]$claimed)) { exit 1 }; if (Get-Process -Id $claimed -ErrorAction SilentlyContinue) { exit 0 }; exit 1" >nul 2>nul
if not errorlevel 1 (
  echo.
  echo BLOCK: The V6 Discord listener is running. Run STOP_V6_OPERATOR.bat before a historical sweep.
  pause
  exit /b 2
)
exit /b 0
