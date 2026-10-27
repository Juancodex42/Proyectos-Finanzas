@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
title Bot P2P Binance ARS - Institutional Quantitative Platform

cd /d "%~dp0"

:MENU
cls
echo ===============================================================================
echo        BOT P2P BINANCE ARS -- PLATAFORMA DE ARBITRAJE Y LIQUIDEZ P2P
echo ===============================================================================
echo.
echo   [1] Modo Demo Cuantitativo (Zero-API / Sandbox Institucional)
echo       * Ejecuta simulacion en memoria de libros P2P, Repositioner, Escalera
echo         de Ventas (Opcion A), Oraculo Fiwind y WAC sin requerir API keys.
echo.
echo   [2] Iniciar Bot P2P en Modo Terminal (main.py)
echo       * Requiere variables en .env (Binance API Key, Secret y Telegram).
echo.
echo   [3] Interfaz de Bandeja del Sistema Windows (tray_app.py)
echo       * Monitor visual en segundo plano con alertas y suspension preventiva.
echo.
echo   [4] Menu Launcher Interactivo (launcher.py)
echo       * Panel de control CLI con opciones de diagnostico y limpieza.
echo.
echo   [5] Ejecutar Suite de Tests Unitarios (Pytest - 210 tests offline)
echo       * Valida matematicas, antiban, guardarrailes WAC y anti-colisiones.
echo.
echo   [6] Salir
echo.
echo ===============================================================================
set /p OPCION="Seleccione una opcion [1-6]: "

if "%OPCION%"=="1" goto MODO_DEMO
if "%OPCION%"=="2" goto MODO_MAIN
if "%OPCION%"=="3" goto MODO_TRAY
if "%OPCION%"=="4" goto MODO_LAUNCHER
if "%OPCION%"=="5" goto RUN_TESTS
if "%OPCION%"=="6" goto SALIR

echo.
echo Opcion no valida. Presione cualquier tecla para continuar...
pause > nul
goto MENU

:MODO_DEMO
cls
echo ===============================================================================
echo   INICIANDO MODO DEMO CUANTITATIVO (ZERO-API MODE)
echo ===============================================================================
python scripts/run_demo_showcase.py
echo.
echo Demostracion completada. Presione cualquier tecla para volver al menu...
pause > nul
goto MENU

:MODO_MAIN
cls
echo ===============================================================================
echo   INICIANDO BOT P2P PRINCIPAL (CLI)
echo ===============================================================================
python main.py
echo.
pause
goto MENU

:MODO_TRAY
cls
echo ===============================================================================
echo   INICIANDO BANDEJA DEL SISTEMA WINDOWS
echo ===============================================================================
python tray_app.py
echo.
pause
goto MENU

:MODO_LAUNCHER
cls
echo ===============================================================================
echo   INICIANDO LAUNCHER INTERACTIVO
echo ===============================================================================
python launcher.py
echo.
pause
goto MENU

:RUN_TESTS
cls
echo ===============================================================================
echo   EJECUTANDO SUITE DE TESTS DETERMINISTAS (210 TESTS OFFLINE)
echo ===============================================================================
python -m pytest tests -v
echo.
echo Presione cualquier tecla para volver al menu...
pause > nul
goto MENU

:SALIR
echo Saliendo...
exit /b 0
