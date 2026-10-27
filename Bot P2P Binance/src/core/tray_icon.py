"""
Módulo de icono en la bandeja del sistema (System Tray) con pystray y Pillow.
Proporciona el icono en la barra de tareas ("iconos ocultos" ^), indicadores visuales
de estado (Standby / Activo) y menú interactivo de control.
"""
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw
import pystray

logger = logging.getLogger("tray_icon")


def create_bot_icon(status: str = "standby") -> Image.Image:
    """
    Genera un icono nítido de terminal / consola de 64x64 píxeles con indicador de estado.
    - 'standby': Indicador ámbar/amarillo (en espera de Telegram)
    - 'active': Indicador verde brillante (operando activamente)
    - 'paused': Indicador rojo (pausado)
    """
    size = 64
    img = Image.new("RGBA", (size, size), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Marco de ventana de consola oscura
    draw.rounded_rectangle(
        (2, 2, size - 3, size - 3),
        radius=12,
        fill=(22, 24, 29),
        outline=(55, 60, 72),
        width=2,
    )

    # Barra superior de la consola
    draw.line((2, 17, size - 3, 17), fill=(40, 44, 52), width=1)

    # Puntos de ventana estilo macOS / terminal moderno
    draw.ellipse((8, 7, 13, 12), fill=(239, 68, 68))    # Rojo
    draw.ellipse((17, 7, 22, 12), fill=(245, 158, 11))  # Amarillo
    draw.ellipse((26, 7, 31, 12), fill=(34, 197, 94))   # Verde

    # Prompt de consola '>_' en oro Binance (#F3BA2F) y blanco
    draw.line((14, 27, 26, 36), fill=(243, 186, 47), width=3)
    draw.line((26, 36, 14, 45), fill=(243, 186, 47), width=3)
    draw.line((32, 45, 45, 45), fill=(255, 255, 255), width=3)

    # Indicador de estado en la esquina inferior derecha
    badge_colors = {
        "active": (34, 197, 94),     # Verde
        "standby": (245, 158, 11),   # Ámbar / Amarillo
        "paused": (239, 68, 68),     # Rojo
    }
    badge_color = badge_colors.get(status, (245, 158, 11))

    # Anillo exterior oscuro para resaltar el estado
    draw.ellipse((42, 42, 60, 60), fill=(18, 18, 22), outline=(45, 48, 56), width=1)
    # Punto luminoso de estado
    draw.ellipse((46, 46, 56, 56), fill=badge_color)

    return img


class BotTrayIcon:
    """Administra el icono de la bandeja del sistema de Windows."""

    def __init__(
        self,
        on_show_logs: Callable[[], None],
        on_turn_on: Optional[Callable[[], None]] = None,
        on_turn_off: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
        is_paused: bool = True,
    ):
        self.on_show_logs = on_show_logs
        self.on_turn_on = on_turn_on
        self.on_turn_off = on_turn_off
        self.on_quit = on_quit
        self.is_paused = is_paused

        self._icon: Optional[pystray.Icon] = None
        self._build_icon()

    def _get_status_text(self) -> str:
        return "🟡 Estado: EN ESPERA (Standby)" if self.is_paused else "🟢 Estado: ACTIVO (Operando)"

    def _get_tooltip(self) -> str:
        mode = "Standby (En espera)" if self.is_paused else "Activo"
        return f"Bot P2P Binance ARS — {mode}"

    def _build_menu(self) -> pystray.Menu:
        """Construye el menú contextual del icono de la bandeja."""
        return pystray.Menu(
            pystray.MenuItem(
                "🖥️ Ver Logs en vivo",
                lambda icon, item: self.on_show_logs(),
                default=True,  # Acción por defecto al hacer doble clic o clic principal
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                self._get_status_text(),
                lambda icon, item: None,
                enabled=False,  # Informativo
            ),
            pystray.MenuItem(
                "🟢 Encender Bot",
                lambda icon, item: self._handle_turn_on(),
                visible=lambda item: self.is_paused,
            ),
            pystray.MenuItem(
                "🔴 Apagar Bot",
                lambda icon, item: self._handle_turn_off(),
                visible=lambda item: not self.is_paused,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "📄 Abrir archivo bot.log",
                lambda icon, item: self._open_log_file(),
            ),
            pystray.MenuItem(
                "📁 Abrir carpeta del Bot",
                lambda icon, item: self._open_project_folder(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "❌ Cerrar y Detener Bot",
                lambda icon, item: self._handle_quit(),
            ),
        )

    def _build_icon(self):
        status = "standby" if self.is_paused else "active"
        icon_img = create_bot_icon(status)
        menu = self._build_menu()
        self._icon = pystray.Icon(
            "BotP2PBinance",
            icon_img,
            self._get_tooltip(),
            menu,
        )

    def update_status(self, is_paused: bool):
        """Actualiza el estado del bot (refleja cambios de Telegram o de la GUI)."""
        self.is_paused = is_paused
        status = "standby" if is_paused else "active"
        if self._icon:
            try:
                self._icon.icon = create_bot_icon(status)
                self._icon.title = self._get_tooltip()
                self._icon.menu = self._build_menu()
            except Exception as e:
                logger.debug("Error actualizando icono de bandeja: %s", e)

    def notify(self, title: str, message: str):
        """Muestra una notificación en la bandeja de Windows."""
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception as e:
                logger.debug("No se pudo emitir notificación de bandeja: %s", e)

    def _handle_turn_on(self):
        if self.on_turn_on:
            self.on_turn_on()

    def _handle_turn_off(self):
        if self.on_turn_off:
            self.on_turn_off()

    def _handle_quit(self):
        if self.on_quit:
            # Ejecutar en hilo desacoplado para que el dispatcher de Windows/pystray retorne limpiamente
            threading.Thread(target=self.on_quit, name="TrayShutdownThread", daemon=True).start()
        else:
            self.stop()

    def _open_log_file(self):
        log_path = Path(__file__).resolve().parent.parent / "logs" / "bot.log"
        if not log_path.exists():
            log_path = Path(__file__).resolve().parent.parent / "bot.log"
        if log_path.exists() and sys.platform == "win32":
            try:
                os.startfile(str(log_path))
            except Exception as e:
                logger.error("Error abriendo bot.log: %s", e)

    def _open_project_folder(self):
        folder_path = Path(__file__).resolve().parent.parent
        if sys.platform == "win32":
            try:
                os.startfile(str(folder_path))
            except Exception as e:
                logger.error("Error abriendo carpeta: %s", e)

    def run_detached(self):
        """Ejecuta el icono de la bandeja en un hilo secundario desacoplado."""
        if self._icon:
            self._icon.run_detached()
            logger.info("Icono de bandeja del sistema iniciado.")

    def stop(self):
        """Detiene y remueve el icono de la bandeja del sistema."""
        if self._icon:
            try:
                self._icon.stop()
            except Exception as e:
                logger.debug("Error deteniendo icono de bandeja: %s", e)
            self._icon = None
            logger.info("Icono de bandeja removido.")
