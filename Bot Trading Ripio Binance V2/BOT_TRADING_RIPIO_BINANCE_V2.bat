@echo off
title Bot Trading Ripio-Binance V2.0 - Panel de Control Cuantitativo

:MENU
cls
echo ============================================================================
echo          BOT TRADING RIPIO-BINANCE V2.0 - PANEL DE CONTROL CUANTITATIVO
echo ============================================================================
echo.
echo   [1] EJECUTAR DEMO EN VIVO (Simulacion Market Making Stoikov + Arbitraje Estadistico sin APIs)
echo   [2] EJECUTAR MOTOR DE BACKTESTING CUANTITATIVO (Walk-Forward + Monte Carlo + Reporte)
echo   [3] EJECUTAR SUITE DE TESTS UNITARIOS (Pytest Offline)
echo   [4] Salir
echo.
echo ============================================================================
set /p OPCION="Elegi una opcion (1, 2, 3 o 4) y presiona Enter: "

if "%OPCION%"=="1" goto DEMO
if "%OPCION%"=="2" goto BACKTEST
if "%OPCION%"=="3" goto TESTS
if "%OPCION%"=="4" goto SALIR
goto MENU

:DEMO
cls
echo ============================================================================
echo   Iniciando Demo Cuantitativa en Vivo (Modo Zero-API)...
echo ============================================================================
echo.
cd /d "%~dp0"
python main.py --mode demo
echo.
pause
goto MENU

:BACKTEST
cls
echo ============================================================================
echo   Ejecutando Motor de Backtesting Cuantitativo Completo...
echo ============================================================================
echo.
cd /d "%~dp0"
python run_backtest.py --mode full --synthetic --days 30 --capital 10000 --simulations 1000 --permutations 1000 --export
echo.
pause
goto MENU

:TESTS
cls
echo ============================================================================
echo   Ejecutando Suite de Tests Unitarios Deterministas (Pytest Offline)...
echo ============================================================================
echo.
cd /d "%~dp0"
python -m pytest -v
echo.
pause
goto MENU

:SALIR
exit
