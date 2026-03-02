@echo off
setlocal EnableExtensions

REM =========================================================
REM Inicializador de MiFabricaIA2 / Tutorial Pipeline v2
REM Uso:
REM   inicializar_mifabricaia2.bat           -> init + run
REM   inicializar_mifabricaia2.bat init      -> solo init
REM   inicializar_mifabricaia2.bat run       -> solo run (asume init previo)
REM =========================================================

set "ROOT_DIR=%~dp0"
set "PROJECT_DIR=%ROOT_DIR%tutorial_pipeline_v2"
set "VENV_DIR=%PROJECT_DIR%\.venv"

if not exist "%PROJECT_DIR%\app.py" (
  echo [ERROR] No se encontro "%PROJECT_DIR%\app.py"
  echo Ejecuta este .bat desde la raiz de MiFabricaIA2.
  exit /b 1
)

if /I "%~1"=="init" goto :init_only
if /I "%~1"=="run" goto :run_only

goto :init_and_run

:check_python
where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python no esta en PATH.
  echo Instala Python 3.11+ y marca "Add python.exe to PATH".
  exit /b 1
)
exit /b 0

:create_env_file
if not exist "%PROJECT_DIR%\.env" (
  if exist "%PROJECT_DIR%\.env.example" (
    copy "%PROJECT_DIR%\.env.example" "%PROJECT_DIR%\.env" >nul
    echo [OK] Se creo .env desde .env.example
    echo [IMPORTANTE] Edita "%PROJECT_DIR%\.env" con tus API keys.
  ) else (
    echo [WARN] No existe .env.example, no se pudo crear .env automaticamente.
  )
) else (
  echo [OK] .env ya existe.
)
exit /b 0

:setup_project
call :check_python
if errorlevel 1 exit /b 1

cd /d "%PROJECT_DIR%"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [INFO] Creando entorno virtual...
  python -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [ERROR] No se pudo crear el entorno virtual.
    exit /b 1
  )
) else (
  echo [OK] Entorno virtual detectado.
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] No se pudo activar el entorno virtual.
  exit /b 1
)

echo [INFO] Actualizando pip...
python -m pip install --upgrade pip
if errorlevel 1 (
  echo [ERROR] Fallo al actualizar pip.
  exit /b 1
)

echo [INFO] Instalando dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Fallo instalando dependencias.
  exit /b 1
)

call :create_env_file
if errorlevel 1 exit /b 1

echo [INFO] Inicializando directorios/data base...
python -c "from utils.paths import ensure_dirs; ensure_dirs(); print('Directorios inicializados')"
if errorlevel 1 (
  echo [ERROR] Fallo inicializando estructura de directorios.
  exit /b 1
)

echo [OK] Inicializacion completada.
exit /b 0

:run_app
cd /d "%PROJECT_DIR%"

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [ERROR] No existe entorno virtual. Ejecuta primero:
  echo   inicializar_mifabricaia2.bat init
  exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] No se pudo activar el entorno virtual.
  exit /b 1
)

echo [INFO] Iniciando Streamlit...
echo [INFO] URL esperada: http://localhost:8501
python -m streamlit run app.py
exit /b %errorlevel%

:init_only
call :setup_project
exit /b %errorlevel%

:run_only
call :run_app
exit /b %errorlevel%

:init_and_run
call :setup_project
if errorlevel 1 exit /b 1
call :run_app
exit /b %errorlevel%
