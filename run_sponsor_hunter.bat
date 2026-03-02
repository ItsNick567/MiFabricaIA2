@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
set "PROJECT_DIR=%ROOT_DIR%tutorial_pipeline_v2"
set "VENV_PYTHON=%PROJECT_DIR%\.venv\Scripts\python.exe"
set "MODE=%~1"

if /I "%MODE%"=="" set "MODE=scan"

echo Starting Sponsor Hunter Mode...
echo(
echo Mode: %MODE%
echo This process discovers sponsor leads and can send outreach emails.
echo(

if not exist "%PROJECT_DIR%\scripts\run_sponsor_hunter.py" (
  echo [ERROR] File not found: "%PROJECT_DIR%\scripts\run_sponsor_hunter.py"
  exit /b 1
)

if not exist "%VENV_PYTHON%" (
  echo [INFO] Virtual environment not found. Running project init...
  call "%ROOT_DIR%inicializar_mifabricaia2.bat" init
  if errorlevel 1 (
    echo [ERROR] Initialization failed.
    exit /b 1
  )
)

cd /d "%PROJECT_DIR%"

if /I "%MODE%"=="send" (
  "%VENV_PYTHON%" scripts\run_sponsor_hunter.py --send
) else (
  "%VENV_PYTHON%" scripts\run_sponsor_hunter.py
)
exit /b %errorlevel%
