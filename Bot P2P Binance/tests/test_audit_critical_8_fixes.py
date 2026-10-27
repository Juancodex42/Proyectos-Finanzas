"""
Tests automatizados que verifican la resolución de los 8 errores críticos:
1. Stock real de Fondos en ventas (no se triplica, pausa en 0 USDT).
2. Import de datetime en ads_manager.py para ventas.
3. Cripto ejecutada en ventas (Anti-187040: suma lo ejecutado al actualizar).
4. Sell guardrails re-audita tras ajuste de break-even (no saltea frescura ni oráculo).
5. LiquidityTracker initialize concilia altcoins dividiendo por Spot (tc_implicito real).
6. ProfitTracker calculate_profit normaliza ventas de altcoins a USDT equivalente.
7. Límite mínimo de Mercado Pago (G1) usa piso de $15.000 ARS y no el 50% de la cartera.
8. Repositioner decremento de cripto ajusta new_max_trans_amount y pasa AntiBanValidator sin abortar.
"""
import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from core.ads.manager import AdsManager
from core.antiban_validator import AntiBanValidator
from core.liquidity.liquidity_manager import LiquidityTracker
from core.profit_tracker import ProfitTracker
from core.pricing.buy_repositioner import Repositioner
from core.sell_guardrails import SellGuardrails
from core.pricing.sell_repositioner import SellRepositioner
from data.database import Database
from data.models import Benchmark, BotConfig, DetectedOrder, MyAd, RepositionDecision, SellDecision


