@echo off
setlocal EnableExtensions

set "PROJECT_DIR=%~dp0"
set "VENV_PYTHON=%PROJECT_DIR%\.venv\Scripts\python.exe"

echo Starting Tutorial Pipeline Autonomous Mode...
echo(
echo This process will generate and publish tutorials automatically.
echo Press Ctrl+C to stop.
echo(

if not exist "%PROJECT_DIR%autonomous_pipeline.py" (
  echo [ERROR] File not found: "%PROJECT_DIR%autonomous_pipeline.py"
  exit /b 1
)

if not exist "%VENV_PYTHON%" (
  echo [ERROR] Virtual environment not found in "%PROJECT_DIR%\.venv".
  echo Run: C:\Users\nicos\Desktop\MiFabricaIA2\inicializar_mifabricaia2.bat init
  exit /b 1
)

cd /d "%PROJECT_DIR%"
"%VENV_PYTHON%" autonomous_pipeline.py
exit /b %errorlevel%
