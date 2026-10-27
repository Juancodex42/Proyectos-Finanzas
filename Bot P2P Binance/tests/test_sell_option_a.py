"""
Tests exhaustivos para la Opción A (Escalera de Alta Rotación desde el Puesto #1):
1. Verificación de publisherType='merchant' en BinanceClient.search_ads y MarketScanner.scan_usdt_benchmark.
2. Posicionamiento de G1 en Puesto #1 (Top 1 verificado - 0.01 ARS).
3. Escalera de ventas: G1 (Base) < G3 (Base + $0.35) < G2 (Base + $0.70).
4. Cumplimiento estricto de separación >= $0.30 ARS (Regla Binance Error 187055).
5. Límites dinámicos de 50% a 100% proporcionales al saldo libre en Fondos.
6. Blindaje de Break-Even WAC y guardarraíles de seguridad.
"""
import asyncio
import math
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from core.network.binance_api import BinanceClient
from core.market_scanner import MarketScanner
from core.pricing.sell_repositioner import SellRepositioner
from data.models import Benchmark, MyAd, SellDecision, BotConfig
from config.settings import (
    FIAT,
    SELL_AD_PRICE_DIFF_ARS,
    SELL_CASCADE_MODE,
    SELL_GROUP_LIMIT_FACTORS,
)


