"""
Tests unitarios de verificación para las 14 correcciones de la auditoría.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from core.pricing.buy_repositioner import Repositioner
from core.market_scanner import MarketScanner
from data.database import Database
from data.models import MyAd, ExchangeRate, Benchmark, BotConfig, DetectedOrder
from telegram_bot.bot import TelegramBot


class TestAuditFixes(unittest.IsolatedAsyncioTestCase):

    def test_telegram_fail_closed_authorization(self):
        """Verifica que sin TELEGRAM_ADMIN_IDS ni _chat_id el acceso sea DENEGADO (Hallazgo #11)."""
        bot = TelegramBot(db=MagicMock())
        bot._chat_id = ""

        # Update real (no mock)
        update = MagicMock()
        type(update).__name__ = "Update"
        update.effective_user.id = 123456789
        update.effective_chat.id = 123456789

        with patch("telegram_bot.bot.TELEGRAM_ADMIN_IDS", set()):
            is_auth = bot._is_authorized(update)
            self.assertFalse(is_auth)

    def test_telegram_stop_and_parar_handlers(self):
        """Verifica que /stop y /parar estén registrados en los handlers (Hallazgo #13)."""
        import inspect
        source = inspect.getsource(TelegramBot.start)
        self.assertIn('("stop", self._cmd_power_off)', source)
        self.assertIn('("parar", self._cmd_power_off)', source)
        self.assertIn('("apagar", self._cmd_power_off)', source)

    async def test_circuit_breaker_83714_in_repositioner(self):
        """Verifica que is_83714_active freeze las evaluaciones en repositioner (Hallazgo #1)."""
        mock_ads = MagicMock()
        mock_ads.is_83714_active = True

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=MagicMock(),
            liquidity=MagicMock(available_balance=100000.0),
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )

        ad = MyAd(adv_no="ad_1", asset="USDT", ad_group=1, current_price=1500.0, status=1, payment_methods=["MercadoPagoNew"])
        decision = await repo.evaluate_ad(
            ad=ad,
            competitors={},
            benchmarks={"BANK": Benchmark("BANK", 1600.0)},
            spot_prices={"USDT": 1.0},
            config=BotConfig(),
        )

        self.assertFalse(decision.should_update)
        self.assertEqual(decision.reason, "error_83714_cooldown")

    def test_market_scanner_anti_cebo_filter_returns_none(self):
        """Verifica que si ningún competidor califica, retorne None en vez de usar cuentas dudosas (Hallazgo #2)."""
        scanner = MarketScanner(client=MagicMock(), spot_client=MagicMock(), db=MagicMock())

        # Competidores con métricas de anunciante que NO califican (órdenes < 15, tasa < 0.88)
        unqualified = [
            ExchangeRate("USDT", "MercadoPagoNew", 1650.0, 1.0, 1650.0, 1,
                         advertiser_order_count=2, advertiser_completion_rate=0.50),
            ExchangeRate("USDT", "MercadoPagoNew", 1640.0, 1.0, 1640.0, 2,
                         advertiser_order_count=5, advertiser_completion_rate=0.70),
        ]

        best = scanner.get_best_competitor(unqualified)
        self.assertIsNone(best)

    async def test_repositioner_benchmark_fallback_uses_min(self):
        """Verifica que el fallback de benchmarks use el mínimo y no el promedio (Hallazgo #4)."""
        mock_ads = MagicMock()
        mock_ads.is_83714_active = False

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=MagicMock(get_best_competitor=MagicMock(return_value=None)),
            liquidity=MagicMock(available_balance=100000.0),
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )

        ad = MyAd(adv_no="ad_1", asset="USDT", ad_group=1, current_price=1500.0, status=1, payment_methods=["MetodoRaro"])
        # Metodos que no están en LIQUID_REFERENCE_METHODS ni en ad.payment_methods
        benchmarks = {
            "MetodoA": Benchmark("MetodoA", 1700.0),
            "MetodoB": Benchmark("MetodoB", 1500.0),
        }
        config = BotConfig(margin_min=10.0)

        decision = await repo.evaluate_ad(
            ad=ad,
            competitors={},
            benchmarks=benchmarks,
            spot_prices={"USDT": 1.0},
            config=config,
        )

        # min_benchmark debe ser min(1700, 1500) = 1500, no el promedio 1600!
        # Por ende max_allowed_price debe ser 1500 - 10 = 1490
        self.assertLessEqual(decision.new_price, 1490.0)

    def test_database_load_bot_config_prioritizes_liquidity_balance(self):
        """Verifica que load_bot_config priorice el saldo auditado de liquidity sobre bot_config (Hallazgo #6)."""
        import tempfile
        import os
        from pathlib import Path

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            db = Database(db_path=Path(path))
            db.init_schema()
            # Guardar balance obsoleto en bot_config
            db.set_config("balance_ars", "1000000.0")
            # Guardar balance real auditado en liquidity
            db.save_liquidity_event(event_type="buy", balance_after=450000.0, amount_ars=550000.0)

            cfg = db.load_bot_config()
            self.assertEqual(cfg.balance_ars, 450000.0)
            db.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    async def test_pause_on_missing_spot_price(self):
        """Verifica que si no hay precio spot, should_pause sea True para no operar descalzado."""
        repo = Repositioner(
            ads_manager=MagicMock(),
            scanner=MagicMock(),
            liquidity=MagicMock(available_balance=100000.0),
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )
        ad = MyAd(adv_no="ad_btc", asset="BTC", ad_group=1, current_price=100000000.0, status=1, payment_methods=["MercadoPagoNew"])
        decision = await repo.evaluate_ad(
            ad=ad,
            competitors={},
            benchmarks={"BANK": Benchmark("BANK", 1600.0)},
            spot_prices={"BTC": 0.0},
            config=BotConfig(),
        )
        self.assertTrue(decision.should_pause)
        self.assertEqual(decision.reason, "sin_spot_price")

    async def test_pause_on_missing_benchmark(self):
        """Verifica que si no hay benchmark USDT, should_pause sea True para resguardar capital."""
        mock_fiwind = AsyncMock()
        mock_fiwind.get_usdt_bid.return_value = 0.0
        repo = Repositioner(
            ads_manager=MagicMock(),
            scanner=MagicMock(),
            liquidity=MagicMock(available_balance=100000.0),
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
            fiwind_client=mock_fiwind,
        )
        ad = MyAd(adv_no="ad_usdt", asset="USDT", ad_group=1, current_price=1500.0, status=1, payment_methods=["MercadoPagoNew"])
        decision = await repo.evaluate_ad(
            ad=ad,
            competitors={},
            benchmarks={},
            spot_prices={"USDT": 1.0},
            config=BotConfig(),
        )
        self.assertTrue(decision.should_pause)
        self.assertEqual(decision.reason, "sin_benchmark")

    async def test_margin_ceiling_enforced_in_active_war(self):
        """Verifica que si hay guerra activa pero el precio actual excede el techo, se recorte a max_allowed_price."""
        mock_war = MagicMock()
        mock_war.is_in_war.return_value = True

        repo = Repositioner(
            ads_manager=MagicMock(),
            scanner=MagicMock(),
            liquidity=MagicMock(available_balance=500000.0),
            war_detector=mock_war,
            db=MagicMock(),
        )
        # current_price 1600 > max_allowed 1500 - 10 = 1490
        ad = MyAd(adv_no="ad_war", asset="USDT", ad_group=1, current_price=1600.0, status=1, payment_methods=["MercadoPagoNew"])
        decision = await repo.evaluate_ad(
            ad=ad,
            competitors={("USDT", "MercadoPagoNew"): [ExchangeRate("USDT", "MercadoPagoNew", 1620.0, 1.0, 1620.0, 1)]},
            benchmarks={"MercadoPagoNew": Benchmark("MercadoPagoNew", 1500.0)},
            spot_prices={"USDT": 1.0},
            config=BotConfig(margin_min=10.0),
        )
        self.assertTrue(decision.should_update)
        self.assertEqual(decision.new_price, 1490.0)
        self.assertIn("margin_ceiling_cut", decision.reason)

    async def test_margin_ceiling_enforced_in_api_error_cooldown(self):
        """Verifica que si el anuncio está en cooldown pero su precio viola el margen, se fuerce la bajada."""
        repo = Repositioner(
            ads_manager=MagicMock(),
            scanner=MagicMock(),
            liquidity=MagicMock(available_balance=500000.0),
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )
        import time
        repo._error_cooldown_until["ad_cd"] = time.time() + 300.0

        ad = MyAd(adv_no="ad_cd", asset="USDT", ad_group=1, current_price=1550.0, status=1, payment_methods=["MercadoPagoNew"])
        decision = await repo.evaluate_ad(
            ad=ad,
            competitors={},
            benchmarks={"MercadoPagoNew": Benchmark("MercadoPagoNew", 1500.0)},
            spot_prices={"USDT": 1.0},
            config=BotConfig(margin_min=10.0),
        )
        self.assertTrue(decision.should_update)
        self.assertEqual(decision.new_price, 1490.0)
        self.assertIn("margin_ceiling_cut", decision.reason)

    def test_resolve_collisions_permits_downward_cut_for_ad_above_ceiling(self):
        """Verifica que resolve_asset_price_collisions no fije como ancla un anuncio que supera el techo."""
        repo = Repositioner(
            ads_manager=MagicMock(),
            scanner=MagicMock(),
            liquidity=MagicMock(available_balance=500000.0),
            war_detector=MagicMock(),
            db=MagicMock(),
        )
        repo._asset_price_bounds["USDT"] = (1000.0, 1490.0)

        ad = MyAd(adv_no="ad_high", asset="USDT", ad_group=1, current_price=1600.0, status=1, payment_methods=["MercadoPagoNew"])
        from data.models import RepositionDecision
        dec = RepositionDecision()
        dec.reason = "war_detected"
        dec.should_update = False

        resolved = repo.resolve_asset_price_collisions(
            asset="USDT",
            evaluated=[(ad, dec)],
            config=BotConfig(),
        )
        self.assertEqual(len(resolved), 1)
        res_ad, res_dec = resolved[0]
        self.assertTrue(res_dec.should_update)
        self.assertLessEqual(res_dec.new_price, 1490.0)

    async def test_main_run_cycle_pauses_ad_when_balance_below_floor(self):
        """Verifica que run_cycle pause en Binance el anuncio cuando falta saldo disponible."""
        from main import BotEngine
        with patch.object(BotEngine, "__init__", lambda self: None):
            engine = BotEngine()
            engine.db = MagicMock()
            engine.config = BotConfig(is_paused=False, paused_ads=[], paused_assets=[])
            engine.db.load_bot_config.return_value = engine.config
            engine.db.get_my_ads.return_value = []
            engine.ads_manager = MagicMock()
            engine.ads_manager.pause_ad = AsyncMock(return_value=True)
            engine.ads_manager.is_83714_active = False
            engine.telegram = MagicMock()
            engine.telegram.notify = AsyncMock()
            engine.telegram.update_live_dashboard = AsyncMock()
            engine.scanner = MagicMock()
            engine.scanner.scan_full_cycle = AsyncMock(return_value={
                "rates": {},
                "competitors": {},
                "benchmarks": {"BANK": Benchmark("BANK", 1600.0)},
                "spot_prices": {"USDT": 1.0},
                "volatilities": {},
            })
            engine.scanner.set_my_adv_nos = MagicMock()
            engine.liquidity = MagicMock()
            engine.liquidity.balance = 500.0
            engine.liquidity.available_balance = 500.0
            engine.liquidity.sync_orders = AsyncMock(return_value=[])
            engine.liquidity.sync_swaps = AsyncMock(return_value=[])
            engine.fiwind = MagicMock()
            engine.fiwind.get_usdt_bid = AsyncMock(return_value=0.0)
            engine.method_selector = MagicMock()
            engine.method_selector.regroup_if_needed = AsyncMock(return_value=None)
            engine.war_detector = MagicMock(is_in_war=MagicMock(return_value=False))
            engine.repositioner = Repositioner(
                engine.ads_manager, engine.scanner, engine.liquidity, engine.war_detector, engine.db
            )
            engine.cycle_count = 1
            engine.method_groups = {1: ["BANK"]}
            engine.assets = ["USDT"]
            ad = MyAd(adv_no="ad_low_bal", asset="USDT", ad_group=1, current_price=1500.0, status=1, payment_methods=["BANK"])
            engine.my_ads = [ad]
            engine.latest_decisions = {}
            engine._last_antiban_alert_ts = 0.0
            engine._watchdog_alerted = False
            engine.last_successful_binance_time = time.time()
            engine._last_regroup = datetime.now()

            await engine.run_cycle()

            engine.ads_manager.pause_ad.assert_awaited_with("ad_low_bal")
            self.assertEqual(ad.status, 3)
            self.assertIn("ad_low_bal", engine.repositioner._paused_by_liquidity)

    async def test_main_run_cycle_pauses_ad_on_antiban_critical_violation(self):
        """Verifica que run_cycle pause en Binance los anuncios del activo con violaciones críticas de AntiBanValidator."""
        from main import BotEngine
        from core.antiban_validator import AntiBanViolation
        with patch.object(BotEngine, "__init__", lambda self: None):
            engine = BotEngine()
            engine.db = MagicMock()
            engine.config = BotConfig(is_paused=False, paused_ads=[], paused_assets=[])
            engine.db.load_bot_config.return_value = engine.config
            engine.db.get_my_ads.return_value = []
            engine.ads_manager = MagicMock()
            engine.ads_manager.pause_ad = AsyncMock(return_value=True)
            engine.ads_manager.is_83714_active = False
            engine.telegram = MagicMock()
            engine.telegram.notify = AsyncMock()
            engine.telegram.update_live_dashboard = AsyncMock()
            engine.scanner = MagicMock()
            engine.scanner.scan_full_cycle = AsyncMock(return_value={
                "rates": {},
                "competitors": {},
                "benchmarks": {"BANK": Benchmark("BANK", 1600.0)},
                "spot_prices": {"USDT": 1.0},
                "volatilities": {},
            })
            engine.scanner.set_my_adv_nos = MagicMock()
            engine.liquidity = MagicMock()
            engine.liquidity.balance = 500000.0
            engine.liquidity.available_balance = 500000.0
            engine.liquidity.sync_orders = AsyncMock(return_value=[])
            engine.liquidity.sync_swaps = AsyncMock(return_value=[])
            engine.fiwind = MagicMock()
            engine.fiwind.get_usdt_bid = AsyncMock(return_value=0.0)
            engine.method_selector = MagicMock()
            engine.method_selector.regroup_if_needed = AsyncMock(return_value=None)
            engine.war_detector = MagicMock(is_in_war=MagicMock(return_value=False))
            engine.repositioner = Repositioner(
                engine.ads_manager, engine.scanner, engine.liquidity, engine.war_detector, engine.db
            )
            engine.cycle_count = 1
            engine.method_groups = {1: ["BANK"]}
            engine.assets = ["USDT"]
            ad = MyAd(adv_no="ad_viol", asset="USDT", ad_group=1, current_price=1500.0, status=1, payment_methods=["BANK"])
            engine.my_ads = [ad]
            engine.latest_decisions = {}
            engine._last_antiban_alert_ts = 0.0
            engine._watchdog_alerted = False
            engine.last_successful_binance_time = time.time()
            engine._last_regroup = datetime.now()

            with patch("core.antiban_validator.AntiBanValidator.audit_asset_decisions", return_value=[
                AntiBanViolation(rule_id="RULE_5_1_3_SEPARATION", asset="USDT", group=1, message="test collision", severity="CRITICAL")
            ]):
                await engine.run_cycle()

            engine.ads_manager.pause_ad.assert_awaited_with("ad_viol")
            self.assertEqual(ad.status, 3)
            self.assertIn("ad_viol", engine.repositioner._paused_by_antiban)

    async def test_main_run_cycle_resumes_ad_when_liquidity_recovers(self):
        """Verifica que run_cycle reactive en Binance un anuncio pausado cuando el saldo se normaliza."""
        from main import BotEngine
        with patch.object(BotEngine, "__init__", lambda self: None):
            engine = BotEngine()
            engine.db = MagicMock()
            engine.config = BotConfig(is_paused=False, paused_ads=[], paused_assets=[])
            engine.db.load_bot_config.return_value = engine.config
            engine.db.get_my_ads.return_value = []
            engine.ads_manager = MagicMock()
            engine.ads_manager.pause_ad = AsyncMock(return_value=True)
            engine.ads_manager.resume_ad = AsyncMock(return_value=True)
            engine.ads_manager.update_ad_params = AsyncMock(return_value=True)
            engine.ads_manager.is_83714_active = False
            engine.telegram = MagicMock()
            engine.telegram.notify = AsyncMock()
            engine.telegram.update_live_dashboard = AsyncMock()
            engine.scanner = MagicMock()
            engine.scanner.scan_full_cycle = AsyncMock(return_value={
                "rates": {},
                "competitors": {},
                "benchmarks": {"BANK": Benchmark("BANK", 1600.0)},
                "spot_prices": {"USDT": 1.0},
                "volatilities": {},
            })
            engine.scanner.set_my_adv_nos = MagicMock()
            engine.liquidity = MagicMock()
            engine.liquidity.balance = 500000.0
            engine.liquidity.available_balance = 500000.0
            engine.liquidity.sync_orders = AsyncMock(return_value=[])
            engine.liquidity.sync_swaps = AsyncMock(return_value=[])
            engine.fiwind = MagicMock()
            engine.fiwind.get_usdt_bid = AsyncMock(return_value=0.0)
            engine.method_selector = MagicMock()
            engine.method_selector.regroup_if_needed = AsyncMock(return_value=None)
            engine.war_detector = MagicMock(is_in_war=MagicMock(return_value=False))
            engine.repositioner = Repositioner(
                engine.ads_manager, engine.scanner, engine.liquidity, engine.war_detector, engine.db
            )
            # Anuncio previamente pausado por liquidez
            engine.repositioner._paused_by_liquidity.add("ad_recovered")
            engine.cycle_count = 1
            engine.method_groups = {1: ["BANK"]}
            engine.assets = ["USDT"]
            ad = MyAd(adv_no="ad_recovered", asset="USDT", ad_group=1, current_price=1500.0, status=3, payment_methods=["BANK"])
            engine.my_ads = [ad]
            engine.latest_decisions = {}
            engine._last_antiban_alert_ts = 0.0
            engine._watchdog_alerted = False
            engine.last_successful_binance_time = time.time()
            engine._last_regroup = datetime.now()

            await engine.run_cycle()

            engine.ads_manager.resume_ad.assert_awaited_with("ad_recovered")
            self.assertEqual(ad.status, 1)
            self.assertNotIn("ad_recovered", engine.repositioner._paused_by_liquidity)

    async def test_offline_orders_reconciliation_in_liquidity_tracker(self):
        """Verifica que LiquidityTracker.initialize() concilie ventas completadas offline e hidrate el saldo."""
        from core.liquidity.liquidity_manager import LiquidityTracker
        from data.models import BotConfig

        mock_client = MagicMock()
        mock_client.list_orders = AsyncMock(side_effect=lambda trade_type, rows=50, order_status_list=None: {
            "data": [
                {
                    "orderNumber": "offline_order_123",
                    "tradeType": "SELL",
                    "asset": "USDT",
                    "totalPrice": "150000.0",
                    "amount": "100.0",
                    "unitPrice": "1500.0",
                    "orderStatus": 4,  # COMPLETED
                    "createTime": 1710000000000,
                }
            ] if order_status_list == [4] and trade_type == "SELL" else []
        })
        mock_db = MagicMock()
        mock_db.get_all_detected_order_nos.return_value = {"prev_known"}
        config = BotConfig(balance_ars=300000.0)

        tracker = LiquidityTracker(client=mock_client, db=mock_db)
        await tracker.initialize(config)

        # Debe haber acreditado los 150.000 ARS de la venta offline: 300.000 + 150.000 = 450.000
        self.assertEqual(tracker.balance, 450000.0)
        mock_db.save_detected_order.assert_called_once()
        saved_order = mock_db.save_detected_order.call_args[0][0]
        self.assertEqual(saved_order.order_no, "offline_order_123")
        mock_db.set_config.assert_called_with("balance_ars", "450000.0")

    def test_ad_replenishment_when_depleted(self):
        """Verifica que un anuncio con surplus menor al mínimo se recapitalice y sus límites no superen init_amount * price."""
        from core.pricing.buy_repositioner import Repositioner
        from data.models import RepositionDecision

        mock_liq = MagicMock()
        mock_liq.available_balance = 750000.0
        repo = Repositioner(
            ads_manager=MagicMock(),
            scanner=MagicMock(),
            liquidity=mock_liq,
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )

        # Anuncio con 70 USDT de remanente (por debajo del piso de 100 USDT)
        ad = MyAd(
            adv_no="depleted_ad",
            asset="USDT",
            ad_group=1,
            current_price=1500.0,
            init_amount=500.0,
            surplus_amount=70.0,
            min_trans_amount=15000.0,
            max_trans_amount=500000.0,
            payment_methods=["BANK"],
            status=3,
        )
        decision = RepositionDecision(new_price=1500.0, should_update=False)
        config = BotConfig(price_step=0.01)

        repo._recompute_ad_amounts_and_limits(ad, decision, 1500.0, config)

        self.assertTrue(decision.should_update)
        self.assertIsNotNone(decision.new_init_amount)
        self.assertGreaterEqual(decision.new_init_amount, 100.0)
        # Asegurar invariante anti-triángulo rojo: max_trans <= effective_init * price
        effective_init = decision.new_init_amount
        self.assertLessEqual(decision.new_max_trans_amount, effective_init * 1500.0)
        self.assertGreaterEqual(decision.new_max_trans_amount, decision.new_min_trans_amount)

    def test_group_hierarchy_preserved_in_collision_resolution(self):
        """Verifica que resolve_asset_price_collisions ordene y resuelva estrictamente por grupo (G1 > G2 > G3)."""
        from core.pricing.buy_repositioner import Repositioner
        from data.models import RepositionDecision

        repo = Repositioner(
            ads_manager=MagicMock(),
            scanner=MagicMock(),
            liquidity=MagicMock(available_balance=1000000.0),
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )

        # Supongamos que los precios del mercado invertían las candidaturas: G2 proponía 1590.20 y G1 1590.10
        ad_g1 = MyAd(adv_no="g1", asset="USDT", ad_group=1, current_price=1590.00, status=1, payment_methods=["BANK"])
        ad_g2 = MyAd(adv_no="g2", asset="USDT", ad_group=2, current_price=1589.50, status=1, payment_methods=["BANK"])
        ad_g3 = MyAd(adv_no="g3", asset="USDT", ad_group=3, current_price=1589.00, status=1, payment_methods=["BANK"])

        dec_g1 = RepositionDecision(new_price=1590.10, should_update=True)
        dec_g2 = RepositionDecision(new_price=1590.20, should_update=True)
        dec_g3 = RepositionDecision(new_price=1590.15, should_update=True)

        config = BotConfig(price_step=0.01)
        pairs = [(ad_g1, dec_g1), (ad_g2, dec_g2), (ad_g3, dec_g3)]

        resolved = repo.resolve_asset_price_collisions(
            asset="USDT",
            evaluated=pairs,
            config=config,
            all_asset_ads=[ad_g1, ad_g2, ad_g3],
            allow_offline=False,
        )

        resolved_map = {a.adv_no: d for a, d in resolved}
        p_g1 = resolved_map["g1"].new_price
        p_g2 = resolved_map["g2"].new_price
        p_g3 = resolved_map["g3"].new_price

        # La jerarquía G1 > G2 > G3 debe respetarse estrictamente y estar separada por al menos 0.16
        self.assertGreaterEqual(p_g1 - p_g2, 0.16)
        self.assertGreaterEqual(p_g2 - p_g3, 0.16)
        self.assertEqual(len(resolved), 3)

    async def test_reconcile_ads_triggers_calibration(self):
        """Verifica que reconcile_ads(calibrate=True) ejecute calibración en frío de precios y cantidades."""
        from main import BotEngine

        with patch("main.Database"), patch("main.BinanceClient"), patch("main.TelegramBot"):
            engine = BotEngine()
            engine.get_pay_id_map = AsyncMock(return_value={})
            engine.spot_client = MagicMock(get_usdt_prices=AsyncMock(return_value={"USDT": 1.0}))
            engine.db = MagicMock(get_latest_benchmarks=MagicMock(return_value={}), get_all_my_adv_nos=MagicMock(return_value=set()))
            engine.ads_manager = MagicMock(
                reconcile_all_ads=AsyncMock(return_value={"verified": 42}),
                sync_my_ads=AsyncMock(return_value=[]),
            )
            engine.scanner = MagicMock()
            engine._calibrate_internal = AsyncMock(return_value=42)

            stats = await engine.reconcile_ads(set_online=False, calibrate=True)

            engine.ads_manager.reconcile_all_ads.assert_awaited_once()
            engine._calibrate_internal.assert_awaited_once()
            self.assertEqual(stats.get("calibrated"), 42)

    async def test_spot_client_compact_symbols_and_resilience(self):
        """Verifica que SpotClient maneje fallos de red sin lanzar excepciones que aborten el escaneo."""
        from core.spot_client import SpotClient

        client = SpotClient()
        mock_session = MagicMock()
        mock_session.closed = False
        client._session = mock_session

        # Simular fallo en la llamada HTTP
        mock_session.get.side_effect = asyncio.TimeoutError("Network timeout")

        # get_all_prices no debe lanzar TimeoutError
        prices = await client.get_all_prices()
        self.assertEqual(prices, {})

        # get_usdt_prices no debe lanzar TimeoutError
        usdt_prices = await client.get_usdt_prices(["BTC", "ETH"])
        self.assertEqual(usdt_prices, {})

    async def test_market_scanner_spot_prices_cache_fallback(self):
        """Verifica que MarketScanner conserve los precios spot anteriores ante microcortes."""
        from core.market_scanner import MarketScanner

        mock_spot = MagicMock()
        mock_spot.get_usdt_prices = AsyncMock(return_value={"BTC": 80000.0, "ETH": 2500.0})
        mock_db = MagicMock()

        scanner = MarketScanner(client=MagicMock(), spot_client=mock_spot, db=mock_db)

        # Primer escaneo exitoso
        p1 = await scanner.get_spot_prices(["BTC", "ETH"])
        self.assertEqual(p1["BTC"], 80000.0)

        # Segundo escaneo falla con timeout
        mock_spot.get_usdt_prices = AsyncMock(side_effect=asyncio.TimeoutError("Timeout"))
        p2 = await scanner.get_spot_prices(["BTC", "ETH"])
        self.assertEqual(p2["BTC"], 80000.0)
        self.assertEqual(p2["ETH"], 2500.0)

    def test_tray_icon_quit_thread_decoupled(self):
        """Verifica que _handle_quit invoque on_quit en un hilo secundario sin lanzar SystemExit a pystray."""
        from core.tray_icon import BotTrayIcon

        quit_called = False
        def mock_quit():
            nonlocal quit_called
            quit_called = True

        tray = BotTrayIcon(on_show_logs=MagicMock(), on_quit=mock_quit)
        tray._handle_quit()
        time.sleep(0.1)
        self.assertTrue(quit_called)

    def test_format_altcoin_buy_swap_alert(self):
        """Verifica que format_altcoin_buy_swap_alert calcule correctamente TC implícito y USDT proyectados."""
        from telegram_bot.formatters import format_altcoin_buy_swap_alert

        order = DetectedOrder(
            order_no="order_sol_123",
            adv_no="adv_sol_456",
            asset="SOL",
            trade_type="BUY",
            amount_crypto=5.0,
            amount_ars=500000.0,
            price=100000.0,  # 100k ARS/SOL
            tc_implicito=1000.0,
            payment_method="MercadoPagoNew",
            counterparty="VendedorCrypto",
            status="4",
            timestamp=datetime.now(),
        )

        # Spot de SOL = 100 USDT -> TC implícito = 100,000 / 100 = 1,000 ARS/USDT
        # USDT proyectados = 5.0 SOL * 100 = 500 USDT
        # USDT venta benchmark = 1,600 ARS -> Spread = +600 ARS/USDT
        # Ganancia neta = 500 USDT * 1,600 = 800,000 - 500,000 = 300,000 ARS
        text = format_altcoin_buy_swap_alert(order, spot_price=100.0, usdt_sell_tc=1600.0)

        self.assertIn("SOL", text)
        self.assertIn("$100.00 USDT", text)
        self.assertIn("$1,000.00 ARS/USDT", text)
        self.assertIn("500.00 USDT", text)
        self.assertIn("+$600.00/USDT", text)
        self.assertIn("+$300,000 ARS", text)
        self.assertIn("SWAP RECOMENDADO A USDT", text)

    async def test_notify_altcoin_buy_order_buttons(self):
        """Verifica que notify_altcoin_buy_order construya el mensaje con botones de Convert y Pausar."""
        from telegram_bot.bot import TelegramBot

        mock_bot_api = AsyncMock()
        bot = TelegramBot(db=MagicMock())
        bot._chat_id = "123456"
        bot._app = MagicMock()
        bot._app.bot = mock_bot_api

        order = DetectedOrder(
            order_no="order_btc_999",
            adv_no="adv_btc_888",
            asset="BTC",
            trade_type="BUY",
            amount_crypto=0.01,
            amount_ars=1300000.0,
            price=130000000.0,
            tc_implicito=1585.0,
            payment_method="SantanderArgentina",
            counterparty="Trader1",
            status="4",
            timestamp=datetime.now(),
        )

        await bot.notify_altcoin_buy_order(order, spot_price=82000.0, usdt_sell_tc=1610.0)

        mock_bot_api.send_message.assert_awaited_once()
        kwargs = mock_bot_api.send_message.await_args.kwargs
        self.assertEqual(kwargs["chat_id"], "123456")
        self.assertIn("BTC", kwargs["text"])

        reply_markup = kwargs["reply_markup"]
        buttons = [btn for row in reply_markup.inline_keyboard for btn in row]

        # Verificar botón con URL de Binance Convert
        convert_btn = next((b for b in buttons if "Binance Convert" in b.text), None)
        self.assertIsNotNone(convert_btn)
        self.assertIn("convert?from=BTC&to=USDT", convert_btn.url)

        # Verificar botón para pausar anuncio
        pause_btn = next((b for b in buttons if "Pausar Anuncio BTC" in b.text), None)
        self.assertIsNotNone(pause_btn)
        self.assertEqual(pause_btn.callback_data, "alt_pause_BTC_adv_btc_888")

        # Verificar botón de Cerrar Alerta
        close_btn = next((b for b in buttons if "Cerrar Alerta" in b.text), None)
        self.assertIsNotNone(close_btn)
        self.assertEqual(close_btn.callback_data, "alt_close_order_btc_999_BTC")

    async def test_liquidity_tracker_consume_incoming_orders(self):
        """Verifica que LiquidityTracker detecte órdenes entrantes (status 1) sin afectar balance nominal."""
        from core.liquidity.liquidity_manager import LiquidityTracker
        mock_client = AsyncMock()

        async def mock_list(trade_type="BUY", order_status_list=None, rows=50):
            if trade_type == "BUY" and order_status_list in ([1, 2], [1, 2, 3, 5]):
                return {
                    "data": [
                        {
                            "orderNumber": "inc_order_sol_1",
                            "advNo": "adv_sol_1",
                            "asset": "SOL",
                            "tradeType": "BUY",
                            "amount": 2.5,
                            "totalPrice": 250000.0,
                            "unitPrice": 100000.0,
                            "orderStatus": 1,
                            "sellerNickname": "VendorSOL",
                            "payType": "MercadoPago",
                        }
                    ]
                }
            return {"data": []}

        mock_client.list_orders.side_effect = mock_list
        lt = LiquidityTracker(mock_client, db=MagicMock())
        lt._balance = 500000.0

        res = await lt.sync_orders(spot_prices={"SOL": 100.0})
        # La orden abierta compromete liquidez pero no figura como completada:
        self.assertEqual(len(res), 0)
        self.assertEqual(lt.committed_balance, 250000.0)
        self.assertEqual(lt.balance, 500000.0)

        # Se obtiene en incoming_orders:
        incoming = lt.consume_incoming_orders()
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0].order_no, "inc_order_sol_1")
        self.assertEqual(incoming[0].status, "1")
        self.assertEqual(incoming[0].tc_implicito, 1000.0)

        # Consumir de nuevo devuelve vacío:
        self.assertEqual(len(lt.consume_incoming_orders()), 0)

    def test_cumulative_init_amount_on_partially_filled_ad(self):
        """Verifica que al reponer un anuncio con ejecuciones previas, new_init_amount sea acumulativo (Anti-187040 y Anti-187006)."""
        from core.pricing.buy_repositioner import Repositioner, RepositionDecision
        from core.antiban_validator import AntiBanValidator

        repo = Repositioner(
            ads_manager=MagicMock(),
            scanner=MagicMock(),
            liquidity=MagicMock(available_balance=979268.0),
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )

        # Anuncio BTC con 0.009758 inicial, pero casi todo ejecutado (quedan 0.00000611 BTC = ~800 ARS)
        ad = MyAd(
            adv_no="10000000000000000001",
            asset="BTC",
            ad_group=1,
            current_price=132000000.0,
            status=1,
            payment_methods=["MercadoPagoNew"],
            init_amount=0.009758,
            surplus_amount=0.00000611,
            min_trans_amount=440671.0,
            max_trans_amount=969476.0,
        )

        decision = RepositionDecision()
        final_price = 132000000.0
        config = BotConfig(balance_ars=979268.0)

        repo._recompute_ad_amounts_and_limits(ad, decision, final_price, config)

        # Lo ejecutado es ~0.00975189 BTC
        executed = 0.009758 - 0.00000611
        # Con $979,268 ARS y precio 132M, target_amount = 979268 / 132000000 = 0.007419 BTC
        self.assertIsNotNone(decision.new_init_amount)
        self.assertGreater(decision.new_init_amount, executed)
        self.assertGreater(decision.new_init_amount, ad.init_amount)

        # El nuevo excedente tradable proyectado es target_amount
        target_amount = round(decision.new_init_amount - executed, 6)
        self.assertAlmostEqual(target_amount, 979268.0 / 132000000.0, places=4)

        # Los límites no pueden superar la capacidad fresca
        self.assertIsNotNone(decision.new_max_trans_amount)
        self.assertLessEqual(decision.new_max_trans_amount, target_amount * final_price)
        self.assertLessEqual(decision.new_min_trans_amount, decision.new_max_trans_amount)

        # AntiBanValidator debe validar con 0 violaciones críticas
        validator = AntiBanValidator()
        violations = validator.audit_asset_decisions("BTC", [(ad, decision)], spot_price=85000.0, fiat_rate=1552.94)
        self.assertEqual(len(violations), 0)

    def test_exhausted_ad_pauses_when_no_liquidity(self):
        """Verifica que un anuncio con remanente agotado y sin saldo ARS para reponer se pause preventivamente (Anti-187006)."""
        from core.pricing.buy_repositioner import Repositioner, RepositionDecision

        repo = Repositioner(
            ads_manager=MagicMock(),
            scanner=MagicMock(),
            liquidity=MagicMock(available_balance=0.0),
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )

        # Anuncio con surplusAmount de $800 ARS y min_trans de $440k
        ad = MyAd(
            adv_no="10000000000000000001",
            asset="BTC",
            ad_group=1,
            current_price=132000000.0,
            status=1,
            payment_methods=["MercadoPagoNew"],
            init_amount=0.009758,
            surplus_amount=0.00000611,
            min_trans_amount=440671.0,
            max_trans_amount=969476.0,
        )

        decision = RepositionDecision()
        final_price = 133000000.0  # Cambio de precio en el mercado
        config = BotConfig(balance_ars=0.0)

        repo._recompute_ad_amounts_and_limits(ad, decision, final_price, config)

        self.assertTrue(decision.should_pause)
        self.assertFalse(decision.should_update)
        self.assertIn("stock_agotado_sin_saldo", decision.pause_reason)

    def test_antiban_validator_detects_187040_and_187006(self):
        """Verifica que AntiBanValidator detecte proactivamente violaciones de reglas 187040 y 187006."""
        from core.pricing.buy_repositioner import RepositionDecision
        from core.antiban_validator import AntiBanValidator

        validator = AntiBanValidator()
        ad = MyAd(
            adv_no="ad_btc_test",
            asset="BTC",
            ad_group=1,
            current_price=130000000.0,
            status=1,
            payment_methods=["MercadoPagoNew"],
            init_amount=0.01,
            surplus_amount=0.001,  # 0.009 ya ejecutado
            min_trans_amount=10000.0,
            max_trans_amount=500000.0,
        )

        # Caso 1: new_init_amount (0.005) < executed (0.009) -> Error 187040
        bad_dec_187040 = RepositionDecision(
            should_update=True,
            new_price=130000000.0,
            new_init_amount=0.005,
        )
        violations = validator.audit_asset_decisions("BTC", [(ad, bad_dec_187040)], spot_price=85000.0)
        rule_ids = [v.rule_id for v in violations]
        self.assertIn("RULE_ANTI_187040_INIT_AMOUNT_LT_EXECUTED", rule_ids)

        # Caso 2: minSingleTransAmount ($500,000) > remanente disponible (0.001 BTC * 130M = $130,000) -> Error 187006
        bad_dec_187006 = RepositionDecision(
            should_update=True,
            new_price=130000000.0,
            new_min_trans_amount=500000.0,
        )
        violations2 = validator.audit_asset_decisions("BTC", [(ad, bad_dec_187006)], spot_price=85000.0)
        rule_ids2 = [v.rule_id for v in violations2]
        self.assertIn("RULE_ANTI_187006_MIN_TRANS_GT_CAPACITY", rule_ids2)

    async def test_binance_client_session_auto_reset_and_sync_time_cooldown(self):
        """Verifica que BinanceClient reinicie su ClientSession tras 3 fallos de red y evite estampidas en sync_time."""
        import aiohttp
        from core.network.binance_api import BinanceClient

        client = BinanceClient(api_key="k", secret_key="s")
        real_session = await client._get_session()
        self.assertIsInstance(real_session, aiohttp.ClientSession)
        self.assertFalse(real_session.closed)

        # Simular 3 errores de red y llamar a _reset_session
        client._consecutive_net_errors = 3
        await client._reset_session()
        self.assertIsNone(client._session)
        self.assertTrue(real_session.closed)
        self.assertEqual(client._consecutive_net_errors, 0)

        # Nueva sesión limpia al volver a pedirla
        new_session = await client._get_session()
        self.assertIsNot(new_session, real_session)
        self.assertFalse(new_session.closed)

        # Verificar cooldown anti-estampida en sync_time()
        client._last_time_sync_attempt = time.time()
        client._time_offset = 1234
        offset = await client.sync_time(force=False)
        self.assertEqual(offset, 1234)

        await client.close()

    async def test_watchdog_auto_recovery_on_connection_restored(self):
        """Verifica que cuando vuelve la conexión tras un Watchdog, el bot reactive is_paused=False y reanude anuncios."""
        from main import BotEngine
        from core.pricing.buy_repositioner import Repositioner
        with patch.object(BotEngine, "__init__", lambda self: None):
            engine = BotEngine()
            engine.db = MagicMock()
            engine.config = BotConfig(is_paused=True, paused_ads=[], paused_assets=[])
            engine.db.load_bot_config.return_value = engine.config
            engine.db.get_my_ads.return_value = []
            engine.ads_manager = MagicMock()
            engine.ads_manager.pause_ad = AsyncMock(return_value=True)
            engine.ads_manager.resume_ad = AsyncMock(return_value=True)
            engine.ads_manager.resume_all = AsyncMock(return_value=1)
            engine.ads_manager.update_ad_params = AsyncMock(return_value=True)
            engine.ads_manager.is_83714_active = False
            engine.telegram = MagicMock()
            engine.telegram.notify = AsyncMock()
            engine.telegram.update_live_dashboard = AsyncMock()
            engine.scanner = MagicMock()
            engine.scanner.scan_full_cycle = AsyncMock(return_value={
                "rates": {},
                "competitors": {},
                "benchmarks": {"BANK": Benchmark("BANK", 1600.0)},
                "spot_prices": {"USDT": 1.0},
                "volatilities": {},
            })
            engine.scanner.set_my_adv_nos = MagicMock()
            engine.liquidity = MagicMock()
            engine.liquidity.balance = 500000.0
            engine.liquidity.available_balance = 500000.0
            engine.liquidity.sync_orders = AsyncMock(return_value=[])
            engine.liquidity.consume_incoming_orders = MagicMock(return_value=[])
            engine.liquidity.sync_swaps = AsyncMock(return_value=[])
            engine.fiwind = MagicMock()
            engine.fiwind.get_usdt_bid = AsyncMock(return_value=0.0)
            engine.method_selector = MagicMock()
            engine.method_selector.regroup_if_needed = AsyncMock(return_value=None)
            engine.war_detector = MagicMock(is_in_war=MagicMock(return_value=False))
            engine.repositioner = Repositioner(
                engine.ads_manager, engine.scanner, engine.liquidity, engine.war_detector, engine.db
            )
            engine.cycle_count = 1
            engine.method_groups = {1: ["BANK"]}
            engine.assets = ["USDT"]
            ad = MyAd(adv_no="ad_wd", asset="USDT", ad_group=1, current_price=1500.0, status=3, payment_methods=["BANK"])
            engine.my_ads = [ad]
            engine.latest_decisions = {}
            engine._last_antiban_alert_ts = 0.0
            engine._watchdog_alerted = True
            engine._paused_by_watchdog = True
            engine._state_change_callbacks = []
            engine.shutdown_event = asyncio.Event()
            engine.last_successful_binance_time = time.time() - 400
            engine._last_regroup = datetime.now()

            await engine.run_cycle()

            self.assertFalse(engine.config.is_paused)
            self.assertFalse(engine._watchdog_alerted)
            self.assertFalse(engine._paused_by_watchdog)
            engine.ads_manager.resume_all.assert_awaited_once()

    def test_compact_market_intel_upsert_and_query(self):
        """Verifica que record_compact_market_intel consolide resúmenes horarios y perfiles de competidores sin duplicar filas."""
        import os
        import tempfile
        from pathlib import Path
        from data.database import Database

        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        db = Database(db_path=Path(temp_path))
        db.init_schema()
        try:
            dt1 = datetime(2026, 10, 11, 16, 10, 0)
            dt2 = datetime(2026, 10, 11, 16, 25, 0)

            comp_cycle_1 = {
                ("USDT", "MercadoPagoNew"): [
                    ExchangeRate("USDT", "MercadoPagoNew", 1500.0, 1.0, 1500.0, 1, "adv_A", "TraderAlpha", 0.98, 250),
                    ExchangeRate("USDT", "MercadoPagoNew", 1495.0, 1.0, 1495.0, 2, "adv_B", "TraderBeta", 0.95, 120),
                ]
            }
            comp_cycle_2 = {
                ("USDT", "MercadoPagoNew"): [
                    ExchangeRate("USDT", "MercadoPagoNew", 1510.0, 1.0, 1510.0, 1, "adv_A", "TraderAlpha", 0.99, 260),
                    ExchangeRate("USDT", "MercadoPagoNew", 1502.0, 1.0, 1502.0, 2, "adv_B", "TraderBeta", 0.95, 125),
                ]
            }

            db.record_compact_market_intel(comp_cycle_1, {"USDT": 1.0}, now_dt=dt1)
            db.record_compact_market_intel(comp_cycle_2, {"USDT": 1.0}, now_dt=dt2)

            summary = db.get_market_hourly_summary("USDT")
            self.assertEqual(len(summary), 1)
            self.assertEqual(summary[0]["hour_bucket"], "2026-10-11 16:00")
            self.assertEqual(summary[0]["samples_count"], 2)
            self.assertAlmostEqual(summary[0]["best_price_avg"], 1505.0, places=2)
            self.assertAlmostEqual(summary[0]["best_price_max"], 1510.0, places=2)

            profiles = db.get_top_competitor_profiles()
            self.assertEqual(len(profiles), 2)
            self.assertEqual(profiles[0]["advertiser_no"], "adv_A")
            self.assertEqual(profiles[0]["times_top1"], 2)
            self.assertEqual(profiles[0]["times_seen"], 2)
            self.assertEqual(profiles[0]["max_order_count"], 260)
        finally:
            db.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_multigroup_upward_passive_hysteresis_hold(self):
        """[BUG-A1] Verifica que G1, G2 y G3 mantengan passive_hysteresis_hold simultáneamente ante una micro-subida pasiva (+$0.02 ARS)."""
        from core.pricing.buy_repositioner import RepositionDecision

        repo = Repositioner(
            ads_manager=MagicMock(),
            scanner=MagicMock(),
            liquidity=MagicMock(available_balance=0.0),
            war_detector=MagicMock(),
            db=MagicMock(),
        )
        repo._asset_price_bounds["USDT"] = (1400.0, 1600.0)
        now = time.time()
        repo._last_update_ts = {"g1": now - 30.0, "g2": now - 30.0, "g3": now - 30.0}

        ad1 = MyAd(adv_no="g1", asset="USDT", ad_group=1, current_price=1585.00, status=1, init_amount=1000.0, min_trans_amount=450000.0, max_trans_amount=990000.0, payment_methods=["BANK"])
        ad2 = MyAd(adv_no="g2", asset="USDT", ad_group=2, current_price=1582.62, status=1, init_amount=950.0, min_trans_amount=600000.0, max_trans_amount=980000.0, payment_methods=["BANK"])
        ad3 = MyAd(adv_no="g3", asset="USDT", ad_group=3, current_price=1580.24, status=1, init_amount=900.0, min_trans_amount=500000.0, max_trans_amount=970000.0, payment_methods=["BANK"])

        dec1 = RepositionDecision(should_update=True, new_price=1585.02, reason="reposition_max_margin")
        dec2 = RepositionDecision(should_update=True, new_price=1585.02, reason="reposition_max_margin")
        dec3 = RepositionDecision(should_update=True, new_price=1585.02, reason="reposition_max_margin")

        resolved = repo.resolve_asset_price_collisions(
            "USDT",
            [(ad1, dec1), (ad2, dec2), (ad3, dec3)],
            config=BotConfig(price_step=0.01),
        )
        for ad, dec in resolved:
            self.assertFalse(dec.should_update, f"G{ad.ad_group} no debía actualizarse en micro-subida pasiva")
            self.assertEqual(dec.reason, "passive_hysteresis_hold")
            self.assertEqual(dec.new_price, ad.current_price)

    def test_parse_numeric_input_rejects_nan_and_inf(self):
        """[BUG-D2] Verifica que parse_numeric_input rechace NaN e Infinity."""
        from telegram_bot.bot import parse_numeric_input

        self.assertIsNone(parse_numeric_input("nan"))
        self.assertIsNone(parse_numeric_input("NaN"))
        self.assertIsNone(parse_numeric_input("inf"))
        self.assertIsNone(parse_numeric_input("-inf"))
        self.assertIsNone(parse_numeric_input("1e500"))
        self.assertEqual(parse_numeric_input("500.000"), 500000.0)

    async def test_fw_yes_atomic_pop_prevents_double_credit(self):
        """[BUG-D1] Verifica que dos clics concurrentes en fw_yes_ acrediten el saldo ARS una sola vez."""
        from telegram_bot.bot import TelegramBot

        mock_db = MagicMock()
        cfg = BotConfig(balance_ars=100_000.0)
        mock_db.load_bot_config.return_value = cfg

        mock_engine = MagicMock()
        mock_engine.config = cfg
        mock_engine.liquidity.balance = 100_000.0

        def _set_bal(val, **kwargs):
            mock_engine.liquidity.balance = val

        mock_engine.liquidity.set_balance.side_effect = _set_bal

        async def _slow_resume(adv_no):
            await asyncio.sleep(0.05)
            return True

        mock_engine.ads_manager.resume_ad = AsyncMock(side_effect=_slow_resume)
        mock_engine.repositioner._paused_by_liquidity = set()

        bot = TelegramBot(db=mock_db, bot_engine=mock_engine)
        bot._admin_ids = {999}
        bot.pending_rescues["ord_123"] = {
            "payout_ars": 48_000.0,
            "order_ars": 45_000.0,
            "adv_no": "adv_1",
            "asset": "USDT",
            "amount_crypto": 30.0,
            "fiwind_bid": 1600.0,
        }

        def _make_update():
            u = MagicMock()
            u.effective_user.id = 999
            u.effective_chat.id = 999
            u.callback_query.data = "fw_yes_ord_123"
            u.callback_query.answer = AsyncMock()
            u.callback_query.edit_message_text = AsyncMock()
            u.callback_query.message.text = "Alerta Fiwind"
            return u

        await asyncio.gather(
            bot._handle_callback(_make_update(), MagicMock()),
            bot._handle_callback(_make_update(), MagicMock()),
        )

        self.assertEqual(mock_engine.liquidity.balance, 148_000.0)
        self.assertEqual(mock_engine.liquidity.set_balance.call_count, 1)

    async def test_sync_my_ads_aborts_purge_on_truncated_pagination(self):
        """[BUG-B1] Verifica que sync_my_ads no purgue anuncios en BD si la paginación se corta prematuramente."""
        from core.ads.manager import AdsManager

        mock_client = MagicMock()
        page1_ads = [{"advNo": f"adv_{i}", "asset": "USDT", "price": "1500", "advStatus": 1, "tradeMethods": []} for i in range(20)]
        mock_client.list_my_ads = AsyncMock(side_effect=[
            {"data": page1_ads, "total": 42},
            {"data": [], "total": 42},
        ])
        mock_db = MagicMock()
        mock_db.get_my_ads.return_value = []

        mgr = AdsManager(mock_client, mock_db)
        await mgr.sync_my_ads()

        mock_db.purge_ads_except.assert_not_called()

    async def test_resume_all_skips_auto_paused_ads(self):
        """[BUG-C1] Verifica que resume_all omita anuncios en skip_adv_nos."""
        from core.ads.manager import AdsManager

        mock_client = MagicMock()
        mock_client.update_ad_status = AsyncMock(return_value={"data": True})
        mock_db = MagicMock()
        ad_ok = MyAd(adv_no="adv_ok", asset="USDT", ad_group=1, current_price=1500.0, status=3, init_amount=100.0, payment_methods=["BANK"])
        ad_no_liq = MyAd(adv_no="adv_no_liq", asset="USDT", ad_group=2, current_price=1495.0, status=3, init_amount=100.0, payment_methods=["BANK"])
        mock_db.get_my_ads.return_value = [ad_ok, ad_no_liq]

        mgr = AdsManager(mock_client, mock_db)
        count = await mgr.resume_all(config=BotConfig(), skip_adv_nos={"adv_no_liq"})

        self.assertEqual(count, 1)
        mock_client.update_ad_status.assert_awaited_once_with(adv_nos=["adv_ok"], status=1)

    async def test_b1_ads_post_does_not_retry_on_500_or_client_error(self):
        """[BUG-B1/B2] Verifica que POST /sapi/v1/c2c/ads/post no reintente en HTTP 5xx ni en ClientError."""
        import aiohttp
        from core.network.binance_api import BinanceClient, BinanceClientError

        client = BinanceClient(api_key="k", secret_key="s")
        client._reset_session = AsyncMock()

        # Caso 1: HTTP 502 en ads/post -> 1 solo intento, preserva status 502
        mock_session_502 = MagicMock()
        mock_session_502.request.side_effect = BinanceClientError(502, "HTTP_ERROR", "Bad Gateway")
        client._get_session = AsyncMock(return_value=mock_session_502)
        with self.assertRaises(BinanceClientError) as ctx502:
            await client._request("POST", "/sapi/v1/c2c/ads/post", body={"asset": "USDT"}, max_retries=3)
        self.assertEqual(ctx502.exception.status, 502)
        self.assertEqual(mock_session_502.request.call_count, 1)

        # Caso 2: aiohttp.ClientError en ads/post -> 1 solo intento, NETWORK_ERROR_NO_RETRY
        mock_session_net = MagicMock()
        mock_session_net.request.side_effect = aiohttp.ClientError("socket closed")
        client._get_session = AsyncMock(return_value=mock_session_net)
        with self.assertRaises(BinanceClientError) as ctx_net:
            await client._request("POST", "/sapi/v1/c2c/ads/post", body={"asset": "USDT"}, max_retries=3)
        self.assertEqual(ctx_net.exception.code, "NETWORK_ERROR_NO_RETRY")
        self.assertEqual(mock_session_net.request.call_count, 1)

    async def test_t9_alt_pause_does_not_persist_when_pause_ad_fails(self):
        """[BUG-T9] Verifica que alt_pause_ no marque el anuncio como pausado en BD si pause_ad retorna False."""
        from telegram_bot.bot import TelegramBot

        mock_db = MagicMock()
        cfg = BotConfig(paused_ads=[])
        mock_db.load_bot_config.return_value = cfg

        mock_engine = MagicMock()
        mock_engine.config = cfg
        mock_engine.ads_manager.pause_ad = AsyncMock(return_value=False)

        bot = TelegramBot(db=mock_db, bot_engine=mock_engine)
        bot._admin_ids = {999}

        u = MagicMock()
        u.effective_user.id = 999
        u.effective_chat.id = 999
        u.callback_query.data = "alt_pause_adv_99_ord_1"
        u.callback_query.answer = AsyncMock()
        u.callback_query.edit_message_text = AsyncMock()
        u.callback_query.message.text = "Alerta orden"

        await bot._handle_callback(u, MagicMock())

        self.assertNotIn("adv_99", cfg.paused_ads)
        mock_db.save_bot_config.assert_not_called()

    async def test_t7_user_state_expires_after_300s(self):
        """[BUG-T7] Verifica que el estado interactivo expire tras 300 segundos de inactividad."""
        from telegram_bot.bot import TelegramBot

        mock_db = MagicMock()
        mock_engine = MagicMock()
        bot = TelegramBot(db=mock_db, bot_engine=mock_engine)
        bot._admin_ids = {999}
        bot._user_state[999] = "set_balance"
        bot._user_state_ts[999] = time.time() - 310.0

        u = MagicMock()
        u.effective_user.id = 999
        u.effective_chat.id = 999
        u.message.text = "500000"
        u.message.reply_text = AsyncMock()

        await bot._handle_text_button(u, MagicMock())

        self.assertNotIn(999, bot._user_state)
        self.assertNotIn(999, bot._user_state_ts)
        mock_engine.liquidity.set_balance.assert_not_called()
        u.message.reply_text.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
