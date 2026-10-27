@echo off
cd /d "%~dp0"
echo ===================================================
echo           CRYPTOTAX PRO - INICIANDO...
echo ===================================================
echo.

rem Check node_modules inside webapp/frontend
if not exist "webapp\frontend\node_modules" (
    echo [1/2] Instalando dependencias del Frontend - Primera ejecucion...
    pushd webapp\frontend
    call npm install
    if errorlevel 1 (
        echo [ERROR] Fallo la instalacion de dependencias del Frontend.
        popd
        pause
        exit /b 1
    )
    popd
) else (
    echo [1/2] Dependencias del Frontend ya instaladas. Omitiendo.
)

echo.
echo [2/2] Iniciando Sistema Contable...

rem Localizar ejecutable de Python
set "PY_CMD=python"
where python >nul 2>&1
if errorlevel 1 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    )
)

"%PY_CMD%" start_system.py
if errorlevel 1 (
    echo.
    echo [ERROR] Hubo un problema al iniciar el sistema contable.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo Proceso de inicio completado con exito.
echo ===================================================
ping 127.0.0.1 -n 3 >nul
