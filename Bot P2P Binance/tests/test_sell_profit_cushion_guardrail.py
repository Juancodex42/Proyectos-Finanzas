import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from config.settings import SELL_MIN_MARGIN_PCT
from core.sell_guardrails import SellGuardrails
from core.pricing.sell_repositioner import SellRepositioner
from data.models import Benchmark, BotConfig, MyAd


class TestSellProfitCushionGuardrail(unittest.TestCase):
    """Pruebas unitarias para el Guardrail de Ganancia Garantizada (WAC + Colchón Telegram)."""

    def test_validate_break_even_with_ars_cushion(self):
        """Verifica que el piso en ARS (config.margin_min) bloquee precios con margen insuficiente."""
        wac_cost = 1580.0
        cushion_ars = 15.0
        # safe_floor = 1580.0 + 15.0 = 1595.0 ARS

        # 1. Precio por debajo del piso
        ok, reason = SellGuardrails.validate_break_even(
            price=1590.0,
            wac_cost=wac_cost,
            min_margin_ars=cushion_ars,
        )
        self.assertFalse(ok)
        self.assertIn("Pérdida evitada", reason)
        self.assertIn("colchón ($15.00 ARS)", reason)
        self.assertIn("1,595.00", reason)

        # 2. Precio exactamente en el piso
        ok, reason = SellGuardrails.validate_break_even(
            price=1595.0,
            wac_cost=wac_cost,
            min_margin_ars=cushion_ars,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "")

        # 3. Precio superior al piso
        ok, reason = SellGuardrails.validate_break_even(
            price=1605.0,
            wac_cost=wac_cost,
            min_margin_ars=cushion_ars,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_validate_break_even_prefers_higher_bound(self):
        """Verifica que tome el mayor entre el % break-even y el colchón en ARS."""
        wac_cost = 1000.0
        # 10% min_margin_pct da 1100. Colchón 50 da 1050. Debe exigir 1100.
        ok, _ = SellGuardrails.validate_break_even(
            price=1080.0,
            wac_cost=wac_cost,
            min_margin_pct=0.10,
            min_margin_ars=50.0,
        )
        self.assertFalse(ok)

        ok, _ = SellGuardrails.validate_break_even(
            price=1100.0,
            wac_cost=wac_cost,
            min_margin_pct=0.10,
            min_margin_ars=50.0,
        )
        self.assertTrue(ok)

    def test_validate_break_even_zero_wac(self):
        """Si no hay compras previas (WAC=0), cualquier precio positivo es válido."""
        ok, reason = SellGuardrails.validate_break_even(
            price=1600.0,
            wac_cost=0.0,
            min_margin_ars=15.0,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_backward_compatibility_signature(self):
        """Llamadas legacy sin min_margin_ars deben funcionar con SELL_MIN_MARGIN_PCT (0.2%)."""
        wac_cost = 1580.0
        # 1580 * 1.002 = 1583.16
        ok, reason = SellGuardrails.validate_break_even(1582.0, wac_cost)
        self.assertFalse(ok)
        self.assertIn("margen (0.2%)", reason)

        ok, reason = SellGuardrails.validate_break_even(1584.0, wac_cost)
        self.assertTrue(ok)

    def test_audit_sell_price_forwards_margin_ars(self):
        """Verifica que audit_sell_price audite el colchón en ARS correctamente."""
        ok, reason = SellGuardrails.audit_sell_price(
            price=1590.0,
            wac_cost=1580.0,
            fiwind_bid=1595.0,
            data_timestamp=datetime.now(),
            individual_prices=[1590.0, 1592.0, 1595.0],
            min_margin_ars=15.0,
        )
        self.assertFalse(ok)
        self.assertIn("colchón ($15.00 ARS)", reason)

    def test_sell_repositioner_adjusts_price_to_profit_cushion_floor(self):
        """Verifica que el motor de venta eleve el precio al piso de WAC + colchón si el libro baja."""
        import asyncio

        async def _run():
            mock_db = MagicMock()
            mock_db.get_latest_benchmarks.return_value = {}
            mock_db.get_my_sell_ads.return_value = []
            mock_db.load_bot_config.return_value = BotConfig(margin_min=15.0)

            mock_ads = MagicMock()
            mock_ads.client = MagicMock()
            mock_ads.client.get_funding_asset = AsyncMock(return_value=350.0)

            mock_tracker = MagicMock()
            # WAC = $1.580 -> Con colchón $15, piso seguro = $1.595 ARS
            mock_tracker.get_effective_wac_cost.return_value = 1580.0

            mock_fiwind = MagicMock()
            mock_fiwind.get_usdt_bid = AsyncMock(return_value=1598.0)

            repositioner = SellRepositioner(
                db=mock_db,
                ads_manager=mock_ads,
                profit_tracker=mock_tracker,
                fiwind_client=mock_fiwind,
            )

            # Simular un libro donde Mercado Pago Top 1 está a $1.588 y P2 a $1.589
            # Normalmente Book-Aware pondría ~1588.35 o 1588.99, por debajo del piso de $1.595
            bms = {
                "MercadoPagoNew": Benchmark(
                    payment_method="MercadoPagoNew",
                    avg_top_n_price=1588.0,
                    individual_prices=[1588.0, 1589.0, 1590.0],
                    timestamp=datetime.now(),
                ),
                "SantanderArgentina": Benchmark(
                    payment_method="SantanderArgentina",
                    avg_top_n_price=1592.0,
                    individual_prices=[1592.0, 1593.0, 1594.0],
                    timestamp=datetime.now(),
                ),
                "personalpay": Benchmark(
                    payment_method="personalpay",
                    avg_top_n_price=1595.0,
                    individual_prices=[1595.0, 1596.0, 1597.0],
                    timestamp=datetime.now(),
                ),
            }

            decisions = await repositioner.evaluate_sell_clusters(
                benchmarks=bms,
                available_crypto_stock=350.0,
                config=BotConfig(margin_min=15.0, sell_margin_min=15.0),
            )

            # G1 debe quedar ajustado exactamente al piso seguro de $1.595 ARS
            g1 = next(d for d in decisions if d.cluster_id == 1)
            self.assertEqual(g1.suggested_price, 1595.0)
            self.assertTrue(g1.is_safe)
            self.assertIn("Ajustado a piso de costo", g1.safety_reason)

            # G2 y G3 deben escalonar por encima respetando Regla 5.1 anti-colisión
            g2 = next(d for d in decisions if d.cluster_id == 2)
            g3 = next(d for d in decisions if d.cluster_id == 3)

            self.assertGreater(g3.suggested_price, g1.suggested_price)
            self.assertGreater(g2.suggested_price, g3.suggested_price)
            # Garantizar que G2 y G3 ganen más que el piso mínimo
            self.assertGreaterEqual(g2.suggested_price, 1595.0)
            self.assertGreaterEqual(g3.suggested_price, 1595.0)

        asyncio.run(_run())

    def test_decoupled_buy_and_sell_margins(self):
        """Verifica que cambiar el colchón de compra (ej: a 6 ARS por spread comprimido)
        NO degrade el piso de ganancia en venta si sell_margin_min está en 12 ARS."""
        import asyncio

        async def _run():
            mock_db = MagicMock()
            mock_db.get_latest_benchmarks.return_value = {}
            mock_db.get_my_sell_ads.return_value = []

            mock_ads = MagicMock()
            mock_ads.client = MagicMock()
            mock_ads.client.get_funding_asset = AsyncMock(return_value=350.0)

            mock_tracker = MagicMock()
            # WAC = $1.580 -> Con sell_margin_min = $12, piso seguro de venta = $1.592 ARS
            mock_tracker.get_effective_wac_cost.return_value = 1580.0

            mock_fiwind = MagicMock()
            mock_fiwind.get_usdt_bid = AsyncMock(return_value=1598.0)

            repositioner = SellRepositioner(
                db=mock_db,
                ads_manager=mock_ads,
                profit_tracker=mock_tracker,
                fiwind_client=mock_fiwind,
            )

            # Mercado deprimido por debajo de WAC + 12
            bms = {
                "MercadoPagoNew": Benchmark(
                    payment_method="MercadoPagoNew",
                    avg_top_n_price=1588.0,
                    individual_prices=[1588.0, 1589.0, 1590.0],
                    timestamp=datetime.now(),
                ),
            }

            # Configuración desacoplada: margen de compra bajo ($6) pero piso de venta alto ($12)
            config = BotConfig(margin_min=6.0, sell_margin_min=12.0)

            decisions = await repositioner.evaluate_sell_clusters(
                benchmarks=bms,
                available_crypto_stock=350.0,
                config=config,
            )

            g1 = next(d for d in decisions if d.cluster_id == 1)
            # El piso seguro debe ser 1580 + 12 = 1592.0 ARS (NO 1580 + 6 = 1586.0 ARS)
            self.assertEqual(g1.suggested_price, 1592.0)
            self.assertTrue(g1.is_safe)

        asyncio.run(_run())

    def test_database_persistence_sell_margin(self):
        """Verifica que sell_margin_min se persista y cargue correctamente en SQLite."""
        import tempfile
        import shutil
        from data.database import Database

        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "test.db"
            db = Database(db_path)
            db.init_schema()
            cfg = db.load_bot_config()
            self.assertEqual(cfg.sell_margin_min, 5.0)

            cfg.sell_margin_min = 18.5
            db.save_bot_config(cfg)

            loaded = db.load_bot_config()
            self.assertEqual(loaded.sell_margin_min, 18.5)
            db.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
