@echo off
setlocal EnableExtensions

set "PROJECT_DIR=%~dp0"
set "VENV_PYTHON=%PROJECT_DIR%\.venv\Scripts\python.exe"
set "MODE=%~1"

if /I "%MODE%"=="" set "MODE=scan"

echo Starting Sponsor Hunter Mode...
echo(
echo Mode: %MODE%
echo This process discovers sponsor leads and can send outreach emails.
echo(

if not exist "%PROJECT_DIR%scripts\run_sponsor_hunter.py" (
  echo [ERROR] File not found: "%PROJECT_DIR%scripts\run_sponsor_hunter.py"
  exit /b 1
)

if not exist "%VENV_PYTHON%" (
  echo [ERROR] Virtual environment not found in "%PROJECT_DIR%\.venv".
  echo Run: C:\Users\nicos\Desktop\MiFabricaIA2\inicializar_mifabricaia2.bat init
  exit /b 1
)

cd /d "%PROJECT_DIR%"

if /I "%MODE%"=="send" (
  "%VENV_PYTHON%" scripts\run_sponsor_hunter.py --send
) else (
  "%VENV_PYTHON%" scripts\run_sponsor_hunter.py
)
exit /b %errorlevel%