class TestSellOptionA(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_ads = MagicMock()
        self.mock_profit = MagicMock()
        self.mock_fiwind = MagicMock()
        self.repositioner = SellRepositioner(
            db=self.mock_db,
            ads_manager=self.mock_ads,
            profit_tracker=self.mock_profit,
            fiwind_client=self.mock_fiwind,
            cascade_mode="HIGH_ROTATION_LADDER",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Verificación de Comerciantes Verificados en Benchmark
    # ──────────────────────────────────────────────────────────────────────────
    def test_search_ads_includes_publisher_type_when_provided(self):
        """Verifica que search_ads envíe publisherType en el payload solo cuando no es None."""
        async def _run():
            client = BinanceClient(api_key="k", secret_key="s", validate_keys=False)
            client.signed_post = AsyncMock(return_value={"data": []})

            # Caso 1: con publisher_type="merchant"
            await client.search_ads(
                asset="USDT",
                fiat="ARS",
                trade_type="BUY",
                publisher_type="merchant",
            )
            client.signed_post.assert_called_with(
                "/sapi/v1/c2c/ads/search",
                body={
                    "asset": "USDT",
                    "fiat": "ARS",
                    "tradeType": "BUY",
                    "page": 1,
                    "rows": 20,
                    "publisherType": "merchant",
                },
            )

            # Caso 2: sin publisher_type (None)
            client.signed_post.reset_mock()
            await client.search_ads(
                asset="USDT",
                fiat="ARS",
                trade_type="BUY",
            )
            client.signed_post.assert_called_with(
                "/sapi/v1/c2c/ads/search",
                body={
                    "asset": "USDT",
                    "fiat": "ARS",
                    "tradeType": "BUY",
                    "page": 1,
                    "rows": 20,
                },
            )

        asyncio.run(_run())

    def test_scan_usdt_benchmark_filters_verified_merchants_by_default(self):
        """Verifica que scan_usdt_benchmark solicite publisher_type='merchant'."""
        async def _run():
            mock_client = MagicMock()
            mock_client.search_ads = AsyncMock(return_value={"data": []})
            mock_spot = MagicMock()
            scanner = MarketScanner(client=mock_client, spot_client=mock_spot, db=self.mock_db)

            await scanner.scan_usdt_benchmark(payment_method="MercadoPagoNew", volume_ref=500000.0)

            mock_client.search_ads.assert_called_once_with(
                asset="USDT",
                fiat=FIAT,
                trade_type="BUY",
                pay_types=["MercadoPagoNew"],
                trans_amount=500000.0,
                publisher_type="merchant",
                rows=10,
            )

        asyncio.run(_run())

    def test_scan_full_cycle_passes_verified_merchant_and_max_stock(self):
        """Verifica que scan_full_cycle use max_stock_ars y publisher_type='merchant'."""
        async def _run():
            mock_client = MagicMock()
            mock_client.search_ads = AsyncMock(return_value={"data": []})
            mock_spot = MagicMock()
            mock_spot.get_usdt_prices = AsyncMock(return_value={"USDT": 1.0})
            mock_spot.get_24hr_volatilities = AsyncMock(return_value={})
            scanner = MarketScanner(client=mock_client, spot_client=mock_spot, db=self.mock_db)

            scanner.scan_usdt_benchmark = AsyncMock(return_value=None)
            scanner.scan_competitors = AsyncMock(return_value=[])

            groups = {1: ["MercadoPagoNew"]}
            await scanner.scan_full_cycle(
                assets=["USDT"],
                method_groups=groups,
                volume_ref=50000.0,
                max_stock_ars=750000.0,
            )

            scanner.scan_usdt_benchmark.assert_called_with(
                "MercadoPagoNew", 750000.0, publisher_type="merchant"
            )

        asyncio.run(_run())

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Escalera Opción A: G1 en #1, G3 en Base+0.35, G2 en Base+0.70
    # ──────────────────────────────────────────────────────────────────────────
    def test_resolve_sell_collisions_option_a_ladder(self):
        """Verifica que Opción A ubique G1 en Base, G3 en Base + $0.35 y G2 en Base + $0.70."""
        decisions = [
            SellDecision(
                cluster_id=1,
                title="Billeteras",
                anchor_method="MercadoPagoNew",
                suggested_price=1584.49,  # Puesto #1 (1584.50 - 0.01)
                top1_price=1584.50,
                spread_added=-0.01,
                estimated_position="Puesto #1 (MercadoPagoNew)",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
            SellDecision(
                cluster_id=2,
                title="Bancos",
                anchor_method="SantanderArgentina",
                suggested_price=1590.00,
                top1_price=1589.50,
                spread_added=0.50,
                estimated_position="Puesto #2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
            SellDecision(
                cluster_id=3,
                title="Fintechs",
                anchor_method="personalpay",
                suggested_price=1587.00,
                top1_price=1586.50,
                spread_added=0.50,
                estimated_position="Puesto #2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
        ]

        resolved = self.repositioner.resolve_sell_collisions(
            decisions, available_crypto_stock=350.0, cascade_mode="HIGH_ROTATION_LADDER"
        )
        self.assertEqual(len(resolved), 3)

        by_grp = {d.cluster_id: d for d in resolved}
        p1 = by_grp[1].suggested_price
        p2 = by_grp[2].suggested_price
        p3 = by_grp[3].suggested_price

        # G1 es Base (Puesto #1)
        self.assertEqual(p1, 1584.49)
        # G3 es Base + 0.35
        self.assertEqual(p3, 1584.84)
        # G2 es Base + 0.70
        self.assertEqual(p2, 1585.19)

        # Jerarquía estricta: G1 < G3 < G2
        self.assertLess(p1, p3)
        self.assertLess(p3, p2)

        # Separación fija exacta >= $0.35 ARS (cumple >= $0.30 obligatorio)
        diff_3_1 = round(p3 - p1, 2)
        diff_2_3 = round(p2 - p3, 2)
        self.assertEqual(diff_3_1, 0.35)
        self.assertEqual(diff_2_3, 0.35)

        # Supera holgadamente el límite de error 187055 de Binance (> $0.15 ARS)
        self.assertGreater(diff_3_1, 0.15)
        self.assertGreater(diff_2_3, 0.15)

    def test_evaluate_sell_clusters_calculates_option_a_from_benchmarks(self):
        """Verifica que evaluate_sell_clusters calcule G1 en Puesto #1 y la escalera G1 < G3 < G2."""
        async def _run():
            st_now = datetime.now()
            bms = {
                "MercadoPagoNew": Benchmark(
                    payment_method="MercadoPagoNew",
                    avg_top_n_price=1585.00,
                    individual_prices=[1585.00, 1585.20, 1585.50],
                    timestamp=st_now,
                ),
                "SantanderArgentina": Benchmark(
                    payment_method="SantanderArgentina",
                    avg_top_n_price=1592.00,
                    individual_prices=[1592.00, 1592.50],
                    timestamp=st_now,
                ),
                "personalpay": Benchmark(
                    payment_method="personalpay",
                    avg_top_n_price=1588.00,
                    individual_prices=[1588.00, 1588.50],
                    timestamp=st_now,
                ),
            }
            self.mock_db.get_latest_benchmarks.return_value = bms
            self.mock_profit.get_effective_wac_cost.return_value = 1570.0
            self.mock_fiwind.get_usdt_bid = AsyncMock(return_value=1580.0)

            decisions = await self.repositioner.evaluate_sell_clusters(
                benchmarks=bms, available_crypto_stock=500.0
            )

            by_grp = {d.cluster_id: d for d in decisions}
            g1 = by_grp[1]
            g2 = by_grp[2]
            g3 = by_grp[3]

            # G1 debe apuntar a Top 1 verificado - 0.01 = 1585.00 - 0.01 = 1584.99
            self.assertEqual(g1.suggested_price, 1584.99)
            self.assertEqual(g1.spread_added, -0.01)

            # G3 debe quedar a Base + 0.35 = 1584.99 + 0.35 = 1585.34
            self.assertEqual(g3.suggested_price, 1585.34)

            # G2 debe quedar a Base + 0.70 = 1584.99 + 0.70 = 1585.69
            self.assertEqual(g2.suggested_price, 1585.69)

            # Separación estricta >= 0.35
            self.assertEqual(round(g3.suggested_price - g1.suggested_price, 2), 0.35)
            self.assertEqual(round(g2.suggested_price - g3.suggested_price, 2), 0.35)

        asyncio.run(_run())

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Límites dinámicos 50% - 100% y contracción por liquidez
    # ──────────────────────────────────────────────────────────────────────────
    def test_dynamic_limits_50_to_100_percent_contraction(self):
        """Verifica que min sea 50% y max 100% de la capacidad de stock en Fondos, contrayéndose con la liquidez."""
        decisions_350 = [
            SellDecision(cluster_id=1, title="G1", anchor_method="MP", suggested_price=1600.0, top1_price=1600.01, spread_added=-0.01, estimated_position="Puesto #1", wac_cost=1550.0, fiwind_bid=1590.0),
            SellDecision(cluster_id=2, title="G2", anchor_method="Santander", suggested_price=1600.70, top1_price=1600.01, spread_added=0.69, estimated_position="Base+0.70", wac_cost=1550.0, fiwind_bid=1590.0),
            SellDecision(cluster_id=3, title="G3", anchor_method="PersonalPay", suggested_price=1600.35, top1_price=1600.01, spread_added=0.34, estimated_position="Base+0.35", wac_cost=1550.0, fiwind_bid=1590.0),
        ]

        # Con 350 USDT:
        res_350 = self.repositioner.resolve_sell_collisions(decisions_350, available_crypto_stock=350.0, cascade_mode="HIGH_ROTATION_LADDER")
        for dec in res_350:
            cap = dec.new_init_amount * dec.suggested_price
            self.assertEqual(dec.new_init_amount, 350.0)
            self.assertAlmostEqual(dec.new_min_trans_amount / cap, 0.50, delta=0.02)
            self.assertAlmostEqual(dec.new_max_trans_amount / cap, 1.00, delta=0.02)

        # Con 100 USDT (liquidez menor -> límites se contraen):
        decisions_100 = [
            SellDecision(cluster_id=1, title="G1", anchor_method="MP", suggested_price=1600.0, top1_price=1600.01, spread_added=-0.01, estimated_position="Puesto #1", wac_cost=1550.0, fiwind_bid=1590.0),
            SellDecision(cluster_id=2, title="G2", anchor_method="Santander", suggested_price=1600.70, top1_price=1600.01, spread_added=0.69, estimated_position="Base+0.70", wac_cost=1550.0, fiwind_bid=1590.0),
            SellDecision(cluster_id=3, title="G3", anchor_method="PersonalPay", suggested_price=1600.35, top1_price=1600.01, spread_added=0.34, estimated_position="Base+0.35", wac_cost=1550.0, fiwind_bid=1590.0),
        ]
        res_100 = self.repositioner.resolve_sell_collisions(decisions_100, available_crypto_stock=100.0, cascade_mode="HIGH_ROTATION_LADDER")
        for dec in res_100:
            cap = dec.new_init_amount * dec.suggested_price
            self.assertEqual(dec.new_init_amount, 100.0)
            self.assertAlmostEqual(dec.new_min_trans_amount / cap, 0.50, delta=0.02)
            self.assertAlmostEqual(dec.new_max_trans_amount / cap, 1.00, delta=0.02)
            # El max con 100 USDT debe ser menor que el max con 350 USDT
            self.assertLess(dec.new_max_trans_amount, 350.0 * dec.suggested_price)

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Blindaje Break-Even WAC
    # ──────────────────────────────────────────────────────────────────────────
    def test_wac_floor_guards_option_a_from_selling_below_cost(self):
        """Verifica que si Top 1 - 0.01 cae por debajo del costo WAC + margen, G1 suba al piso seguro."""
        async def _run():
            st_now = datetime.now()
            # Mercado deprimido: Top 1 en 1500.00 ARS
            bms = {
                "MercadoPagoNew": Benchmark(
                    payment_method="MercadoPagoNew",
                    avg_top_n_price=1500.00,
                    individual_prices=[1500.00, 1501.00],
                    timestamp=st_now,
                ),
            }
            self.mock_db.get_latest_benchmarks.return_value = bms
            # Costo WAC de compra alto: 1560.00 ARS + margen $5.00 -> piso $1565.00
            self.mock_profit.get_effective_wac_cost.return_value = 1560.00
            self.mock_fiwind.get_usdt_bid = AsyncMock(return_value=1560.00)

            cfg = BotConfig(sell_margin_min=5.0)
            decisions = await self.repositioner.evaluate_sell_clusters(
                benchmarks=bms, available_crypto_stock=350.0, config=cfg
            )

            g1 = decisions[0]
            # No debe vender a 1499.99 (perdería $65 ARS por USDT). Debe elevarse a WAC + margen = $1565.00
            self.assertGreaterEqual(g1.suggested_price, 1565.00)
            self.assertTrue(g1.is_safe)
            self.assertIn("Ajustado a piso de costo", g1.safety_reason)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
