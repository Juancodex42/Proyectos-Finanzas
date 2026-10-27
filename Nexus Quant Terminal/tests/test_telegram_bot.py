"""
tests/test_telegram_bot.py
Tests unitarios y de integración para el bot de control remoto de Telegram.
Verifica seguridad por whitelist, enrutamiento de comandos, botones inline,
generación de gráficos en memoria y enlaces con DualBotManager.
"""

import unittest
from unittest.mock import patch, MagicMock
import io
import pandas as pd
from engine.execution.telegram_bot import TelegramBotClient
from engine.execution.dual_bot_manager import DualBotManager


class TestTelegramBot(unittest.TestCase):

    def setUp(self):
        self.manager = DualBotManager()
        self.client = TelegramBotClient(
            bot_token="123456:TEST_TOKEN",
            allowed_chat_ids=[999111],
            manager=self.manager
        )

    def test_configuration_validation(self):
        """Verifica que el bot reconozca si está correctamente configurado."""
        self.assertTrue(self.client.is_configured())

        empty_client = TelegramBotClient(bot_token="", allowed_chat_ids=[])
        self.assertFalse(empty_client.is_configured())

    @patch("engine.execution.telegram_bot.requests.post")
    def test_send_message_calls_telegram_api(self, mock_post):
        """Verifica el envío de mensajes con formato Markdown y teclado inline."""
        mock_post.return_value.status_code = 200

        ok = self.client.send_message(
            chat_id=999111,
            text="Hola Test",
            reply_markup={"inline_keyboard": []}
        )
        self.assertTrue(ok)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("sendMessage", args[0])
        self.assertEqual(kwargs["json"]["chat_id"], 999111)

    @patch("engine.execution.telegram_bot.requests.post")
    def test_whitelist_security_blocks_unauthorized_users(self, mock_post):
        """Verifica que cualquier mensaje de un chat_id no autorizado sea rechazado inmediatamente."""
        mock_post.return_value.status_code = 200

        unauthorized_update = {
            "update_id": 1,
            "message": {
                "chat": {"id": 666999},  # NO está en allowed_chat_ids
                "text": "/status"
            }
        }

        self.client._process_update(unauthorized_update)

        # Debe haber enviado el mensaje de Acceso Denegado
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("sendMessage", args[0])
        self.assertIn("Acceso Denegado", kwargs["json"]["text"])

    @patch("engine.execution.telegram_bot.requests.post")
    def test_command_status_and_menu(self, mock_post):
        """Verifica que los comandos /status y /menu respondan a usuarios autorizados."""
        mock_post.return_value.status_code = 200

        authorized_update = {
            "update_id": 2,
            "message": {
                "chat": {"id": 999111},
                "text": "/status"
            }
        }

        self.client._process_update(authorized_update)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("ESTADO GENERAL DEL SISTEMA", kwargs["json"]["text"])

    @patch("engine.execution.telegram_bot.requests.post")
    def test_callback_query_toggle_bots(self, mock_post):
        """Verifica que pulsar los botones inline ejecute las acciones en el DualBotManager."""
        mock_post.return_value.status_code = 200

        callback_update = {
            "update_id": 3,
            "callback_query": {
                "id": "cb_123",
                "from": {"id": 999111},
                "data": "TOGGLE_BOT1_RUN"
            }
        }

        self.client._process_update(callback_update)
        self.assertEqual(self.manager.bot1["state"], "RUNNING")

        # Botón para apagar
        callback_stop = {
            "update_id": 4,
            "callback_query": {
                "id": "cb_124",
                "from": {"id": 999111},
                "data": "TOGGLE_BOT1_STOP"
            }
        }
        self.client._process_update(callback_stop)
        self.assertEqual(self.manager.bot1["state"], "STOPPED")

    @patch("engine.execution.telegram_bot.requests.post")
    def test_callback_query_panic_kill(self, mock_post):
        """Verifica la ejecución del Botón de Pánico desde el celular."""
        mock_post.return_value.status_code = 200

        callback_panic = {
            "update_id": 5,
            "callback_query": {
                "id": "cb_125",
                "from": {"id": 999111},
                "data": "PANIC_EXECUTE_NOW"
            }
        }

        self.client._process_update(callback_panic)
        self.assertEqual(self.manager.bot1["state"], "STOPPED")
        self.assertEqual(self.manager.bot2["state"], "STOPPED")

    def test_candlestick_chart_png_generation(self):
        """Verifica que el renderizador de velas genere un archivo PNG válido en memoria."""
        dates = pd.date_range("2026-01-01", periods=30, freq="1h")
        df = pd.DataFrame({
            "open": [70000 + i * 10 for i in range(30)],
            "high": [70050 + i * 10 for i in range(30)],
            "low": [69950 + i * 10 for i in range(30)],
            "close": [70020 + i * 10 for i in range(30)],
            "volume": [100.0] * 30
        }, index=dates)

        trade = {
            "symbol": "BTC/USDT",
            "direction": "BUY",
            "entry_price": 70100.0,
            "atr": 150.0,
            "breakeven_triggered": True
        }

        buf = TelegramBotClient.render_candlestick_png(df, trade, "BTC/USDT")
        self.assertIsInstance(buf, io.BytesIO)
        content = buf.getvalue()
        # Verificar cabecera mágica PNG (\x89PNG\r\n\x1a\n)
        self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_equity_chart_png_generation(self):
        """Verifica que el renderizador de equidad genere un archivo PNG válido en memoria."""
        equity_hist = [
            {"combined_equity": 1000.0},
            {"combined_equity": 1025.0},
            {"combined_equity": 1080.0},
            {"combined_equity": 1150.0}
        ]

        buf = TelegramBotClient.render_equity_png(equity_hist)
        self.assertIsInstance(buf, io.BytesIO)
        content = buf.getvalue()
        self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))

    @patch("engine.execution.telegram_bot.requests.post")
    def test_manager_telegram_credentials_integration(self, mock_post):
        """Verifica la vinculación de credenciales desde DualBotManager."""
        mock_post.return_value.status_code = 200

        res = self.manager.set_telegram_credentials(
            bot_token="987654:XYZ_TOKEN",
            allowed_chat_ids=[999111]
        )
        self.assertTrue(res["success"])
        self.assertIsNotNone(self.manager.telegram_bot)
        self.assertTrue(self.manager.telegram_bot.is_configured())

    @patch("engine.execution.telegram_bot.requests.post")
    def test_bot2_menu_and_risk_callbacks(self, mock_post):
        """Verifica la navegación y configuración de riesgo de Bot 2 desde Telegram."""
        mock_post.return_value.status_code = 200

        # 1. Abrir menú Bot 2
        update_menu = {
            "update_id": 10,
            "callback_query": {
                "id": "cb_b2_menu",
                "from": {"id": 999111},
                "data": "MENU_BOT2"
            }
        }
        self.client._process_update(update_menu)
        last_json = mock_post.call_args[1]["json"]
        self.assertIn("GESTIÓN MACRO BOT 2", last_json["text"])

        # 2. Ajustar riesgo a 2.0%
        update_risk = {
            "update_id": 11,
            "callback_query": {
                "id": "cb_b2_risk",
                "from": {"id": 999111},
                "data": "BOT2_SET_RISK_2.0"
            }
        }
        self.client._process_update(update_risk)
        self.assertEqual(self.manager.bot2["risk_per_trade_pct"], 2.0)


if __name__ == "__main__":
    unittest.main()

