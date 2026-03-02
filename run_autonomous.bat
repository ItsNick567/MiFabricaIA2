@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
set "PROJECT_DIR=%ROOT_DIR%tutorial_pipeline_v2"
set "VENV_PYTHON=%PROJECT_DIR%\.venv\Scripts\python.exe"

echo Starting Tutorial Pipeline Autonomous Mode...
echo(
echo This process will generate and publish tutorials automatically.
echo Press Ctrl+C to stop.
echo(

if not exist "%PROJECT_DIR%\autonomous_pipeline.py" (
  echo [ERROR] File not found: "%PROJECT_DIR%\autonomous_pipeline.py"
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
"%VENV_PYTHON%" autonomous_pipeline.py
exit /b %errorlevel%
