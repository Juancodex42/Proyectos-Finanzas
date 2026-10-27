"""
Tests unitarios exhaustivos para el Asesor de Ventas P2P (SellAdvisor) y su integración en Telegram.
Verifica:
1. Integridad del Aislamiento (Air-Gap) y 100% Solo Lectura.
2. Cálculos matemáticos de precios sugeridos, anclas, podio y margen de ganancia.
3. Fallbacks de seguridad ante ausencia de datos en benchmarks.
4. Formateo amigable para Telegram.
5. Presencia del botón y handlers en TelegramBot.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from core.sell_advisor import SellAdvisor, ClusterAdvice, SELL_CLUSTERS_CONFIG
from data.models import Benchmark
from telegram_bot.formatters import format_sell_advice_report
from telegram_bot.bot import TelegramBot


class TestSellAdvisor(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.advisor = SellAdvisor(self.mock_db)

    def test_air_gap_integrity(self):
        """Verifica que SellAdvisor no contenga ni llame métodos de escritura en Binance."""
        forbidden_methods = [
            "update_ad", "create_ad", "pause_ad", "delete_ad",
            "set_price", "place_order", "client"
        ]
        for method in forbidden_methods:
            self.assertFalse(hasattr(self.advisor, method), f"SellAdvisor violó el air-gap con {method}")

        import core.sell_advisor as sa_mod
        # Asegurarse de que no importa BinanceClient ni Repositioner
        self.assertNotIn("BinanceClient", dir(sa_mod))
        self.assertNotIn("Repositioner", dir(sa_mod))
        self.assertNotIn("AdsManager", dir(sa_mod))

    def test_get_sell_advice_with_real_benchmarks(self):
        """Verifica cálculo preciso de precios, spreads y ganancias extras con benchmarks simulados."""
        benchmarks = {
            "MercadoPagoNew": Benchmark(
                payment_method="MercadoPagoNew",
                avg_top_n_price=1585.50,
                individual_prices=[1585.50, 1585.80, 1586.00, 1586.20],
                timestamp=datetime.now(),
            ),
            "SantanderArgentina": Benchmark(
                payment_method="SantanderArgentina",
                avg_top_n_price=1591.00,
                individual_prices=[1591.00, 1592.00, 1593.00, 1594.00],
                timestamp=datetime.now(),
            ),
            "personalpay": Benchmark(
                payment_method="personalpay",
                avg_top_n_price=1593.20,
                individual_prices=[1593.20, 1594.50, 1595.50, 1597.00],
                timestamp=datetime.now(),
            ),
        }

        advice = self.advisor.get_sell_advice(ticket_ref_crypto=350.0, benchmarks=benchmarks)
        self.assertEqual(len(advice), 3)

        # Cluster 1: Billeteras
        c1 = advice[0]
        self.assertEqual(c1.cluster_id, 1)
        self.assertEqual(c1.anchor_method, "MercadoPagoNew")
        self.assertEqual(c1.top1_price, 1585.50)
        self.assertEqual(c1.suggested_price, 1585.85)  # 1585.50 + 0.35
        self.assertEqual(c1.extra_profit_per_usdt, 0.0)
        self.assertEqual(c1.suggested_min_ars, 15000.0)
        self.assertTrue(c1.is_valid_data)

        # Cluster 2: Bancos Tradicionales
        c2 = advice[1]
        self.assertEqual(c2.cluster_id, 2)
        self.assertEqual(c2.anchor_method, "SantanderArgentina")
        self.assertEqual(c2.top1_price, 1591.00)
        self.assertEqual(c2.suggested_price, 1592.80)  # 1591.00 + 1.80
        # extra_profit = 1592.80 - 1585.85 = 6.95
        self.assertAlmostEqual(c2.extra_profit_per_usdt, 6.95, places=2)
        # ticket = round(6.95 * 350) = 2432 ARS
        self.assertEqual(c2.estimated_extra_ticket_ars, 2432.0)
        self.assertEqual(c2.suggested_min_ars, 80000.0)
        self.assertTrue(c2.is_valid_data)

        # Cluster 3: Fintechs Secundarias
        c3 = advice[2]
        self.assertEqual(c3.cluster_id, 3)
        self.assertEqual(c3.anchor_method, "personalpay")
        self.assertEqual(c3.top1_price, 1593.20)
        self.assertEqual(c3.suggested_price, 1595.40)  # 1593.20 + 2.20
        # extra_profit = 1595.40 - 1585.85 = 9.55
        self.assertAlmostEqual(c3.extra_profit_per_usdt, 9.55, places=2)
        # ticket = round(9.55 * 350) = 3343 ARS
        self.assertEqual(c3.estimated_extra_ticket_ars, 3343.0)
        self.assertEqual(c3.suggested_min_ars, 30000.0)
        self.assertTrue(c3.is_valid_data)

    def test_fallback_when_benchmarks_empty(self):
        """Verifica que ante base de datos vacía o sin benchmarks, no falle y provea valores por defecto seguros."""
        self.mock_db.get_latest_benchmarks.return_value = {}
        advice = self.advisor.get_sell_advice(benchmarks={})

        self.assertEqual(len(advice), 3)
        for c in advice:
            self.assertFalse(c.is_valid_data)
            self.assertGreater(c.suggested_price, 0)
            self.assertGreater(c.suggested_min_ars, 0)

    def test_alternative_anchor_selection(self):
        """Verifica que si el ancla principal no tiene datos, use un método alternativo del mismo cluster."""
        benchmarks = {
            "MercadoPagoNew": Benchmark(
                payment_method="MercadoPagoNew",
                avg_top_n_price=1580.0, individual_prices=[1580.0], timestamp=datetime.now()
            ),
            # SantanderArgentina ausente, pero bancogalicia presente en Cluster 2
            "bancogalicia": Benchmark(
                payment_method="bancogalicia",
                avg_top_n_price=1590.0, individual_prices=[1590.0, 1592.0], timestamp=datetime.now()
            ),
        }

        advice = self.advisor.get_sell_advice(benchmarks=benchmarks)
        c2 = advice[1]
        self.assertEqual(c2.anchor_method, "bancogalicia")
        self.assertEqual(c2.top1_price, 1590.0)
        # Con Book-Aware: P1=1590.0, P2=1592.0 -> se expande a P2 - 0.01 = 1591.99 (Puesto #2)
        self.assertEqual(c2.suggested_price, 1591.99)
        self.assertTrue(c2.is_valid_data)

    def test_book_aware_illiquid_spread_capture(self):
        """Verifica que en métodos ilíquidos con spreads amplios (G3: BancoDelSol/PersonalPay),
        el algoritmo capture el margen completo hasta Puesto #2 en vez de un delta fijo pequeño."""
        benchmarks = {
            "MercadoPagoNew": Benchmark(
                payment_method="MercadoPagoNew",
                avg_top_n_price=1600.0, individual_prices=[1600.0, 1600.30], timestamp=datetime.now()
            ),
            "personalpay": Benchmark(
                payment_method="personalpay",
                avg_top_n_price=1615.0,
                # P1 = 1615.0, P2 = 1625.0 (spread real de $10 ARS)
                individual_prices=[1615.0, 1625.0, 1630.0],
                timestamp=datetime.now()
            ),
        }

        advice = self.advisor.get_sell_advice(benchmarks=benchmarks)
        c3 = advice[2]
        self.assertEqual(c3.cluster_id, 3)
        self.assertEqual(c3.top1_price, 1615.0)
        # En vez del viejo 1615.0 + 2.20 = 1617.20 (que regalaba $7.80 ARS),
        # Book-Aware se posiciona en 1625.0 - 0.01 = 1624.99 (Puesto #2 real)
        self.assertEqual(c3.suggested_price, 1624.99)
        self.assertEqual(c3.spread_added, 9.99)
        self.assertEqual(c3.estimated_position, "Puesto #2")

    def test_book_aware_max_outlier_cap(self):
        """Verifica que ante un libro vacío con P2 inflado a precio absurdo, se respete el cap de 2.5%."""
        benchmarks = {
            "MercadoPagoNew": Benchmark(
                payment_method="MercadoPagoNew",
                avg_top_n_price=1600.0, individual_prices=[1600.0], timestamp=datetime.now()
            ),
            "personalpay": Benchmark(
                payment_method="personalpay",
                avg_top_n_price=1600.0,
                # P2 a +$100 ARS (outlier absurdo)
                individual_prices=[1600.0, 1700.0],
                timestamp=datetime.now()
            ),
        }

        advice = self.advisor.get_sell_advice(benchmarks=benchmarks)
        c3 = advice[2]
        # Cap de 2.5%: 1600.0 * 1.025 = 1640.0
        self.assertEqual(c3.suggested_price, 1640.0)

    def test_format_sell_advice_report(self):
        """Verifica que el reporte generado contenga la estructura markdown y la leyenda de solo lectura."""
        dummy_advice = [
            ClusterAdvice(
                cluster_id=1,
                title="Billeteras Masivas (Salida Rápida)",
                methods=["MercadoPagoNew", "LemonCash"],
                anchor_method="MercadoPagoNew",
                top1_price=1585.00,
                suggested_price=1585.35,
                spread_added=0.35,
                estimated_position="Puesto #2",
                extra_profit_per_usdt=0.0,
                estimated_extra_ticket_ars=0.0,
                suggested_min_ars=15000.0,
                suggested_max_ars=0.0,
                speed_label="⚡ Máxima (5 - 10 min)",
                is_valid_data=True,
                notes="Rotación inmediata",
            )
        ]

        report = format_sell_advice_report(dummy_advice, now_str="14:30", ticket_ref=350.0)
        self.assertIn("💡 *ASESOR DE VENTAS P2P USDT* ⚡", report)
        self.assertIn("14:30 hs", report)
        self.assertIn("Mercado Pago", report)
        self.assertIn("$1,585.35 ARS", report)
        self.assertIn("Solo Lectura", report)
        self.assertIn("No emite ninguna orden a Binance", report)

    def test_telegram_integration_panel_and_commands(self):
        """Verifica que el botón esté presente en el panel inline y los comandos registrados."""
        bot = TelegramBot(db=self.mock_db)
        panel = bot.get_inline_panel()

        # Buscar el callback_data 'bot_sell_advisor' en la botonera
        buttons = [btn for row in panel.inline_keyboard for btn in row]
        sell_button = next((btn for btn in buttons if btn.callback_data == "bot_sell_advisor"), None)
        self.assertIsNotNone(sell_button, "El botón 'bot_sell_advisor' no está en el panel inline")
        self.assertIn("Sugerencia Venta", sell_button.text)

        # Verificar que el comando esté registrado
        import inspect
        source = inspect.getsource(TelegramBot.start)
        self.assertIn('("sugerencia_venta", self._cmd_sell_advisor)', source)
        self.assertIn('("sugerencias_venta", self._cmd_sell_advisor)', source)
        self.assertIn('("venta_tips", self._cmd_sell_advisor)', source)

    def test_podio_capping_when_market_compressed(self):
        """Verifica que si el mercado está muy comprimido, el precio sugerido no caiga más allá del puesto 3."""
        benchmarks = {
            "MercadoPagoNew": Benchmark(
                payment_method="MercadoPagoNew",
                avg_top_n_price=1585.0, individual_prices=[1585.0], timestamp=datetime.now()
            ),
            # En bancos Santander, Puesto 1=1590.0, Puesto 2=1590.20, Puesto 3=1590.50
            # Delta normal es +1.80 (daría 1591.80 -> Puesto #4 o peor).
            # Con el podio cap, debe topar en 1590.50 (Puesto #3).
            "SantanderArgentina": Benchmark(
                payment_method="SantanderArgentina",
                avg_top_n_price=1590.0,
                individual_prices=[1590.0, 1590.20, 1590.50, 1592.0],
                timestamp=datetime.now()
            ),
        }

        advice = self.advisor.get_sell_advice(benchmarks=benchmarks)
        c2 = advice[1]
        self.assertEqual(c2.top1_price, 1590.0)
        self.assertEqual(c2.suggested_price, 1590.49)  # Capped right below Puesto 3 (1590.50 - 0.01)
        self.assertEqual(c2.spread_added, 0.49)        # 1590.49 - 1590.00
        self.assertEqual(c2.estimated_position, "Puesto #3")

    def test_format_sell_advice_report_staleness_warning(self):
        """Verifica que si los datos tienen más de 30 minutos de antigüedad, emita una advertencia."""
        from datetime import timedelta
        stale_ts = datetime.now() - timedelta(minutes=45)
        stale_advice = [
            ClusterAdvice(
                cluster_id=1,
                title="Billeteras Masivas (Salida Rápida)",
                methods=["MercadoPagoNew"],
                anchor_method="MercadoPagoNew",
                top1_price=1580.0,
                suggested_price=1580.35,
                spread_added=0.35,
                estimated_position="Puesto #2",
                extra_profit_per_usdt=0.0,
                estimated_extra_ticket_ars=0.0,
                suggested_min_ars=15000.0,
                suggested_max_ars=0.0,
                speed_label="⚡ Máxima",
                is_valid_data=True,
                notes="",
                data_timestamp=stale_ts,
            )
        ]

        report = format_sell_advice_report(stale_advice, now_str="15:00")
        self.assertIn("⚠️ *DATOS HISTÓRICOS*", report)
        self.assertIn("hace 45 min", report)
        self.assertIn("Verificá los precios en Binance antes de publicar", report)

    def test_calculate_cluster_multi_method_sell_price(self):
        """Verifica que el cálculo multi-método elija el mejor precio competitivo del grupo
        (ej. Brubank a 1612.8) en vez de arrodillarse ante Mercado Pago (1610.35)."""
        from core.sell_advisor import calculate_cluster_multi_method_sell_price
        st_now = datetime.now()
        benchmarks = {
            # Mercado Pago con precios minoristas bajos
            "MercadoPagoNew": Benchmark(
                payment_method="MercadoPagoNew",
                avg_top_n_price=1610.0,
                individual_prices=[1610.0, 1610.3, 1610.4],
                timestamp=st_now,
            ),
            # Brubank con cotización mayorista superior
            "BancoBrubankNew": Benchmark(
                payment_method="BancoBrubankNew",
                avg_top_n_price=1612.45,
                individual_prices=[1612.45, 1612.8, 1613.0],
                timestamp=st_now,
            ),
            # Lemon Cash intermedio
            "LemonCash": Benchmark(
                payment_method="LemonCash",
                avg_top_n_price=1611.11,
                individual_prices=[1611.11, 1611.4],
                timestamp=st_now,
            ),
        }

        methods_g1 = ["MercadoPagoNew", "LemonCash", "BancoBrubankNew", "UalaNew", "NaranjaX"]
        sugg_p, top1, leader_m, prices, ts = calculate_cluster_multi_method_sell_price(
            cluster_methods=methods_g1,
            benchmarks=benchmarks,
            cluster_id=1,
            default_delta=0.35,
            anchor_method="MercadoPagoNew",
        )

        # Debe elegir BancoBrubankNew como método líder
        self.assertEqual(leader_m, "BancoBrubankNew")
        self.assertEqual(top1, 1612.45)
        # 1612.45 + 0.35 = 1612.80 (o dynamic target P2 - 0.01 = 1612.79)
        self.assertGreaterEqual(sugg_p, 1612.79)
        self.assertLessEqual(sugg_p, 1613.0)


if __name__ == "__main__":
    unittest.main()
