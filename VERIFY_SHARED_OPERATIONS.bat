@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
set "LOG_PATH=data\shared_operations_verify.log"

if not exist "data" mkdir "data"
>"%LOG_PATH%" echo Shared operation verification started %DATE% %TIME%

"%PYTHON_EXE%" verify_shared_operations.py >>"%LOG_PATH%" 2>&1
if errorlevel 1 goto failed

>>"%LOG_PATH%" echo Verification passed.
echo Verification passed. Full output: %CD%\%LOG_PATH%
exit /b 0

:failed
>>"%LOG_PATH%" echo Verification failed with exit code %errorlevel%.
echo Verification failed. Open: %CD%\%LOG_PATH%
exit /b 1
