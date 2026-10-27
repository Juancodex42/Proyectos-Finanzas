"""
Suite de Pruebas Unitarias para el WebSocket de Simulación (/ws/simulacion).
Valida que ConnectionManager difunda mensajes de forma concurrente sin bloqueos ni deadlocks.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock
from src.api.websocket_sim import ConnectionManager


@pytest.mark.asyncio
async def test_connection_manager_broadcast_resilient():
    """Valida que broadcast envíe mensajes a clientes sanos y descarte clientes lentos/caídos sin bloquear."""
    manager = ConnectionManager()

    # Cliente 1: Socket sano
    ws_ok = AsyncMock()
    ws_ok.send_text = AsyncMock()

    # Cliente 2: Socket muerto que arroja excepción
    ws_fail = AsyncMock()
    ws_fail.send_text = AsyncMock(side_effect=Exception("Connection reset"))

    # Cliente 3: Socket colgado que supera el timeout
    ws_slow = AsyncMock()
    async def slow_send(_text):
        await asyncio.sleep(5.0)
    ws_slow.send_text = slow_send

    # Registrar conexiones simuladas
    manager.active_connections.add(ws_ok)
    manager.active_connections.add(ws_fail)
    manager.active_connections.add(ws_slow)

    # El broadcast debe completarse rápidamente gracias a los timeouts concurrentes
    await asyncio.wait_for(manager.broadcast({"tipo": "TEST"}), timeout=3.5)

    # ws_ok debe haber recibido el mensaje
    ws_ok.send_text.assert_called_once()

    # Los sockets caídos y lentos deben haber sido purgados de active_connections
    assert ws_fail not in manager.active_connections
    assert ws_slow not in manager.active_connections
    assert ws_ok in manager.active_connections
