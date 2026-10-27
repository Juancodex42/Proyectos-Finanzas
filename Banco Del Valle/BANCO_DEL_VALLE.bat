@echo off
title Banco del Valle - Panel de Control

:MENU
cls
echo ======================================================================
echo                 BANCO DEL VALLE - PANEL DE CONTROL
echo ======================================================================
echo.
echo   [1] INICIAR en segundo plano (Web + Celular + Link Bonito WhatsApp)
echo   [2] VER / COPIAR LINK BONITO al portapapeles
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
    set "ROOT=%~dp0Banco Del Valle\"
) else if exist "%~dp0src\main.py" (
    set "ROOT=%~dp0"
) else (
    set "ROOT=%~dp0"
)

:: Limpiar procesos anteriores si los hubiera
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = 8000, 5174; foreach ($p in $ports) { Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*localtunnel*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

:: Obtener IP local de la Wi-Fi
for /f "tokens=*" %%a in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.InterfaceAlias -notlike '*vEthernet*' -and $_.IPAddress -notlike '169.*' } | Select-Object -ExpandProperty IPAddress -First 1)"') do set "LOCAL_IP=%%a"

:: Obtener IP publica para desbloqueo rapido en celular si lo requiere localtunnel
for /f "tokens=*" %%p in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Invoke-RestMethod -Uri 'https://api.ipify.org' -TimeoutSec 2) } catch { '186.12.204.75' }"') do set "PUBLIC_IP=%%p"

echo [*] 1/3 Iniciando Backend FastAPI (Puerto 8000)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python' -ArgumentList '-m uvicorn src.main:app --port 8000' -WorkingDirectory '%ROOT%' -WindowStyle Hidden"

echo [*] 2/3 Iniciando Frontend React (Puerto 5174)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c npm run dev' -WorkingDirectory '%ROOT%frontend' -WindowStyle Hidden"

echo [*] 3/3 Levantando Tunel Publico con Link Bonito (banco-del-valle-oficial)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c powershell -NoProfile -ExecutionPolicy Bypass -Command \"while ($true) { npx -y localtunnel --port 5174 --subdomain banco-del-valle-oficial; Start-Sleep -Seconds 2 }\"' -WindowStyle Hidden"

:: Copiar automaticamente el link bonito al portapapeles de Windows
powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-Clipboard -Value 'https://banco-del-valle-oficial.loca.lt'"

echo.
echo ======================================================================
echo   [EXITO] Banco del Valle esta corriendo en segundo plano!
echo ======================================================================
echo.
echo   ------------------------------------------------------------------
echo      1. LINK BONITO PARA COMPARTIR POR WHATSAPP:
echo         https://banco-del-valle-oficial.loca.lt
echo      (COPIADO AL PORTAPAPELES AUTOMATICAMENTE - Usa Ctrl+V en WhatsApp)
echo      * Si en el celular pide "Tunnel Password", es: %PUBLIC_IP%
echo   ------------------------------------------------------------------
echo.
echo   ------------------------------------------------------------------
echo      2. LINK PARA TU CELULAR (En casa por Wi-Fi - Sin pedir clave):
echo         http://%COMPUTERNAME%.local:5174
echo         o: http://%LOCAL_IP%:5174
echo   ------------------------------------------------------------------
echo.
echo   ------------------------------------------------------------------
echo      3. LINK PARA ESTA COMPUTADORA:
echo         http://localhost:5174
echo   ------------------------------------------------------------------
echo.
echo   (Podes cerrar esta ventana con la [X], el sistema no se apagara)
echo ======================================================================
echo.
echo Abriendo aplicacion en tu navegador...
ping 127.0.0.1 -n 4 >nul
start http://localhost:5174
echo.
pause
goto MENU

:VERLINK
cls
for /f "tokens=*" %%a in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.InterfaceAlias -notlike '*vEthernet*' -and $_.IPAddress -notlike '169.*' } | Select-Object -ExpandProperty IPAddress -First 1)"') do set "LOCAL_IP=%%a"

for /f "tokens=*" %%p in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Invoke-RestMethod -Uri 'https://api.ipify.org' -TimeoutSec 2) } catch { '186.12.204.75' }"') do set "PUBLIC_IP=%%p"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-Clipboard -Value 'https://banco-del-valle-oficial.loca.lt'"

echo ======================================================================
echo                 LINK BONITO OFICIAL - BANCO DEL VALLE
echo ======================================================================
echo.
echo   [+] Link Bonito para WhatsApp (Copiado a tu portapapeles con Ctrl+V):
echo       https://banco-del-valle-oficial.loca.lt
echo       * Clave de desbloqueo si el celular la pide: %PUBLIC_IP%
echo.
echo   [+] Link para tu celular en casa por Wi-Fi:
echo       http://%COMPUTERNAME%.local:5174
echo       o: http://%LOCAL_IP%:5174
echo.
echo   [+] Para esta PC:
echo       http://localhost:5174
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

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = 8000, 5174; foreach ($p in $ports) { Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host ('[OK] Servidor detenido en puerto ' + $p) } }; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*localtunnel*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host '[OK] Tuneles detenidos' }"

echo.
echo ======================================================================
echo   [OK] Servidores y tuneles de Banco del Valle apagados con exito.
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
