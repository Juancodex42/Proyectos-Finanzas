@echo off
title Banco del Valle - Panel de Control

:MENU
cls
echo ======================================================================
echo                 BANCO DEL VALLE - PANEL DE CONTROL
echo ======================================================================
echo.
echo   [1] INICIAR en segundo plano (Web + Celular + Link Directo WhatsApp)
echo   [2] VER / COPIAR LINK DIRECTO al portapapeles
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
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = 8000, 5174; foreach ($p in $ports) { Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*localhost.run*' -or $_.CommandLine -like '*localtunnel*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Remove-Item \"$env:TEMP\bv_tun.log\", \"$env:TEMP\bv_url.txt\" -ErrorAction SilentlyContinue"

:: Obtener IP local de la Wi-Fi
for /f "tokens=*" %%a in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.InterfaceAlias -notlike '*vEthernet*' -and $_.IPAddress -notlike '169.*' } | Select-Object -ExpandProperty IPAddress -First 1)"') do set "LOCAL_IP=%%a"

echo [*] 1/3 Iniciando Backend FastAPI (Puerto 8000)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python' -ArgumentList '-m uvicorn src.main:app --port 8000' -WorkingDirectory '%ROOT%' -WindowStyle Hidden"

echo [*] 2/3 Iniciando Frontend React (Puerto 5174)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c npm run dev' -WorkingDirectory '%ROOT%frontend' -WindowStyle Hidden"

echo [*] 3/3 Levantando Tunel Publico Directo (Sin advertencias ni claves)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$log = \"$env:TEMP\bv_tun.log\"; $urlf = \"$env:TEMP\bv_url.txt\"; Remove-Item $log, $urlf -ErrorAction SilentlyContinue; $cmd = \"while (`$true) { ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:localhost:5174 nokey@localhost.run *>> `\"$log`\"; Start-Sleep -Seconds 2 }\"; Start-Process powershell -ArgumentList \"-NoProfile -ExecutionPolicy Bypass -Command `\"$cmd`\"\" -WindowStyle Hidden; for ($i=0; $i -lt 15; $i++) { Start-Sleep -Milliseconds 800; if (Test-Path $log) { $c = Get-Content $log -Raw -ErrorAction SilentlyContinue; if ($c -match '(https://[a-zA-Z0-9\.\-]+\.lhr\.life)') { $u = $matches[1]; $u | Set-Content $urlf; Set-Clipboard -Value $u; break } } }"

set "TUNNEL_URL="
if exist "%TEMP%\bv_url.txt" (
    for /f "usebackq delims=" %%u in ("%TEMP%\bv_url.txt") do set "TUNNEL_URL=%%u"
)
if "%TUNNEL_URL%"=="" (
    set "TUNNEL_URL=https://generando-enlace... (Elegi opcion [2] en 5 segundos para verlo)"
)

echo.
echo ======================================================================
echo   [EXITO] Banco del Valle esta corriendo en segundo plano!
echo ======================================================================
echo.
echo   ------------------------------------------------------------------
echo      1. LINK DIRECTO PARA COMPARTIR POR WHATSAPP:
echo         %TUNNEL_URL%
echo      (COPIADO AL PORTAPAPELES AUTOMATICAMENTE - Usa Ctrl+V en WhatsApp)
echo      * Abre DIRECTO en celulares y PC sin advertencias ni contrase?as.
echo   ------------------------------------------------------------------
echo.
echo   ------------------------------------------------------------------
echo      2. LINK PARA TU CELULAR EN CASA (Por Wi-Fi):
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
set "TUNNEL_URL="
if exist "%TEMP%\bv_url.txt" (
    for /f "usebackq delims=" %%u in ("%TEMP%\bv_url.txt") do set "TUNNEL_URL=%%u"
) else if exist "%TEMP%\bv_tun.log" (
    for /f "tokens=*" %%u in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$c = Get-Content \"$env:TEMP\bv_tun.log\" -Raw -ErrorAction SilentlyContinue; if ($c -match '(https://[a-zA-Z0-9\.\-]+\.lhr\.life)') { $matches[1] }"') do set "TUNNEL_URL=%%u"
)

if not "%TUNNEL_URL%"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-Clipboard -Value '%TUNNEL_URL%'"
) else (
    set "TUNNEL_URL=No hay un tunel activo. Inicia primero con la opcion [1]."
)

for /f "tokens=*" %%a in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.InterfaceAlias -notlike '*vEthernet*' -and $_.IPAddress -notlike '169.*' } | Select-Object -ExpandProperty IPAddress -First 1)"') do set "LOCAL_IP=%%a"

echo ======================================================================
echo                 LINK DIRECTO OFICIAL - BANCO DEL VALLE
echo ======================================================================
echo.
echo   [+] Link Directo WhatsApp (Copiado a tu portapapeles con Ctrl+V):
echo       %TUNNEL_URL%
echo       * Abre DIRECTO en celulares y PC (Sin avisos de phishing ni claves).
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

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = 8000, 5174; foreach ($p in $ports) { Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host ('[OK] Servidor detenido en puerto ' + $p) } }; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*localhost.run*' -or $_.CommandLine -like '*localtunnel*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host '[OK] Tuneles detenidos' }; Remove-Item \"$env:TEMP\bv_tun.log\", \"$env:TEMP\bv_url.txt\" -ErrorAction SilentlyContinue"

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
