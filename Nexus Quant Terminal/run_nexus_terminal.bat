@echo off
title Nexus Quant Terminal - Institutional Algorithmic Platform
cd /d "%~dp0"
echo Starting Nexus Quant Terminal Backend...
start cmd /c "python app.py"
echo Waiting for server to start...
set /a retries=0
:WAIT_SERVER
curl.exe -s -o NUL -m 1 http://127.0.0.1:5001/
if %ERRORLEVEL% equ 0 goto SERVER_READY
set /a retries+=1
if %retries% geq 25 goto SERVER_READY
python -c "import time; time.sleep(0.1)"
goto WAIT_SERVER

:SERVER_READY
echo Opening Nexus Quant Terminal in browser...
start "" "http://127.0.0.1:5001"
exit
