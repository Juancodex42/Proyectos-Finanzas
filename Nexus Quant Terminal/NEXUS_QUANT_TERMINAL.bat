@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
title Nexus Quant Terminal - Institutional Algorithmic Platform

cd /d "%~dp0"

:MENU
cls
echo ===============================================================================
echo        NEXUS QUANT TERMINAL -- INSTITUTIONAL ALGORITHMIC PLATFORM
echo ===============================================================================
echo.
echo   [1] Iniciar Terminal Cuantitativo Web (Modo Demo Zero-API)
echo       * Inicia el servidor Flask en http://127.0.0.1:5001 con datasets locales,
echo         simuladores de campana, optimizador genetico y abre la interfaz web.
echo.
echo   [2] Iniciar Servidor en Consola Directa (app.py)
echo       * Ejecuta Flask en primer plano para visualizar telemetria y logs.
echo.
echo   [3] Ejecutar Suite de Tests Unitarios (Pytest - 516 tests offline)
echo       * Valida motores de simulacion, Walk-Forward, Barbell, PineScript y API.
echo.
echo   [4] Salir
echo.
echo ===============================================================================
set /p OPCION="Seleccione una opcion [1-4]: "

if "%OPCION%"=="1" goto MODO_DEMO
if "%OPCION%"=="2" goto MODO_APP
if "%OPCION%"=="3" goto RUN_TESTS
if "%OPCION%"=="4" goto SALIR

echo.
echo Opcion no valida. Presione cualquier tecla para continuar...
pause > nul
goto MENU

:MODO_DEMO
cls
echo ===============================================================================
echo   INICIANDO NEXUS QUANT TERMINAL (MODO DEMO ZERO-API)
echo ===============================================================================
echo.
echo [1/2] Iniciando backend analitico en segundo plano...
start "Nexus Quant Backend" cmd /c "python app.py"

echo [2/2] Esperando inicializacion del servidor local...
set /a retries=0
:WAIT_SERVER
curl.exe -s -o NUL -m 1 http://127.0.0.1:5001/
if %ERRORLEVEL% equ 0 goto SERVER_READY
set /a retries+=1
if %retries% geq 30 goto SERVER_READY
python -c "import time; time.sleep(0.3)"
goto WAIT_SERVER

:SERVER_READY
echo.
echo Servidor listo en http://127.0.0.1:5001. Abriendo interfaz en el navegador...
start "" "http://127.0.0.1:5001"
echo.
echo La terminal cuantitativa esta activa. Presione cualquier tecla para volver al menu...
pause > nul
goto MENU

:MODO_APP
cls
echo ===============================================================================
echo   INICIANDO SERVIDOR EN CONSOLA DIRECTA
echo ===============================================================================
python app.py
echo.
pause
goto MENU

:RUN_TESTS
cls
echo ===============================================================================
echo   EJECUTANDO SUITE COMPLETA DE TESTS DETERMINISTAS (516 TESTS OFFLINE)
echo ===============================================================================
python -m pytest tests -v
echo.
echo Presione cualquier tecla para volver al menu...
pause > nul
goto MENU

:SALIR
echo Saliendo...
exit /b 0
