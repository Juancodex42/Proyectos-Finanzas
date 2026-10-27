@echo off
title Banco del Valle - Panel de Control

:MENU
cls
echo ======================================================================
echo                 BANCO DEL VALLE - PANEL DE CONTROL
echo ======================================================================
echo.
echo   [1] INICIAR en segundo plano (Web + Link Publico)
echo   [2] VER / COPIAR LINK PUBLICO al portapapeles
echo   [3] DETENER servidores (Apagar Banco del Valle)
echo   [4] EJECUTAR TESTS UNITARIOS (Pytest)
echo   [5] Salir
echo.
echo ======================================================================
set /p OPCION="Elegi una opcion (1, 2, 3, 4 o 5) y presiona Enter: "

if "%OPCION%"=="1" goto INICIAR
if "%OPCION%"=="2" goto VERLINK
if "%OPCION%"=="3" goto DETENER
if "%OPCION%"=="4" goto TESTS
if "%OPCION%"=="5" goto SALIR
goto MENU

:INICIAR
cls
echo ======================================================================
echo   Iniciando Banco del Valle en segundo plano...
echo ======================================================================
echo.

if exist "%~dp0Banco Del Valle\src\main.py" (
    set "ROOT=%~dp0"
) else if exist "%~dp0src\main.py" (
    set "ROOT=%~dp0"
) else (
    set "ROOT=%~dp0"
)

echo [*] 1/3 Iniciando Backend FastAPI (Puerto 8000)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python' -ArgumentList '-m uvicorn src.main:app --port 8000' -WorkingDirectory '%ROOT%' -WindowStyle Hidden"

echo [*] 2/3 Iniciando Frontend React (Puerto 5174)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c npm run dev' -WorkingDirectory '%ROOT%frontend' -WindowStyle Hidden"

echo [*] 3/3 Levantando Tunel Publico Seguro (Localtunnel)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c npx localtunnel --port 5174 --subdomain banco-del-valle' -WindowStyle Hidden"

:: Copiar automaticamente al portapapeles de Windows
powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-Clipboard -Value 'https://banco-del-valle.loca.lt'"

echo.
echo ======================================================================
echo   [EXITO] Sistema corriendo en segundo plano!
echo.
echo   ------------------------------------------------------------------
echo      TU LINK PUBLICO (COPIADO AL PORTAPAPELES AUTOMATICAMENTE):
echo      https://banco-del-valle.loca.lt
echo   ------------------------------------------------------------------
echo   (Ya podes presionar Ctrl + V en WhatsApp o correo para enviarlo)
echo.
echo   - Tu link local en esta PC:
echo     http://localhost:5174
echo.
echo   (Ya podes cerrar esta consola con la [X], el sistema no se apagara)
echo ======================================================================
echo.
echo Abriendo aplicacion en tu navegador...
ping 127.0.0.1 -n 6 >nul
start http://localhost:5174
echo.
pause
goto MENU

:VERLINK
cls
echo ======================================================================
echo                   LINK PUBLICO DE BANCO DEL VALLE
echo ======================================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-Clipboard -Value 'https://banco-del-valle.loca.lt'"
echo   ------------------------------------------------------------------
echo      LINK PUBLICO:
echo      https://banco-del-valle.loca.lt
echo   ------------------------------------------------------------------
echo.
echo   [OK] El link se acaba de COPIAR a tu portapapeles!
echo   Ya podes ir a cualquier chat o ventana y apretar Ctrl + V para pegarlo.
echo.
echo ======================================================================
pause
goto MENU

:DETENER
cls
echo ======================================================================
echo   Deteniendo Banco del Valle...
echo ======================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = 8000, 5174; foreach ($p in $ports) { Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host ('[OK] Servidor detenido en puerto ' + $p) } }"

echo.
echo ======================================================================
echo   [OK] Servidores de Banco del Valle apagados con exito.
echo   Tus otros bots y programas continuan funcionando intactos.
echo ======================================================================
echo.
pause
goto MENU

:TESTS
cls
echo ======================================================================
echo   EJECUTANDO SUITE DE TESTS UNITARIOS (Pytest)
echo ======================================================================
echo.
python -m pytest "%~dp0tests_unitarios" -v
echo.
echo ======================================================================
pause
goto MENU

:SALIR
exit
