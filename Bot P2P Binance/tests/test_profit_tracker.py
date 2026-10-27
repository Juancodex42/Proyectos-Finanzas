"""
Tests unitarios para el módulo de cálculo de ganancias (ProfitTracker) e integración con Telegram.
Verifica:
1. Conversión multiactivo a equivalente USDT mediante tc_implicito.
2. Evitación de falsos saldos negativos a mitad de ciclo (medio pesos, medio USDT).
3. Determinación de precio de venta proyectado (anuncios Binance, SellAdvisor, benchmarks).
4. Formateo idéntico del reporte diario con la adición de la línea de ganancia.
5. Formateo de la tarjeta interactiva de ganancias.
6. Presencia del botón e interacción en TelegramBot.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from core.profit_tracker import ProfitTracker, ProfitReport
from telegram_bot.formatters import format_daily_report, format_profit_report
from telegram_bot.bot import TelegramBot


class TestProfitTracker(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_client = AsyncMock()
        self.tracker = ProfitTracker(self.mock_db, self.mock_client)

    async def test_mid_cycle_positive_profit_avoiding_negative_cashflow(self):
        """
        Verifica el caso planteado por el usuario:
        Se compraron $3.27M ARS y se vendieron solo $2.38M ARS (el cash-flow es -$887k ARS),
        pero como se retiene inventario en USDT que se proyecta vender al precio publicado,
        la ganancia total resultante es POSITIVA (+~$21k ARS).
        """
        # Mock de compras (5 órdenes: USDT, BTC, SOL, USDC)
        mock_buys = [
            {
                "order_no": "1", "asset": "USDC", "amount_crypto": 700.0,
                "amount_ars": 1122107.0, "price": 1603.01, "tc_implicito": 1601.26,
                "detected_at": "2026-10-13 00:23:06"
            },
            {
                "order_no": "2", "asset": "USDT", "amount_crypto": 779.80,
                "amount_ars": 1247180.92, "price": 1599.36, "tc_implicito": 1599.36,
                "detected_at": "2026-10-13 13:05:32"
            },
            {
                "order_no": "3", "asset": "SOL", "amount_crypto": 0.058534,
                "amount_ars": 10000.0, "price": 170840.41, "tc_implicito": 1600.53,
                "detected_at": "2026-10-13 13:56:50"
            },
            {
                "order_no": "4", "asset": "BTC", "amount_crypto": 0.005899,
                "amount_ars": 788384.03, "price": 133650009.24, "tc_implicito": 1598.10,
                "detected_at": "2026-10-13 14:33:25"
            },
            {
                "order_no": "5", "asset": "BTC", "amount_crypto": 0.000800,
                "amount_ars": 107010.94, "price": 133765347.07, "tc_implicito": 1598.32,
                "detected_at": "2026-10-13 14:51:49"
            },
        ]

        # Mock de ventas (6 órdenes de USDT totalizando 1,482.16 USDT por $2,386,944 ARS)
        mock_sells = [
            {"order_no": "10", "asset": "USDT", "amount_crypto": 279.24, "amount_ars": 450000.0, "price": 1611.52, "tc_implicito": 1611.52, "detected_at": "2026-10-13 00:30:43"},
            {"order_no": "11", "asset": "USDT", "amount_crypto": 459.19, "amount_ars": 740000.0, "price": 1611.53, "tc_implicito": 1611.53, "detected_at": "2026-10-13 00:36:47"},
            {"order_no": "12", "asset": "USDT", "amount_crypto": 182.07, "amount_ars": 293000.0, "price": 1609.27, "tc_implicito": 1609.27, "detected_at": "2026-10-13 13:59:50"},
            {"order_no": "13", "asset": "USDT", "amount_crypto": 64.59, "amount_ars": 103944.0, "price": 1609.29, "tc_implicito": 1609.29, "detected_at": "2026-10-13 14:02:59"},
            {"order_no": "14", "asset": "USDT", "amount_crypto": 310.65, "amount_ars": 500000.0, "price": 1609.53, "tc_implicito": 1609.53, "detected_at": "2026-10-13 14:10:34"},
            {"order_no": "15", "asset": "USDT", "amount_crypto": 186.42, "amount_ars": 300000.0, "price": 1609.27, "tc_implicito": 1609.27, "detected_at": "2026-10-13 15:00:20"},
        ]

        mock_conn = MagicMock()
        self.mock_db._lock = MagicMock()
        self.mock_db.connect.return_value = mock_conn

        # Cursor side effect: first buys, second sells
        mock_cursor_buys = MagicMock()
        mock_cursor_buys.fetchall.return_value = mock_buys
        mock_cursor_sells = MagicMock()
        mock_cursor_sells.fetchall.return_value = mock_sells

        mock_conn.execute.side_effect = [mock_cursor_buys, mock_cursor_sells]

        # Mock de Binance Client list_my_ads con 3 anuncios sintéticos de prueba
        self.mock_client.list_my_ads.return_value = {
            "total": 3,
            "data": [
                {"advNo": "10000000000000008480", "asset": "USDT", "price": "1609.70", "advStatus": 1},
                {"advNo": "10000000000000005104", "asset": "USDT", "price": "1609.20", "advStatus": 1},
                {"advNo": "10000000000000009632", "asset": "USDT", "price": "1609.50", "advStatus": 1},
            ]
        }

        report = await self.tracker.calculate_profit("2026-10-13")

        # Verificaciones clave
        self.assertGreater(report.total_profit_ars, 0.0, "La ganancia total nunca debe ser negativa")
        self.assertAlmostEqual(report.total_profit_ars, 21348.0, delta=100.0)
        self.assertGreater(report.realized_profit_ars, 15000.0)
        self.assertGreater(report.projected_profit_ars, 5000.0)
        self.assertAlmostEqual(report.remaining_stock_usdt, 564.9, delta=1.0)
        self.assertEqual(report.projected_sell_price, 1609.20)
        self.assertTrue(report.is_mixed_state)
        self.assertIn("5104", report.projection_source)

    async def test_only_buys_morning_state(self):
        """Si en la mañana solo hubo compras, la ganancia realizada es 0 y la proyectada es positiva."""
        mock_buys = [
            {"order_no": "1", "asset": "USDT", "amount_crypto": 500.0, "amount_ars": 800000.0, "price": 1600.0, "tc_implicito": 1600.0, "detected_at": "2026-10-13 09:00:00"}
        ]
        mock_sells = []

        mock_conn = MagicMock()
        self.mock_db._lock = MagicMock()
        self.mock_db.connect.return_value = mock_conn

        mock_cursor_b = MagicMock()
        mock_cursor_b.fetchall.return_value = mock_buys
        mock_cursor_s = MagicMock()
        mock_cursor_s.fetchall.return_value = mock_sells
        mock_conn.execute.side_effect = [mock_cursor_b, mock_cursor_s]

        self.mock_client.list_my_ads.return_value = {
            "data": [{"advNo": "9999", "asset": "USDT", "price": "1610.00", "advStatus": 1}]
        }

        report = await self.tracker.calculate_profit("2026-10-13")

        self.assertEqual(report.realized_profit_ars, 0.0)
        # 500 USDT * ($1610 - $1600) = $5,000 ARS
        self.assertEqual(report.projected_profit_ars, 5000.0)
        self.assertEqual(report.total_profit_ars, 5000.0)
        self.assertEqual(report.remaining_stock_usdt, 500.0)

    async def test_fallback_when_no_active_sell_ads(self):
        """Si el usuario no tiene anuncios activos en Binance, SellAdvisor o el Benchmark proveen el precio."""
        self.mock_client.list_my_ads.return_value = {"data": []}

        # Mock de DB get_latest_benchmarks
        mock_bm = MagicMock()
        mock_bm.avg_top_n_price = 1608.50
        self.mock_db.get_latest_benchmarks.return_value = {"MercadoPagoNew": mock_bm}

        price, source = await self.tracker.get_published_sell_price()
        self.assertGreater(price, 0.0)
        self.assertTrue("Mercado" in source or "SellAdvisor" in source)


class TestProfitFormattersAndTelegram(unittest.TestCase):

    def test_format_daily_report_keeps_existing_format_and_adds_profit_line(self):
        """Verifica que format_daily_report mantenga exactamente todas las líneas históricas y agregue la ganancia."""
        stats = {
            "date": "2026-10-13",
            "repositions": 142,
            "buy_orders": 5,
            "buy_volume_ars": 3274683.0,
            "sell_orders": 6,
            "sell_volume_ars": 2386944.0,
            "balance_ars": 304261.0,
            "daily_profit_ars": 21348.0,
        }
        text = format_daily_report(stats)

        # Líneas históricas intactas
        self.assertIn("📊 *Reporte Diario*", text)
        self.assertIn("📅 *Fecha:* `2026-10-13`", text)
        self.assertIn("🔄 Reposicionamientos: 142", text)
        self.assertIn("💰 Compras: 5 ($3,274,683 ARS)", text)
        self.assertIn("💸 Ventas: 6 ($2,386,944 ARS)", text)
        self.assertIn("💵 Balance: $304,261 ARS", text)

        # Línea de ganancia anexada
        self.assertIn("📈 *Ganancia del día:* $21,348 ARS", text)

    def test_format_profit_report_card(self):
        """Verifica que la tarjeta de format_profit_report contenga las métricas completas."""
        rep = ProfitReport(
            date="2026-10-13",
            total_profit_ars=21348.0,
            realized_profit_ars=15968.0,
            projected_profit_ars=5380.0,
            total_buy_ars=3274683.0,
            total_buy_usdt=2047.10,
            avg_buy_tc=1599.68,
            total_sell_ars=2386944.0,
            total_sell_usdt=1482.16,
            avg_sell_tc=1610.45,
            remaining_stock_usdt=564.94,
            projected_sell_price=1609.20,
            projection_source="Anuncio publicado #5104 ($1,609.20)",
            buy_orders_count=5,
            sell_orders_count=6,
            is_mixed_state=True,
        )
        card = format_profit_report(rep)

        self.assertIn("REPORTE DE GANANCIAS EN VIVO", card)
        self.assertIn("+$21,348 ARS", card)
        self.assertIn("+$15,968 ARS", card)
        self.assertIn("+$5,380 ARS", card)
        self.assertIn("564.94 USDT", card)
        self.assertIn("1,609.20", card)

    def test_telegram_bot_inline_keyboard_has_profit_button(self):
        """Verifica que la botonera de Telegram incluya el botón '📈 Ganancias' con callback 'bot_profit'."""
        mock_db = MagicMock()
        mock_config = MagicMock()
        mock_config.is_paused = False
        mock_db.load_bot_config.return_value = mock_config

        bot = TelegramBot(mock_db)
        panel = bot.get_inline_panel()

        button_texts = []
        callback_datas = []
        for row in panel.inline_keyboard:
            for btn in row:
                button_texts.append(btn.text)
                callback_datas.append(btn.callback_data)

        self.assertIn("📈 Ganancias", button_texts)
        self.assertIn("bot_profit", callback_datas)


if __name__ == "__main__":
    unittest.main()
