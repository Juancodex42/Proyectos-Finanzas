"""
Aplicación principal en segundo plano (Daemon / System Tray).
Coordina instancia única, motor BotEngine, icono pystray y visor Tkinter LogViewer.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Optional

# Asegurar que src/ esté en el path para imports absolutos
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import tkinter as tk

# Asegurar encoding UTF-8 en Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Configurar Logging
LOG_FILE_PATH = Path(__file__).resolve().parent / "logs" / "bot.log"
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            RotatingFileHandler(
                str(LOG_FILE_PATH),
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
                delay=True,
            ),
        ],
    )
for _noisy in ("httpx", "httpcore", "telegram.ext.Updater"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
logger = logging.getLogger("tray_app")

import ctypes

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def prevent_windows_sleep():
    """Evita que Windows entre en modo de suspensión automática mientras el bot está en ejecución."""
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            logger.info("🛡️ Protección anti-suspensión de Windows activada (ES_SYSTEM_REQUIRED)")
        except Exception as e:
            logger.debug("No se pudo invocar SetThreadExecutionState: %s", e)


def restore_windows_sleep():
    """Restaura la política normal de energía al cerrar el bot."""
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        except Exception:
            pass

from core.tray_icon import BotTrayIcon
from core.log_viewer import LogViewer
from main import BotEngine

PORT_LOCK = 29170


class TrayApplication:
    """Orquestador de la aplicación en segundo plano."""

    def __init__(self, start_visible: bool = False):
        self.start_visible = start_visible
        self._server_sock: Optional[socket.socket] = None
        self._is_running = True

        # Tkinter Root
        self.root = tk.Tk()
        self.root.withdraw()  # Iniciar oculto por defecto

        # Engine & Asyncio Loop
        self.engine = BotEngine()
        self.engine_loop: Optional[asyncio.AbstractEventLoop] = None
        self.engine_thread: Optional[threading.Thread] = None

        # Log Viewer GUI
        self.log_viewer = LogViewer(
            root=self.root,
            on_turn_on=self.request_turn_on,
            on_turn_off=self.request_turn_off,
            is_paused=True,
            log_file_path=str(LOG_FILE_PATH),
        )

        # Tray Icon (pystray)
        self.tray = BotTrayIcon(
            on_show_logs=self.show_logs,
            on_turn_on=self.request_turn_on,
            on_turn_off=self.request_turn_off,
            on_quit=self.shutdown,
            is_paused=True,
        )

        # Vincular callbacks de cambio de estado del motor (Telegram -> Tray/GUI)
        self.engine.add_state_change_callback(self._on_engine_state_changed)

    def _on_engine_state_changed(self, is_paused: bool):
        """Se ejecuta cuando el estado cambia desde Telegram o internamente."""
        # Actualizar bandeja (hilo seguro para pystray)
        self.tray.update_status(is_paused)
        # Actualizar GUI de Tkinter (enviar al hilo principal)
        try:
            self.root.after(0, lambda: self.log_viewer.update_status(is_paused))
        except Exception:
            pass

    def show_logs(self):
        """Muestra la ventana de logs (llamable desde cualquier hilo)."""
        try:
            self.root.after(0, self.log_viewer.show)
        except Exception as e:
            logger.debug("Error mostrando visor de logs: %s", e)

    def request_turn_on(self):
        """Solicita encender el bot en el hilo asyncio."""
        if self.engine_loop and self.engine_loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(self.engine.turn_on(), self.engine_loop)
            fut.add_done_callback(lambda f: f.exception() and logger.error("Error en turn_on(): %s", f.exception()))

    def request_turn_off(self):
        """Solicita apagar el bot en el hilo asyncio."""
        if self.engine_loop and self.engine_loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(self.engine.turn_off(), self.engine_loop)
            fut.add_done_callback(lambda f: f.exception() and logger.error("Error en turn_off(): %s", f.exception()))

    def _start_socket_listener(self):
        """Escucha comandos en localhost:29170 para comunicación entre procesos."""
        def listener():
            while self._is_running and self._server_sock:
                try:
                    conn, _ = self._server_sock.accept()
                except Exception:
                    break
                try:
                    conn.settimeout(2.0)
                    data = conn.recv(1024).decode("utf-8", errors="ignore").strip()
                    if data == "SHOW":
                        self.show_logs()
                        conn.sendall(b"OK:SHOWN\n")
                    elif data == "STATUS":
                        status = "PAUSED" if self.engine.config.is_paused else "RUNNING"
                        conn.sendall(f"OK:{status}\n".encode("utf-8"))
                    elif data in ("START", "TURN_ON", "RESUME"):
                        self.request_turn_on()
                        conn.sendall(b"OK:STARTING\n")
                    elif data in ("PAUSE", "TURN_OFF"):
                        self.request_turn_off()
                        conn.sendall(b"OK:PAUSING\n")
                    elif data == "CALIBRATE":
                        if self.engine_loop and self.engine_loop.is_running():
                            fut = asyncio.run_coroutine_threadsafe(self.engine.calibrate_all_ads(), self.engine_loop)
                            fut.add_done_callback(lambda f: f.exception() and logger.error("Error en calibrate_all_ads(): %s", f.exception()))
                            conn.sendall(b"OK:CALIBRATING\n")
                        else:
                            conn.sendall(b"ERR:NO_LOOP\n")
                    elif data == "STOP":
                        conn.sendall(b"OK:STOPPING\n")
                        try:
                            conn.close()
                        except Exception:
                            pass
                        self.shutdown()
                        break
                except Exception as e_client:
                    logger.debug("Error procesando cliente IPC: %s", e_client)
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

        t = threading.Thread(target=listener, daemon=True, name="IPCListener")
        t.start()

    def _run_engine(self):
        """Ejecuta el loop principal de BotEngine en un hilo secundario con supervisor de auto-reinicio."""
        while self._is_running:
            self.engine_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.engine_loop)

            try:
                self.engine_loop.run_until_complete(self.engine.run())
            except Exception as e:
                logger.error("Error fatal en loop de BotEngine: %s", e, exc_info=True)
                # Pausa preventiva de emergencia en Binance ante falla fatal
                try:
                    self.engine_loop.run_until_complete(self.engine.ads_manager.pause_all())
                except Exception:
                    pass
            finally:
                try:
                    self.engine_loop.run_until_complete(self.engine.shutdown())
                except Exception:
                    pass
                try:
                    self.engine_loop.close()
                except Exception:
                    pass

            if not self._is_running:
                break

            logger.warning("🔄 Supervisor: El motor se detuvo inesperadamente. Reiniciando en 15 segundos...")
            time.sleep(15)
            if self._is_running:
                self.engine = BotEngine()
                self.engine.add_state_change_callback(self._on_engine_state_changed)

    def start(self):
        """Inicia todos los componentes de la aplicación."""
        prevent_windows_sleep()

        # 1. Iniciar listener de comandos
        self._start_socket_listener()

        # 2. Iniciar motor del bot en segundo plano
        self.engine_thread = threading.Thread(
            target=self._run_engine, daemon=True, name="BotEngineThread"
        )
        self.engine_thread.start()

        # 3. Iniciar icono de bandeja
        self.tray.run_detached()

        # Si se solicitó mostrar la ventana de inmediato
        if self.start_visible:
            self.root.after(500, self.log_viewer.show)

        # 4. Ejecutar bucle de eventos Tkinter en el hilo principal
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.shutdown()
        finally:
            sys.exit(0)

    def shutdown(self):
        """Detiene de forma limpia todos los componentes."""
        if not self._is_running:
            return
        self._is_running = False
        logger.info("TrayApplication: Iniciando apagado ordenado...")

        # Restaurar política de energía de Windows
        restore_windows_sleep()

        # Detener icono de bandeja
        try:
            self.tray.stop()
        except Exception as e:
            logger.debug("Error deteniendo icono de bandeja: %s", e)

        # Notificar al motor de apagarse y esperar a que _run_engine complete shutdown()
        if self.engine_loop and self.engine_loop.is_running():
            try:
                if hasattr(self.engine, "request_stop"):
                    self.engine_loop.call_soon_threadsafe(self.engine.request_stop)
                else:
                    self.engine._running = False
                    self.engine_loop.call_soon_threadsafe(self.engine.shutdown_event.set)
            except Exception as e:
                logger.error("Error señalizando parada de BotEngine: %s", e)
        if self.engine_thread and self.engine_thread.is_alive():
            self.engine_thread.join(timeout=18.0)

        # Cerrar socket servidor
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass

        logger.info("TrayApplication: Apagado completo.")

        # Salir limpiamente de mainloop() en el hilo principal
        try:
            self.root.after(0, self.root.quit)
        except Exception:
            pass


def check_single_instance() -> Optional[socket.socket]:
    """Verifica si ya hay una instancia corriendo mediante enlace al puerto 29170."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", PORT_LOCK))
        sock.listen(5)
        return sock
    except OSError:
        # El puerto ya está ocupado: otra instancia está corriendo
        sock.close()
        return None


def main():
    sock = check_single_instance()
    if sock is None:
        # Ya hay una instancia corriendo -> Enviar comando SHOW para abrir el visor de logs
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(2.0)
            client.connect(("127.0.0.1", PORT_LOCK))
            client.sendall(b"SHOW\n")
            client.close()
            print("El bot ya está corriendo. Se ha abierto la ventana de logs.")
        except Exception as e:
            print(f"Instancia existente detectada, pero no respondió: {e}")
        sys.exit(0)

    # Iniciar la aplicación
    start_visible = "--visible" in sys.argv
    app = TrayApplication(start_visible=start_visible)
    app._server_sock = sock
    app.start()


if __name__ == "__main__":
    main()