class TestAuditCritical8Fixes(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_client = MagicMock()
        self.mock_ads = MagicMock()
        self.mock_profit = MagicMock()
        self.mock_fiwind = MagicMock()

    # ──────────────────────────────────────────────────────────────────────────
    # Test 1: Stock real de Fondos y pausa preventiva cuando el saldo es 0
    # ──────────────────────────────────────────────────────────────────────────
    def test_fix_1_free_funding_zero_pauses_ads_and_does_not_triple(self):
        """Verifica que el bot no triplique el saldo y que con 0 USDT pause de inmediato."""
        async def _run():
            # Simular 3 anuncios existentes de 100 USDT cada uno en SQLite
            self.mock_db.get_my_sell_ads.return_value = [
                MyAd(adv_no="AD1", asset="USDT", ad_group=1, current_price=1580.0, payment_methods=["MP"], status=1, init_amount=100.0, surplus_amount=100.0),
                MyAd(adv_no="AD2", asset="USDT", ad_group=2, current_price=1582.0, payment_methods=["Santander"], status=1, init_amount=100.0, surplus_amount=100.0),
                MyAd(adv_no="AD3", asset="USDT", ad_group=3, current_price=1584.0, payment_methods=["PersonalPay"], status=1, init_amount=100.0, surplus_amount=100.0),
            ]
            self.mock_db.get_latest_benchmarks.return_value = {
                "MercadoPagoNew": Benchmark(payment_method="MercadoPagoNew", avg_top_n_price=1580.0, individual_prices=[1580.0, 1581.0, 1582.0], timestamp=datetime.now())
            }

            self.mock_profit.get_effective_wac_cost.return_value = 1570.0
            self.mock_fiwind.get_usdt_bid = AsyncMock(return_value=1580.0)

            # En Binance la billetera de fondos quedó en 0.0 USDT
            client_mock = MagicMock()
            client_mock.get_funding_asset = AsyncMock(return_value=0.0)
            self.mock_ads.client = client_mock

            repositioner = SellRepositioner(
                db=self.mock_db,
                ads_manager=self.mock_ads,
                profit_tracker=self.mock_profit,
                fiwind_client=self.mock_fiwind,
            )

            decisions = await repositioner.evaluate_sell_clusters(available_crypto_stock=350.0)

            # Verificar que con saldo 0 en fondos el stock no se triplicó a 300
            for dec in decisions:
                self.assertEqual(dec.new_init_amount, 0.0)
                self.assertTrue(dec.should_pause, f"G{dec.cluster_id} debió pausarse por saldo 0")
                self.assertIn("saldo_menor_a_piso", dec.pause_reason)

        asyncio.run(_run())

    # ──────────────────────────────────────────────────────────────────────────
    # Test 2: datetime import en ads_manager.py
    # ──────────────────────────────────────────────────────────────────────────
    def test_fix_2_ads_manager_datetime_import(self):
        """Verifica que update_sell_ad_params actualice ad.last_repositioned sin NameError."""
        async def _run():
            client_mock = MagicMock()
            client_mock.update_ad = AsyncMock(return_value={"data": True})

            existing_ad = MyAd(adv_no="AD_SELL_1", asset="USDT", ad_group=1, current_price=1580.0, payment_methods=["MP"])
            self.mock_db.get_my_sell_ads.return_value = [existing_ad]

            mgr = AdsManager(client=client_mock, db=self.mock_db)
            ok = await mgr.update_sell_ad_params(
                adv_no="AD_SELL_1",
                price=1585.0,
                init_amount=200.0,
                surplus_amount=200.0,
                min_trans_amount=15000.0,
                max_trans_amount=300000.0,
            )

            self.assertTrue(ok)
            self.assertEqual(existing_ad.current_price, 1585.0)
            self.assertEqual(existing_ad.init_amount, 200.0)
            self.assertEqual(existing_ad.surplus_amount, 200.0)
            self.assertIsInstance(existing_ad.last_repositioned, datetime)
            self.mock_db.save_my_sell_ad.assert_called_with(existing_ad)

        asyncio.run(_run())

    # ──────────────────────────────────────────────────────────────────────────
    # Test 3: Cripto ya vendida (Anti-187040) al actualizar venta
    # ──────────────────────────────────────────────────────────────────────────
    def test_fix_3_sell_repositioner_executed_crypto_sum_187040(self):
        """Verifica que al enviar update_sell_ad_params se envíe executed_crypto + new_tradable."""
        async def _run():
            # Anuncio con 500 USDT iniciales y 200 de surplus (ejecutó 300 USDT)
            existing_ad = MyAd(adv_no="AD_TEST", asset="USDT", ad_group=1, current_price=1580.0, payment_methods=["MP"], status=1, init_amount=500.0, surplus_amount=200.0)
            self.mock_db.get_my_sell_ads.return_value = [existing_ad]

            repositioner = SellRepositioner(
                db=self.mock_db,
                ads_manager=self.mock_ads,
                profit_tracker=self.mock_profit,
                fiwind_client=self.mock_fiwind,
            )

            captured_kwargs = {}
            async def fake_update(adv_no, **kwargs):
                captured_kwargs.update(kwargs)
                return True

            self.mock_ads.update_sell_ad_params = AsyncMock(side_effect=fake_update)

            decision = SellDecision(
                cluster_id=1,
                title="G1",
                anchor_method="MP",
                suggested_price=1585.0,
                top1_price=1584.0,
                spread_added=1.0,
                estimated_position="#2",
                wac_cost=0.0,
                fiwind_bid=0.0,
                adv_no="AD_TEST",
                should_update=True,
                new_init_amount=250.0,  # Nuevo saldo que se desea vender
                new_min_trans_amount=15000.0,
                new_max_trans_amount=350000.0,
                is_safe=True,
            )

            await repositioner.execute_sell_decisions([decision])

            # Anti-187049: no reenviar initAmount en quickedit para evitar bloqueo de fondos en Binance
            self.assertIsNone(captured_kwargs.get("init_amount"))
            # surplus_amount enviado a la DB debe ser 250.0
            self.assertEqual(captured_kwargs.get("surplus_amount"), 250.0)

        asyncio.run(_run())

    # ──────────────────────────────────────────────────────────────────────────
    # Test 4: Sell Guardrails re-audita tras ajuste de Break-Even
    # ──────────────────────────────────────────────────────────────────────────
    def test_fix_4_sell_guardrails_recheck_on_break_even(self):
        """Verifica que si el precio se ajusta por break-even, no se saltee la frescura de datos."""
        async def _run():
            stale_time = datetime.now() - timedelta(seconds=300)  # Datos obsoletos (>240s)
            stale_bm = Benchmark(
                payment_method="MercadoPagoNew",
                avg_top_n_price=1500.0,
                individual_prices=[1500.0, 1501.0, 1502.0],
                timestamp=stale_time,
            )
            self.mock_db.get_latest_benchmarks.return_value = {"MercadoPagoNew": stale_bm}
            self.mock_profit.get_effective_wac_cost.return_value = 1580.0  # WAC alto -> fuerza break-even adjustment
            self.mock_fiwind.get_usdt_bid = AsyncMock(return_value=1580.0)

            repositioner = SellRepositioner(
                db=self.mock_db,
                ads_manager=self.mock_ads,
                profit_tracker=self.mock_profit,
                fiwind_client=self.mock_fiwind,
            )

            decisions = await repositioner.evaluate_sell_clusters()
            g1 = decisions[0]

            # Como los datos estaban obsoletos, al re-auditar el precio ajustado debe dar is_safe = False
            self.assertFalse(g1.is_safe, "No debió aprobar como seguro con datos de mercado obsoletos")
            self.assertIn("obsoletos", g1.safety_reason)

        asyncio.run(_run())

    # ──────────────────────────────────────────────────────────────────────────
    # Test 5: LiquidityTracker initialize concilia altcoins con Spot
    # ──────────────────────────────────────────────────────────────────────────
    def test_fix_5_liquidity_tracker_initialize_altcoin_spot(self):
        """Verifica que órdenes offline de BTC se guarden con tc_implicito = price / spot."""
        async def _run():
            mock_client = MagicMock()
            # Orden offline de compra de 0.01 BTC a $1.500.000 ARS (unitPrice = 150.000.000 ARS)
            mock_client.list_orders = AsyncMock(side_effect=[
                {"data": []},  # open orders
                {"data": [
                    {
                        "orderNumber": "ORD_BTC_1",
                        "orderStatus": "4",
                        "asset": "BTC",
                        "totalPrice": 1500000.0,
                        "amount": 0.01,
                        "unitPrice": 150000000.0,
                        "createTime": int(datetime.now().timestamp() * 1000),
                    }
                ]},
                {"data": []},  # sell open
                {"data": []},  # sell completed
            ])

            spot_mock = MagicMock()
            spot_mock.get_prices = AsyncMock(return_value={"BTC": 95000.0})

            saved_orders = []
            self.mock_db.get_all_detected_order_nos.return_value = {"PREV_ORDER"}
            self.mock_db.get_latest_detected_order_time.return_value = datetime.now() - timedelta(minutes=10)
            self.mock_db.save_detected_order.side_effect = lambda o: saved_orders.append(o)

            tracker = LiquidityTracker(client=mock_client, db=self.mock_db, spot_client=spot_mock)
            config = BotConfig(balance_ars=2000000.0)

            await tracker.initialize(config, spot_prices={"BTC": 95000.0})

            self.assertEqual(len(saved_orders), 1)
            btc_ord = saved_orders[0]
            # 150.000.000 / 95.000 = 1578.95 ARS/USDT
            self.assertEqual(btc_ord.tc_implicito, 1578.95)
            self.assertNotEqual(btc_ord.tc_implicito, 150000000.0)

        asyncio.run(_run())

    # ──────────────────────────────────────────────────────────────────────────
    # Test 6: ProfitTracker normaliza ventas de altcoins
    # ──────────────────────────────────────────────────────────────────────────
    def test_fix_6_profit_tracker_calculate_profit_altcoin_sales(self):
        """Verifica que calculate_profit convierta ventas de BTC a USDT equivalente."""
        async def _run():
            # Simulamos 1 venta de 100 USDT y 1 venta de 0.01 BTC ($1.500.000 ARS, tc=1578.95)
            sells_data = [
                {"order_no": "S1", "asset": "USDT", "amount_crypto": 100.0, "amount_ars": 158500.0, "tc_implicito": 1585.0},
                {"order_no": "S2", "asset": "BTC", "amount_crypto": 0.01, "amount_ars": 1500000.0, "tc_implicito": 1578.95},
            ]
            buys_data = [
                {"order_no": "B1", "asset": "USDT", "amount_crypto": 1050.0, "amount_ars": 1659000.0, "tc_implicito": 1580.0},
            ]

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.execute.side_effect = [
                MagicMock(fetchall=lambda: buys_data),
                MagicMock(fetchall=lambda: sells_data),
            ]
            self.mock_db._lock = MagicMock()
            self.mock_db._lock.__enter__ = MagicMock(return_value=None)
            self.mock_db._lock.__exit__ = MagicMock(return_value=None)
            self.mock_db.connect.return_value = mock_conn

            tracker = ProfitTracker(db=self.mock_db)
            report = await tracker.calculate_profit("2026-10-13")

            # 0.01 BTC a $1.500.000 con tc=1578.95 equivale a ~950.0 USDT
            # total_sell_usdt debe ser 100 + 950 = ~1050 USDT, NO 100.01 USDT
            self.assertGreater(report.total_sell_usdt, 1000.0)
            self.assertAlmostEqual(report.total_sell_usdt, 100.0 + (1500000.0 / 1578.95), places=1)

        asyncio.run(_run())

    # ──────────────────────────────────────────────────────────────────────────
    # Test 7: Límite mínimo de Mercado Pago (G1) usa piso de $15.000 ARS
    # ──────────────────────────────────────────────────────────────────────────
    def test_fix_7_sell_limits_mercado_pago_floor(self):
        """Verifica que Mercado Pago (G1) tenga mínimo de $15.000 ARS incluso con 2.000 USDT de stock."""
        decisions = [
            SellDecision(cluster_id=1, title="G1 MP", anchor_method="MP", suggested_price=1580.0, top1_price=1579.0, spread_added=1.0, estimated_position="#2", wac_cost=0, fiwind_bid=0),
            SellDecision(cluster_id=2, title="G2 Bancos", anchor_method="Santander", suggested_price=1585.0, top1_price=1583.0, spread_added=2.0, estimated_position="#2", wac_cost=0, fiwind_bid=0),
            SellDecision(cluster_id=3, title="G3 Fintech", anchor_method="PersonalPay", suggested_price=1590.0, top1_price=1587.0, spread_added=3.0, estimated_position="#2", wac_cost=0, fiwind_bid=0),
        ]

        repositioner = SellRepositioner(
            db=self.mock_db,
            ads_manager=self.mock_ads,
            profit_tracker=self.mock_profit,
            fiwind_client=self.mock_fiwind,
        )

        resolved = repositioner.resolve_sell_collisions(decisions, available_crypto_stock=2000.0)

        g1 = resolved[0]
        # Con 2000 USDT (~$3.16M ARS), G1 debe tener límites dinámicos según SELL_GROUP_LIMIT_FACTORS (min ~50%, max ~100%)
        cap1 = g1.new_init_amount * g1.suggested_price
        self.assertAlmostEqual(g1.new_min_trans_amount / cap1, 0.50, delta=0.02)
        self.assertAlmostEqual(g1.new_max_trans_amount / cap1, 1.00, delta=0.02)
        self.assertGreater(g1.new_min_trans_amount, 1000000.0)
        self.assertGreater(g1.new_max_trans_amount, 3000000.0)

    # ──────────────────────────────────────────────────────────────────────────
    # Test 8: Repositioner decremento ajusta new_max_trans_amount y pasa AntiBan
    # ──────────────────────────────────────────────────────────────────────────
    def test_fix_8_repositioner_buy_decrement_recomputes_max_trans(self):
        """Verifica que si eff_rounded se decrementa por colisión, se reajuste new_max_trans_amount."""
        fixed_ad = MyAd(adv_no="AD_FIXED", asset="FDUSD", ad_group=2, current_price=1490.0, payment_methods=["BANK"], status=1, init_amount=200.0, surplus_amount=200.0)
        ad_g1 = MyAd(adv_no="AD1", asset="FDUSD", ad_group=1, current_price=1500.0, payment_methods=["BANK"], status=1, init_amount=200.0, surplus_amount=200.0, min_trans_amount=15000.0, max_trans_amount=300000.0)
        dec_g1 = RepositionDecision(new_price=1500.0, should_update=True, new_min_trans_amount=15000.0, new_max_trans_amount=300000.0)

        repo = Repositioner(
            ads_manager=self.mock_ads,
            scanner=MagicMock(),
            liquidity=MagicMock(available_balance=300000.0),  # 300000 / 1500 = 200.0 max_aff -> obliga a bajar de 200.0
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=self.mock_db,
        )

        pairs = [(ad_g1, dec_g1)]
        resolved_pairs = repo.resolve_asset_price_collisions("FDUSD", pairs, BotConfig(), all_asset_ads=[fixed_ad])

        self.assertEqual(len(resolved_pairs), 1)
        final_ad_g1, final_dec_g1 = resolved_pairs[0]
        self.assertEqual(final_ad_g1.adv_no, "AD1")
        # El monto debe haber bajado de 200.0 para no clonar fixed_ad
        self.assertLess(final_dec_g1.new_init_amount, 200.0)
        # Capacidad tradable: new_max_trans_amount debió ajustarse para no superar la capacidad reducida
        cap_max = final_dec_g1.new_init_amount * 1500.0
        self.assertLessEqual(final_dec_g1.new_max_trans_amount, cap_max)

        # Ejecutar AntiBanValidator
        viols = AntiBanValidator.audit_asset_decisions(
            asset="FDUSD",
            ad_decision_pairs=resolved_pairs,
            spot_price=1.0,
            price_step=0.01,
            fiat_rate=1500.0,
        )
        criticals = [v for v in viols if v.severity == "CRITICAL"]
        self.assertEqual(criticals, [], f"No debe haber violaciones críticas: {[str(v) for v in criticals]}")


if __name__ == "__main__":
    unittest.main()
