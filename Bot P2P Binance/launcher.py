"""
Lanzador interactivo para la consola de Windows.
Inicia el bot en segundo plano (tray_app.py) con icono en la bandeja del sistema y visor de logs.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Asegurar que src/ esté en el path para imports absolutos
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

# Asegurar encoding UTF-8 en la consola
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent
PORT_LOCK = 29170
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def is_already_running() -> bool:
    """Verifica si el daemon del bot ya está en ejecución."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.connect(("127.0.0.1", PORT_LOCK))
        sock.sendall(b"SHOW\n")
        return True
    except Exception:
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def get_pythonw_path() -> str:
    """Localiza el ejecutable pythonw.exe correspondiente al entorno actual."""
    candidate = sys.executable.replace("python.exe", "pythonw.exe")
    if os.path.exists(candidate):
        return candidate
    return sys.executable


def stream_logs_until_init(
    log_path: Path,
    max_wait_seconds: int = 40,
    start_pos: Optional[int] = None,
    proc: Optional[subprocess.Popen] = None,
) -> bool:
    """
    Lee en tiempo real las nuevas líneas de bot.log hasta que la inicialización
    se complete o se agote el tiempo de espera.
    """
    if start_pos is None:
        start_pos = os.path.getsize(log_path) if log_path.exists() else 0

    start_time = time.time()
    initialized = False

    while time.time() - start_time < max_wait_seconds:
        if log_path.exists():
            curr_size = os.path.getsize(log_path)
            if curr_size < start_pos:
                start_pos = 0
            if curr_size > start_pos:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(start_pos)
                    for line in f:
                        print(line, end="", flush=True)
                        if (
                            "Inicialización completa" in line
                            or "Modo Standby" in line
                            or "modo ESPERA (Standby)" in line
                        ):
                            initialized = True
                    start_pos = f.tell()

        if initialized:
            break
        if proc is not None and proc.poll() is not None:
            break
        time.sleep(0.3)

    return initialized


def tail_live_logs(log_path: Path):
    """Mantiene el seguimiento en vivo de los logs mientras la pestaña esté abierta."""
    last_pos = os.path.getsize(log_path) if log_path.exists() else 0
    try:
        while True:
            if log_path.exists():
                curr_size = os.path.getsize(log_path)
                if curr_size > last_pos:
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_pos)
                        for line in f:
                            print(line, end="", flush=True)
                        last_pos = f.tell()
                elif curr_size < last_pos:
                    last_pos = 0
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n" + "─" * 65)
        print(" [i] Cerrando esta pestaña de consola.")
        print(" [i] El bot continúa ejecutándose en segundo plano (icono ^).")
        print("─" * 65)
        time.sleep(1.5)


def main():
    print("=" * 68)
    print("           INICIANDO BOT P2P BINANCE ARS (SEGUNDO PLANO)")
    print("=" * 68)

    # 1. Comprobar si ya está corriendo
    if is_already_running():
        print()
        print(" ℹ️  EL BOT YA SE ENCUENTRA EN EJECUCIÓN EN SEGUNDO PLANO.")
        print(" 📍 Puedes verlo en la bandeja del sistema (flecha 'Mostrar iconos ocultos' ^).")
        print(" 🖥️  Se ha abierto la ventana de logs en pantalla.")
        print()
        print("=" * 68)
        time.sleep(3)
        return

    # 2. Iniciar el proceso en segundo plano desacoplado
    pythonw = get_pythonw_path()
    cmd = [pythonw, str(PROJECT_ROOT / "tray_app.py")]
    log_file = PROJECT_ROOT / "logs" / "bot.log"
    initial_log_pos = os.path.getsize(log_file) if log_file.exists() else 0

    print(" [1/3] Lanzando servicio en segundo plano e icono de bandeja...")
    flags = 0
    if sys.platform == "win32":
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        creationflags=flags,
        close_fds=True,
    )

    print(f" [2/3] Proceso creado (PID: {proc.pid}). Conectando logs de arranque...")
    print("─" * 68)

    # 3. Seguir logs de inicio
    time.sleep(0.5)
    init_ok = stream_logs_until_init(
        log_file,
        max_wait_seconds=45,
        start_pos=initial_log_pos,
        proc=proc,
    )

    if proc.poll() is not None:
        print()
        print("=" * 68)
        print(f" ❌ ERROR: El proceso finalizó prematuramente (código: {proc.returncode}).")
        print("    Revisa los logs anteriores o el archivo bot.log para más detalles.")
        print("=" * 68)
        return

    # 4. Mensaje informativo de cierre seguro
    print()
    print("=" * 68)
    if init_ok:
        print("           ✅ BOT INICIALIZADO Y LISTO EN SEGUNDO PLANO")
    else:
        print("           ⏳ BOT EN ARRANQUE (CONTINÚA EN SEGUNDO PLANO)")
    print("=" * 68)
    print(" 📍 Icono activo en la bandeja del sistema (flecha 'iconos ocultos' ^).")
    print(" 🟡 Modo inicial: EN ESPERA (Standby).")
    print("    El bot NO operará ni colocará órdenes hasta que lo enciendas.")
    print()
    print(" 📱 Para activarlo, usa Telegram enviando /encender o toca el botón")
    print("    '🟢 Encender Bot' en el panel que te envió el bot.")
    print()
    print(" 💡 YA PUEDES CERRAR ESTA PESTAÑA CON LA [X] EN CUALQUIER MOMENTO.")
    print("    El bot seguirá corriendo en segundo plano.")
    print("    Al hacer clic en el icono de la consola en los iconos ocultos,")
    print("    podrás volver a ver los logs en vivo.")
    print("=" * 68)
    print()
    print(" [Presiona Ctrl + C o cierra esta ventana cuando lo desees]")
    print()

    # 5. Mantener streaming de logs por si el usuario decide dejar la ventana abierta
    tail_live_logs(log_file)


if __name__ == "__main__":
    main()
