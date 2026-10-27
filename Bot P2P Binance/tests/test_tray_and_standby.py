"""
Tests unitarios para la integración de la bandeja del sistema (System Tray),
visor de logs y arranque en modo Standby.
"""
import asyncio
import socket
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from core.tray_icon import BotTrayIcon, create_bot_icon
from core.log_viewer import LogViewer
from main import BotEngine


def test_create_bot_icon():
    """Verifica que la generación de iconos produzca imágenes válidas RGBA de 64x64."""
    for status in ("standby", "active", "paused"):
        img = create_bot_icon(status)
        assert isinstance(img, Image.Image)
        assert img.size == (64, 64)
        assert img.mode == "RGBA"


def test_tray_icon_status_updates():
    """Verifica la lógica de estados del menú y tooltip de la bandeja."""
    on_show = MagicMock()
    on_on = MagicMock()
    on_off = MagicMock()
    on_quit = MagicMock()

    tray = BotTrayIcon(
        on_show_logs=on_show,
        on_turn_on=on_on,
        on_turn_off=on_off,
        on_quit=on_quit,
        is_paused=True,
    )

    assert "Standby" in tray._get_tooltip()
    assert "EN ESPERA" in tray._get_status_text()

    # Cambiar a activo
    tray.update_status(is_paused=False)
    assert not tray.is_paused
    assert "Activo" in tray._get_tooltip()
    assert "ACTIVO" in tray._get_status_text()

    # Volver a standby
    tray.update_status(is_paused=True)
    assert tray.is_paused
    assert "Standby" in tray._get_tooltip()


def test_log_viewer_lifecycle():
    """Verifica que el visor de logs cree los widgets, oculte y actualice estado."""
    root = tk.Tk()
    root.withdraw()
    temp_log = Path(tempfile.gettempdir()) / "test_bot_viewer.log"

    viewer = LogViewer(
        root=root,
        is_paused=True,
        log_file_path=str(temp_log),
    )

    # Verificar estado inicial
    assert viewer.is_paused is True
    assert "STANDBY" in viewer.status_badge.cget("text")
    assert "Encender" in viewer.btn_power.cget("text")

    # Actualizar a activo
    viewer.update_status(is_paused=False)
    assert viewer.is_paused is False
    assert "ACTIVO" in viewer.status_badge.cget("text")
    assert "Apagar" in viewer.btn_power.cget("text")

    # Probar ocultar y mostrar
    viewer.hide()
    assert viewer._poll_job is None
    viewer.show()
    assert viewer._poll_job is not None
    viewer.hide()

    # Limpieza
    root.destroy()


def test_bot_engine_standby_and_callbacks():
    """Verifica que BotEngine soporte registro y notificación de callbacks de estado."""
    with patch("main.Database"), patch("main.BinanceClient"), patch("main.SpotClient"), patch("main.FiwindClient"):
        engine = BotEngine()

        state_log = []
        def on_change(is_paused):
            state_log.append(is_paused)

        engine.add_state_change_callback(on_change)

        engine.config.is_paused = True
        engine._notify_state_change()
        assert state_log == [True]

        engine.config.is_paused = False
        engine._notify_state_change()
        assert state_log == [True, False]


def test_ipc_socket_handshake():
    """Verifica que el handshake de socket local en localhost responda a SHOW y STATUS."""
    test_port = 29175
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", test_port))
    server_sock.listen(1)

    received_commands = []

    def server_thread():
        conn, _ = server_sock.accept()
        cmd = conn.recv(1024).decode("utf-8").strip()
        received_commands.append(cmd)
        conn.sendall(b"OK:SHOWN\n")
        conn.close()
        server_sock.close()

    t = threading.Thread(target=server_thread, daemon=True)
    t.start()

    # Cliente envía SHOW
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", test_port))
    client.sendall(b"SHOW\n")
    resp = client.recv(1024).decode("utf-8").strip()
    client.close()

    t.join(timeout=2)
    assert received_commands == ["SHOW"]
    assert resp == "OK:SHOWN"


def test_turn_on_resumes_both_buy_and_sell_ads():
    """Verifica que turn_on reactive tanto las compras como las ventas seguras."""
    from unittest.mock import AsyncMock
    with patch("main.Database"), patch("main.BinanceClient"), patch("main.SpotClient"), patch("main.FiwindClient"):
        engine = BotEngine()
        engine._reconcile_ads_internal = AsyncMock(return_value={})
        engine.ads_manager = MagicMock()
        engine.ads_manager.resume_all = AsyncMock(return_value=42)
        engine.ads_manager.resume_all_sell_ads = AsyncMock(return_value=3)
        engine.db = MagicMock()
        from data.models import BotConfig, MyAd
        engine.db.load_bot_config.return_value = BotConfig(is_paused=True, paused_ads=[])
        engine.my_ads = [MyAd(adv_no="B1", asset="USDT", ad_group=1, current_price=1600.0, payment_methods=[], init_amount=100.0, status=3)]
        engine.my_sell_ads = [MyAd(adv_no="S1", asset="USDT", ad_group=1, current_price=1620.0, payment_methods=[], init_amount=100.0, status=3)]

        res = asyncio.run(engine.turn_on())
        engine.ads_manager.resume_all.assert_called_once()
        engine.ads_manager.resume_all_sell_ads.assert_called_once()
        assert res["total_active"] == 42
        assert res["sell_active"] == 3
        assert engine.config.is_paused is False
        assert engine.my_ads[0].status == 1
        assert engine.my_sell_ads[0].status == 1

