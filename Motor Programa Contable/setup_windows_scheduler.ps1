# Script de Configuración para la Tarea Programada de Windows
$TaskName = "SistemaContable_AutoSync"
$ProjectRoot = $PSScriptRoot
$VbsPath = Join-Path $ProjectRoot "launch_autosync_silent.vbs"
$ScriptPath = Join-Path $ProjectRoot "webapp\backend\workers\auto_sync_worker.py"
$LogPath = Join-Path $ProjectRoot "webapp\backend\uploads\auto_sync.log"

Write-Host "Configurando la Tarea Programada '$TaskName' en Windows..." -ForegroundColor Cyan

# Definir la acción (ejecutar en segundo plano desde la raíz del proyecto y escribir logs)
$Action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsPath`"" -WorkingDirectory $ProjectRoot

# Definir los desencadenadores (Al iniciar sesión y diariamente a las 20:00)
$TriggerLogon = New-ScheduledTaskTrigger -AtLogon
$TriggerDaily = New-ScheduledTaskTrigger -Daily -At "20:00"

# Ajustes para bajo consumo de batería / segundo plano
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Registrar la tarea en el sistema
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($TriggerLogon, $TriggerDaily) -Settings $Settings -Description "Sincronización silenciosa diaria de APIs para el Sistema Contable" -Force

Write-Host "¡Tarea programada registrada exitosamente!" -ForegroundColor Green
Write-Host "La sincronización se ejecutará automáticamente en segundo plano al iniciar sesión y todos los días a las 20:00 hs." -ForegroundColor Yellow
