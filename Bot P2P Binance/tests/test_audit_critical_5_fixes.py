"""
Tests automatizados que verifican la resolución de los 5 bugs críticos:
1. telegram_bot/bot.py#L1144: _btn_sell_advisor instancia SellRepositioner antes de evaluate_sell_clusters.
2. core/liquidity_tracker.py#L255 y L313: Filtro [1, 2, 3, 5] para no fugar liquidez comprometida en apelaciones.
3. main.py#L1416: _reconcile_ads_internal une anuncios de compra y venta para la exclusión del scanner.
4. main.py#L925-L931: Re-agrupamiento en caliente propaga assign_groups a los anuncios reales.
5. main.py#L738: Pausa por colisión asigna AD_STATUS_OFFLINE (3) y no 2.
"""
import asyncio
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from config.settings import AD_STATUS_OFFLINE, AD_STATUS_ONLINE
from core.liquidity.liquidity_manager import LiquidityTracker
from data.models import BotConfig, DetectedOrder, MyAd, RepositionDecision, SellDecision


class TestAuditCritical5Fixes(unittest.TestCase):

    def test_fix_1_btn_sell_advisor_instantiates_sell_repositioner(self):
        """Verifica que _btn_sell_advisor instancie SellRepositioner y use el dashboard interactivo."""
        async def _run():
            from telegram_bot.bot import TelegramBot
            mock_db = MagicMock()
            bot_cfg = BotConfig(sell_margin_min=5.0)
            mock_db.load_bot_config.return_value = bot_cfg
            mock_db.get_my_sell_ads.return_value = []
            mock_db.get_latest_benchmarks.return_value = {}

            bot = TelegramBot(db=mock_db)
            bot._admin_ids = {12345}

            # Configurar mock engine
            mock_engine = MagicMock()
            mock_engine.last_benchmarks = {}
            mock_engine.fiwind = MagicMock()
            mock_engine.fiwind.get_usdt_bid = AsyncMock(return_value=1500.0)
            mock_engine.ads_manager = MagicMock()
            mock_engine.profit_tracker = MagicMock()
            mock_engine.profit_tracker.get_effective_wac_cost.return_value = 1450.0
            mock_engine.config = bot_cfg
            bot.engine = mock_engine

            # Mock Telegram callback query
            update = MagicMock()
            update.callback_query.data = "bot_sell_advisor"
            update.callback_query.from_user.id = 12345
            update.effective_user.id = 12345
            update.effective_chat.id = 12345
            update.callback_query.answer = AsyncMock()
            update.callback_query.edit_message_text = AsyncMock()
            ctx = MagicMock()

            with patch("core.pricing.sell_repositioner.SellRepositioner.evaluate_sell_clusters", new_callable=AsyncMock) as mock_eval:
                mock_eval.return_value = [
                    SellDecision(
                        cluster_id=1,
                        title="Billeteras",
                        anchor_method="MP",
                        suggested_price=1520.0,
                        top1_price=1519.0,
                        spread_added=1.0,
                        estimated_position="#2",
                        wac_cost=1450.0,
                        fiwind_bid=1500.0,
                        adv_no="S1",
                        should_update=True,
                    )
                ]
                await bot._handle_callback(update, ctx)

                # Verificar que evaluate_sell_clusters fue llamado exitosamente
                mock_eval.assert_called_once()
                # Verificar que edit_message_text fue llamado y no cayó en el fallback SellAdvisor
                self.assertTrue(update.callback_query.edit_message_text.called)
                msg_text = update.callback_query.edit_message_text.call_args[0][0]
                self.assertIn("PANEL DE CONTROL DE VENTA", msg_text)

        asyncio.run(_run())

    def test_fix_2_liquidity_tracker_queries_appeal_statuses_and_keeps_committed_fiat(self):
        """Verifica que list_orders use [1, 2, 3, 5] y las órdenes en disputa mantengan comprometida la liquidez."""
        async def _run():
            mock_client = AsyncMock()

            # Orden de compra en disputa (status 3) por $300.000 ARS
            async def mock_list(trade_type="BUY", order_status_list=None, rows=50):
                self.assertIn(order_status_list, ([1, 2, 3, 5], [4]))
                if trade_type == "BUY" and order_status_list == [1, 2, 3, 5]:
                    return {
                        "data": [
                            {
                                "orderNumber": "BUY_DISPUTE_001",
                                "advNo": "ADV_B1",
                                "asset": "USDT",
                                "tradeType": "BUY",
                                "amount": 200.0,
                                "totalPrice": 300000.0,
                                "unitPrice": 1500.0,
                                "orderStatus": 3,  # En apelación/disputa
                                "sellerNickname": "VendorP2P",
                                "payType": "MercadoPago",
                            }
                        ]
                    }
                elif trade_type == "SELL" and order_status_list == [1, 2, 3, 5]:
                    return {
                        "data": [
                            {
                                "orderNumber": "SELL_DISPUTE_002",
                                "advNo": "ADV_S1",
                                "asset": "USDT",
                                "tradeType": "SELL",
                                "amount": 100.0,
                                "totalPrice": 152000.0,
                                "unitPrice": 1520.0,
                                "orderStatus": 3,  # Venta en apelación
                                "buyerNickname": "BuyerP2P",
                                "payType": "Santander",
                            }
                        ]
                    }
                return {"data": []}

            mock_client.list_orders.side_effect = mock_list
            lt = LiquidityTracker(client=mock_client, db=MagicMock())
            lt._balance = 1000000.0

            res = await lt.sync_orders(spot_prices={"USDT": 1.0})

            # La orden de compra en apelación compromete los $300.000 ARS
            self.assertEqual(lt.committed_balance, 300000.0)
            self.assertEqual(lt.effective_balance, 700000.0)

            # La orden de venta en apelación debe notificarse
            incoming = lt.consume_incoming_orders()
            sell_orders = [o for o in incoming if o.trade_type == "SELL"]
            self.assertEqual(len(sell_orders), 1)
            self.assertEqual(sell_orders[0].order_no, "SELL_DISPUTE_002")
            self.assertEqual(sell_orders[0].status, "3")

        asyncio.run(_run())

    def test_fix_2b_sell_order_transition_to_appeal_is_notified(self):
        """Verifica que una venta que pasa de pagado (2) a apelación (3) se notifique nuevamente."""
        async def _run():
            mock_client = AsyncMock()
            current_status = 2

            async def mock_list(trade_type="BUY", order_status_list=None, rows=50):
                if trade_type == "SELL" and order_status_list == [1, 2, 3, 5]:
                    return {
                        "data": [
                            {
                                "orderNumber": "SELL_TR_001",
                                "advNo": "ADV_S1",
                                "asset": "USDT",
                                "tradeType": "SELL",
                                "amount": 50.0,
                                "totalPrice": 75000.0,
                                "unitPrice": 1500.0,
                                "orderStatus": current_status,
                                "buyerNickname": "BuyerP2P",
                                "payType": "MercadoPago",
                            }
                        ]
                    }
                return {"data": []}

            mock_client.list_orders.side_effect = mock_list
            lt = LiquidityTracker(client=mock_client, db=MagicMock())

            # Ciclo 1: status 2 (comprador marcó pagado)
            await lt.sync_orders(spot_prices={"USDT": 1.0})
            inc1 = lt.consume_incoming_orders()
            self.assertEqual(len(inc1), 1)
            self.assertEqual(inc1[0].status, "2")

            # Ciclo 2: status 3 (entró en disputa)
            current_status = 3
            await lt.sync_orders(spot_prices={"USDT": 1.0})
            inc2 = lt.consume_incoming_orders()
            self.assertEqual(len(inc2), 1)
            self.assertEqual(inc2[0].status, "3")

            # Ciclo 3: sigue en status 3 -> no duplicar
            await lt.sync_orders(spot_prices={"USDT": 1.0})
            inc3 = lt.consume_incoming_orders()
            self.assertEqual(len(inc3), 0)

        asyncio.run(_run())

    def test_fix_2c_startup_open_orders_handles_status_5(self):
        """Verifica que LiquidityTracker capture órdenes en status 5 al inicio y comprometa liquidez."""
        async def _run():
            mock_client = AsyncMock()
            mock_db = MagicMock()
            mock_db.get_latest_detected_order_time.return_value = None

            async def mock_list(trade_type="BUY", order_status_list=None, rows=50):
                if order_status_list is None:
                    # Startup open orders query
                    if trade_type == "BUY":
                        return {
                            "data": [
                                {
                                    "orderNumber": "BUY_STARTUP_DISPUTE_5",
                                    "orderStatus": "5",
                                    "totalPrice": 200000.0,
                                    "amount": 100.0,
                                    "asset": "USDT",
                                }
                            ]
                        }
                    elif trade_type == "SELL":
                        return {
                            "data": [
                                {
                                    "orderNumber": "SELL_STARTUP_DISPUTE_5",
                                    "orderStatus": "5",
                                    "totalPrice": 150000.0,
                                    "amount": 100.0,
                                    "asset": "USDT",
                                }
                            ]
                        }
                return {"data": []}

            mock_client.list_orders.side_effect = mock_list
            mock_client.get_convert_trades = AsyncMock(return_value=dict(list=[]))
            lt = LiquidityTracker(client=mock_client, db=mock_db)
            await lt.initialize(config=BotConfig(balance_ars=1000000.0))

            # La orden de compra con status 5 al arrancar debe estar en startup open orders y comprometer liquidez
            self.assertIn("BUY_STARTUP_DISPUTE_5", lt._startup_open_order_nos)
            self.assertIn("SELL_STARTUP_DISPUTE_5", lt._startup_open_order_nos)
            self.assertEqual(lt.committed_balance, 200000.0)

        asyncio.run(_run())

    def test_fix_3_reconcile_ads_internal_unites_buy_and_sell_adv_nos(self):
        """Verifica que _reconcile_ads_internal una buy_adv_nos y sell_adv_nos para el scanner."""
        async def _run():
            from main import BotEngine
            mock_db = MagicMock()
            mock_db.get_latest_benchmarks.return_value = {}
            mock_db.get_all_my_adv_nos.return_value = {"BUY_1", "BUY_2"}
            mock_db.get_all_my_sell_adv_nos.return_value = {"SELL_1", "SELL_2"}

            with patch.object(BotEngine, "__init__", lambda self: None):
                engine = BotEngine()
                engine.db = mock_db
                engine.pay_id_map = {"MP": 1}
                engine.method_groups = {1: ["MP"]}
                engine.spot_client = AsyncMock()
                engine.spot_client.get_usdt_prices.return_value = {"USDT": 1.0}
                engine.ads_manager = AsyncMock()
                engine.ads_manager.reconcile_all_ads.return_value = {"created": 0}
                engine.ads_manager.sync_my_ads.return_value = []
                engine.scanner = MagicMock()

                await engine._reconcile_ads_internal(set_online=False, calibrate=False)

                # Verificar que el scanner recibió la unión exacta
                engine.scanner.set_my_adv_nos.assert_called_with({"BUY_1", "BUY_2", "SELL_1", "SELL_2"})

        asyncio.run(_run())

    def test_fix_4_regroup_propagates_to_ads_manager_assign_groups(self):
        """Verifica que run_cycle ejecute el reagrupamiento y propague assign_groups a los anuncios reales."""
        async def _run():
            from main import BotEngine
            mock_db = MagicMock()
            mock_db.get_all_my_adv_nos.return_value = {"ADV1"}
            mock_db.get_all_my_sell_adv_nos.return_value = {"SELL1"}
            mock_db.load_bot_config.return_value = BotConfig(is_paused=False, paused_ads=[], paused_assets=[])
            mock_db.get_my_ads.return_value = []

            with patch.object(BotEngine, "__init__", lambda self: None):
                engine = BotEngine()
                engine.db = mock_db
                engine.config = mock_db.load_bot_config.return_value
                engine.method_groups = {1: ["MP"], 2: ["Santander"], 3: ["Brubank"]}
                my_ad = MyAd(adv_no="ADV1", asset="USDT", ad_group=1, current_price=1500.0, payment_methods=["Uala"])
                engine.my_ads = [my_ad]
                engine.my_sell_ads = []
                engine.ads_manager = AsyncMock()
                engine.ads_manager.is_83714_active = False
                engine.telegram = AsyncMock()
                engine.scanner = AsyncMock()
                engine.scanner.set_my_adv_nos = MagicMock()
                engine.scanner.scan_full_cycle.return_value = {
                    "rates": {}, "competitors": {}, "benchmarks": {}, "spot_prices": {"USDT": 1.0}, "volatilities": {}
                }
                engine.liquidity = MagicMock()
                engine.liquidity.balance = 500000.0
                engine.liquidity.available_balance = 500000.0
                engine.liquidity.sync_orders = AsyncMock(return_value=[])
                engine.liquidity.sync_swaps = AsyncMock(return_value=[])
                engine.liquidity.consume_incoming_orders = MagicMock(return_value=[])
                engine.liquidity.set_balance = MagicMock()
                engine.fiwind = MagicMock()
                engine.fiwind.get_usdt_bid = AsyncMock(return_value=0.0)
                engine._altcoin_notified_orders = set()
                engine.repositioner = MagicMock()
                engine.repositioner.evaluate_ad = AsyncMock(return_value=RepositionDecision(new_price=1500.0, should_pause=False))
                engine.repositioner.resolve_asset_price_collisions = MagicMock(return_value=[])
                engine.repositioner.execute_decisions = AsyncMock(return_value=[])
                engine.repositioner._paused_by_liquidity = set()
                engine.repositioner._paused_by_market_data = set()
                engine.repositioner._paused_by_antiban = set()
                engine._paused_by_antiban = set()
                engine._paused_by_liquidity = set()
                engine.assets = ["USDT"]
                engine.last_benchmarks = {}
                engine.latest_decisions = {}
                engine.cycle_count = 1
                engine.last_successful_binance_time = time.time()
                engine._last_antiban_alert_ts = 0.0
                engine._watchdog_alerted = False

                # Simular intervalo de regroup vencido (25hs > 24hs)
                engine._last_regroup = datetime.now() - timedelta(hours=25)
                engine.method_selector = AsyncMock()
                new_groups = {1: ["MP", "Uala"], 2: ["Santander"], 3: ["Brubank"]}
                engine.method_selector.regroup_if_needed.return_value = new_groups

                # Ejecutar run_cycle REAL
                await engine.run_cycle()

                # Verificar que regroup_if_needed recibió la unión de compra y venta
                engine.method_selector.regroup_if_needed.assert_called_once_with(
                    current_groups={1: ["MP"], 2: ["Santander"], 3: ["Brubank"]},
                    my_adv_nos={"ADV1", "SELL1"},
                )
                # Verificar que assign_groups fue llamado con los anuncios y nuevos grupos
                engine.ads_manager.assign_groups.assert_called_once_with(engine.my_ads, new_groups)
                self.assertEqual(engine.method_groups, new_groups)
                # Verificar que scanner recibió los adv_nos actualizados
                engine.scanner.set_my_adv_nos.assert_called_with({"ADV1", "SELL1"})

        asyncio.run(_run())

    def test_fix_5_collision_pause_sets_status_offline(self):
        """Verifica que run_cycle asigne AD_STATUS_OFFLINE (3) y pause en Binance al colisionar."""
        async def _run():
            from main import BotEngine
            mock_db = MagicMock()
            mock_db.get_all_my_adv_nos.return_value = {"ADV_COL_1"}
            mock_db.get_all_my_sell_adv_nos.return_value = set()
            mock_db.load_bot_config.return_value = BotConfig(is_paused=False, paused_ads=[], paused_assets=[])
            mock_db.get_my_ads.return_value = []

            with patch.object(BotEngine, "__init__", lambda self: None):
                engine = BotEngine()
                engine.db = mock_db
                engine.config = mock_db.load_bot_config.return_value
                ad = MyAd(adv_no="ADV_COL_1", asset="USDT", ad_group=1, current_price=1500.0, payment_methods=["MP"], status=AD_STATUS_ONLINE)
                engine.my_ads = [ad]
                engine.my_sell_ads = []
                engine.ads_manager = AsyncMock()
                engine.ads_manager.is_83714_active = False
                engine.ads_manager.pause_ad.return_value = True
                engine.telegram = AsyncMock()
                engine.scanner = AsyncMock()
                engine.scanner.set_my_adv_nos = MagicMock()
                engine.scanner.scan_full_cycle.return_value = {
                    "rates": {}, "competitors": {}, "benchmarks": {}, "spot_prices": {"USDT": 1.0}, "volatilities": {}
                }
                engine.liquidity = MagicMock()
                engine.liquidity.balance = 500000.0
                engine.liquidity.available_balance = 500000.0
                engine.liquidity.sync_orders = AsyncMock(return_value=[])
                engine.liquidity.sync_swaps = AsyncMock(return_value=[])
                engine.liquidity.consume_incoming_orders = MagicMock(return_value=[])
                engine.liquidity.set_balance = MagicMock()
                engine.fiwind = MagicMock()
                engine.fiwind.get_usdt_bid = AsyncMock(return_value=0.0)
                engine._altcoin_notified_orders = set()
                engine.method_selector = AsyncMock()
                engine.method_selector.regroup_if_needed.return_value = None
                engine.method_groups = {1: ["MP"]}
                engine.assets = ["USDT"]
                engine.last_benchmarks = {}
                engine.latest_decisions = {}
                engine.cycle_count = 1
                engine.last_successful_binance_time = time.time()
                engine._last_antiban_alert_ts = 0.0
                engine._watchdog_alerted = False
                engine._last_regroup = datetime.now()
                engine._paused_by_antiban = set()
                engine._paused_by_liquidity = set()

                engine.repositioner = MagicMock()
                dec_ok = RepositionDecision(new_price=1500.0, should_pause=False)
                engine.repositioner.evaluate_ad = AsyncMock(return_value=dec_ok)
                engine.repositioner.execute_decisions = AsyncMock(return_value=[])
                engine.repositioner._paused_by_liquidity = set()
                engine.repositioner._paused_by_market_data = set()
                engine.repositioner._paused_by_antiban = set()

                def mock_resolve(asset, evaluated, **kwargs):
                    for a, d in evaluated:
                        d.should_pause = True
                        d.reason = "collision_floor_breach_pause"
                    return []

                engine.repositioner.resolve_asset_price_collisions.side_effect = mock_resolve

                # Ejecutar run_cycle REAL
                await engine.run_cycle()

                # Verificar que pause_ad fue invocado para ADV_COL_1
                engine.ads_manager.pause_ad.assert_called_once_with("ADV_COL_1")
                # Verificar que el status del anuncio cambió a AD_STATUS_OFFLINE (3) y no a 2
                self.assertEqual(ad.status, AD_STATUS_OFFLINE)
                self.assertEqual(ad.status, 3)
                self.assertNotEqual(ad.status, 2)
                # Verificar que se registró en _paused_by_antiban
                self.assertIn("ADV_COL_1", engine._paused_by_antiban)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
