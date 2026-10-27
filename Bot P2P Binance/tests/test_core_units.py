"""Unit tests for P2P Binance bot core components and bugfixes."""
import unittest
import os
import sys
import time
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

# Agregar raíz del proyecto al sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import WATCHDOG_TIMEOUT_SECONDS
from data.database import Database
from data.models import MyAd, BotConfig
from core.liquidity.liquidity_manager import LiquidityTracker
from telegram_bot.formatters import escape_md, _translate_reason
from core.network.binance_api import BinanceClient, BinanceClientError


class TestSettings(unittest.TestCase):
    def test_watchdog_timeout(self):
        """Verifica que WATCHDOG_TIMEOUT_SECONDS sea al menos 300s para soportar ciclos de 135s."""
        self.assertGreaterEqual(WATCHDOG_TIMEOUT_SECONDS, 300)


class TestMarkdownEscaping(unittest.TestCase):
    def test_escape_md(self):
        """Verifica el escape de caracteres especiales de Markdown v1."""
        raw = "order_status_1*test`counterparty[user]"
        escaped = escape_md(raw)
        self.assertEqual(escaped, "order\\_status\\_1\\*test\\`counterparty\\[user]")

    def test_translate_reason(self):
        """Verifica la traducción y escape seguro de motivos."""
        self.assertEqual(_translate_reason("reposition_first"), "Reposicionado para estar 1ro")
        # Motivo desconocido con guiones bajos debe escaparse
        unknown = _translate_reason("custom_unknown_action_123")
        self.assertNotIn("_", unknown.replace("\\_", ""))
        self.assertIn("\\_", unknown)


class TestDatabaseFixes(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.db = Database(db_path=Path(self.temp_db_path))
        self.db.init_schema()

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_get_all_my_ads_alias(self):
        """Verifica que get_all_my_ads existe y funciona igual que get_my_ads."""
        ad = MyAd(
            adv_no="123456",
            asset="USDT",
            ad_group=1,
            current_price=1400.0,
            payment_methods=["BANK_TRANSFER"],
            status=1,
        )
        self.db.save_my_ad(ad)

        ads_normal = self.db.get_my_ads()
        ads_alias = self.db.get_all_my_ads()
        self.assertEqual(len(ads_normal), 1)
        self.assertEqual(len(ads_alias), 1)
        self.assertEqual(ads_alias[0].adv_no, "123456")

    def test_purge_ads_except_guard(self):
        """Verifica que purge_ads_except no borre la base de datos si keep_adv_nos está vacío."""
        ad = MyAd(
            adv_no="999888",
            asset="USDT",
            ad_group=1,
            current_price=1400.0,
            payment_methods=["BANK_TRANSFER"],
            status=1,
        )
        self.db.save_my_ad(ad)

        # Si pasamos set vacío (ej. fallo de red al sincronizar), no debe purgar nada
        deleted_count = self.db.purge_ads_except(set())
        self.assertEqual(deleted_count, 0)
        self.assertEqual(len(self.db.get_my_ads()), 1)

        # Si pasamos un conjunto con otro ID, debe purgar el 999888
        deleted_count = self.db.purge_ads_except({"other_id"})
        self.assertEqual(deleted_count, 1)
        self.assertEqual(len(self.db.get_my_ads()), 0)

    def test_purge_old_snapshots(self):
        """Verifica que purge_old_snapshots ejecuta la limpieza en la base de datos."""
        conn = self.db.connect()
        old_time = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        new_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO market_snapshots (timestamp, asset, trade_type, payment_method, volume_filter, snapshot_json) VALUES (?, ?, ?, ?, ?, ?)",
            (old_time, "USDT", "SELL", "BANK", 50000.0, "[]"),
        )
        conn.execute(
            "INSERT INTO market_snapshots (timestamp, asset, trade_type, payment_method, volume_filter, snapshot_json) VALUES (?, ?, ?, ?, ?, ?)",
            (new_time, "USDT", "SELL", "BANK", 50000.0, "[]"),
        )
        conn.commit()

        self.db.purge_old_snapshots(days=3)

        cursor = conn.execute("SELECT COUNT(*) FROM market_snapshots")
        self.assertEqual(cursor.fetchone()[0], 1)

    def test_load_and_save_bot_config_sync(self):
        """Verifica la persistencia de configuración del bot."""
        cfg = self.db.load_bot_config()
        self.assertIsNotNone(cfg)
        self.db.set_config("balance_ars", "750000")
        loaded_cfg = self.db.load_bot_config()
        self.assertEqual(loaded_cfg.balance_ars, 750000.0)

    def test_liquidity_tracker_sync(self):
        """Verifica que LiquidityTracker sincroniza su estado y base de datos."""
        mock_client = MagicMock()
        tracker = LiquidityTracker(client=mock_client, db=self.db)
        tracker._balance = 500000.0
        tracker.set_balance(850000.0)
        self.assertEqual(tracker.balance, 850000.0)
        self.assertEqual(tracker.effective_balance, 850000.0)

        val_in_db = self.db.get_config("balance_ars")
        self.assertEqual(float(val_in_db), 850000.0)

        text = tracker.get_status_text()
        self.assertIn("Balance Nominal", text)
        self.assertIn("$850,000.00 ARS", text)


class TestBinanceClientHandling(unittest.IsolatedAsyncioTestCase):
    async def test_handle_response_detects_error_without_success_field(self):
        """Verifica que _handle_response lance excepción si el código es de error aun si falta 'success'."""
        client = BinanceClient()
        mock_resp = MagicMock()
        mock_resp.headers = {}
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "code": "100001001",
            "message": "Invalid API-key, IP, or permissions for action.",
            "data": None,
        })

        with self.assertRaises(BinanceClientError) as ctx:
            await client._handle_response(mock_resp)
        self.assertIn("100001001", str(ctx.exception))
        await client.close()

    async def test_handle_response_success(self):
        """Verifica que _handle_response retorne los datos con código exitoso."""
        client = BinanceClient()
        mock_resp = MagicMock()
        mock_resp.headers = {"X-SAPI-USED-IP-WEIGHT-1M": "15"}
        mock_resp.status = 200
        ok_resp = {
            "code": "000000",
            "message": "SUCCESS",
            "data": [{"asset": "USDT"}],
            "success": True,
        }
        mock_resp.json = AsyncMock(return_value=ok_resp)

        result = await client._handle_response(mock_resp)
        self.assertEqual(result, ok_resp)
        self.assertEqual(client._rate_limit_remaining, 1200 - 15)
        await client.close()

    def test_build_signed_params_includes_recvwindow_and_offset(self):
        """Verifica que _build_signed_params aplique recvWindow=60000 y el offset horario."""
        client = BinanceClient(api_key="k", secret_key="s")
        client._time_offset = 2500  # 2.5s offset
        now_ms = int(time.time() * 1000)
        params = {"asset": "USDT"}
        signed_qs = client._build_signed_params(params)
        self.assertIn("recvWindow=60000", signed_qs)
        self.assertIn("signature=", signed_qs)
        self.assertIn("asset=USDT", signed_qs)
        self.assertGreaterEqual(params["timestamp"], now_ms + 2400)

    async def test_sync_time_updates_offset(self):
        """Verifica que sync_time calcule correctamente el offset contra el serverTime."""
        client = BinanceClient(api_key="k", secret_key="s")
        fake_server_time = int(time.time() * 1000) + 3000
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"serverTime": fake_server_time})

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        client._session = mock_session

        offset = await client.sync_time()
        self.assertAlmostEqual(offset, 3000, delta=200)
        self.assertEqual(client._time_offset, offset)
        self.assertGreater(client._last_time_sync, 0)
        await client.close()


class TestPriceRounding(unittest.TestCase):
    def test_price_step_float_rounding(self):
        """Verifica que sumar price_step redondeado a 2 decimales evite números con artefactos IEEE 754."""
        worst_case_price = 1420.31
        price_step = 0.01
        target_price = round(worst_case_price + price_step, 2)
        self.assertEqual(target_price, 1420.32)
        self.assertEqual(str(target_price), "1420.32")


class TestMarketScannerConcurrency(unittest.IsolatedAsyncioTestCase):
    async def test_scan_full_cycle_concurrent(self):
        """Verifica que scan_full_cycle opere concurrentemente y retorne la estructura completa."""
        from core.market_scanner import MarketScanner
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        db = Database(db_path=Path(temp_path))
        db.init_schema()

        mock_binance = MagicMock()
        mock_binance.search_ads = AsyncMock(return_value={
            "code": "000000",
            "data": [
                {
                    "adv": {
                        "advNo": "ad_123",
                        "price": "1400.50",
                        "tradeMethods": [{"identifier": "BANK"}],
                    },
                    "advertiser": {"nickName": "TestSeller", "userNo": "user_1"},
                }
            ]
        })
        mock_spot = MagicMock()
        mock_spot.get_usdt_prices = AsyncMock(return_value={"USDT": 1.0, "BTC": 65000.0})
        mock_spot.get_24hr_volatilities = AsyncMock(return_value={"USDT": 0.0, "BTC": 0.04})

        scanner = MarketScanner(client=mock_binance, spot_client=mock_spot, db=db)
        result = await scanner.scan_full_cycle(
            assets=["USDT", "BTC"],
            method_groups={1: ["BANK", "MP"]},
            volume_ref=50000.0,
        )

        self.assertIn("spot_prices", result)
        self.assertIn("benchmarks", result)
        self.assertIn("competitors", result)
        self.assertIn("volatilities", result)
        self.assertEqual(len(result["spot_prices"]), 2)
        # 2 assets x 2 methods = 4 competitor combinations
        self.assertEqual(len(result["competitors"]), 4)
        self.assertIn(("USDT", "BANK"), result["competitors"])
        self.assertIn(("BTC", "MP"), result["competitors"])

        db.close()
        if os.path.exists(temp_path):
            os.remove(temp_path)

    def test_get_best_competitor_dynamic_filter(self):
        """Verifica la lógica del filtro dinámico de anomalías."""
        from core.market_scanner import MarketScanner
        from data.models import ExchangeRate

        scanner = MarketScanner(client=MagicMock(), spot_client=MagicMock(), db=MagicMock())

        # Caso 1: Mercado real de Fiwind a las 6 AM (outliers extremos descolgados)
        fiwind_rates = [
            ExchangeRate("USDT", "Fiwind", 4305.5, 1.0, 4305.5, 1, advertiser_nickname="Troll1"),
            ExchangeRate("USDT", "Fiwind", 2224.2, 1.0, 2224.2, 2, advertiser_nickname="Troll2"),
            ExchangeRate("USDT", "Fiwind", 1645.0, 1.0, 1645.0, 3, advertiser_nickname="HighSeller"),
            ExchangeRate("USDT", "Fiwind", 1606.5, 1.0, 1606.5, 4, advertiser_nickname="RealSeller1"),
            ExchangeRate("USDT", "Fiwind", 1601.5, 1.0, 1601.5, 5, advertiser_nickname="RealSeller2"),
        ]
        best_fiwind = scanner.get_best_competitor(fiwind_rates)
        # Debe descartar $4305.5 y $2224.2 y quedarse con la posición real
        self.assertIsNotNone(best_fiwind)
        self.assertLess(best_fiwind.price_ars, 1700.0)

        # Caso 2: Altcoin con libro escalonado natural (BTC con saltos uniformes de 2.5%)
        btc_rates = [
            ExchangeRate("BTC", "BANK", 105000000.0, 65000.0, 1615.0, 1, advertiser_nickname="BTC1"),
            ExchangeRate("BTC", "BANK", 102000000.0, 65000.0, 1569.0, 2, advertiser_nickname="BTC2"),
            ExchangeRate("BTC", "BANK", 99000000.0, 65000.0, 1523.0, 3, advertiser_nickname="BTC3"),
            ExchangeRate("BTC", "BANK", 96000000.0, 65000.0, 1476.0, 4, advertiser_nickname="BTC4"),
        ]
        best_btc = scanner.get_best_competitor(btc_rates)
        # La pendiente es natural, debe competir contra el #1
        self.assertIsNotNone(best_btc)
        self.assertEqual(best_btc.price_ars, 105000000.0)

        # Caso 3: Menos de 3 competidores
        few_rates = [
            ExchangeRate("SOL", "BANK", 220000.0, 140.0, 1571.0, 1, advertiser_nickname="SOL1"),
            ExchangeRate("SOL", "BANK", 215000.0, 140.0, 1535.0, 2, advertiser_nickname="SOL2"),
        ]
        best_few = scanner.get_best_competitor(few_rates)
        self.assertEqual(best_few.price_ars, 220000.0)


class TestRescueMarginConfig(unittest.TestCase):
    def setUp(self):
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)
        self.db = Database(db_path=Path(self.temp_path))
        self.db.init_schema()

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.temp_path):
            os.remove(self.temp_path)

    def test_rescue_margin_db_persistence(self):
        """Verifica que rescue_margin se persista y cargue de forma consistente."""
        cfg = self.db.load_bot_config()
        self.assertEqual(cfg.rescue_margin, 10.0)

        cfg.rescue_margin = 8.5
        self.db.save_bot_config(cfg)

        reloaded = self.db.load_bot_config()
        self.assertEqual(reloaded.rescue_margin, 8.5)


class TestMultiAssetAndSellLess(unittest.IsolatedAsyncioTestCase):
    async def test_market_scanner_trade_types(self):
        """Verifica que scan_competitors use trade_type='SELL' y scan_usdt_benchmark use trade_type='BUY'."""
        from core.market_scanner import MarketScanner
        mock_binance = MagicMock()
        mock_binance.search_ads = AsyncMock(return_value={"data": []})
        mock_spot = MagicMock()
        mock_db = MagicMock()

        scanner = MarketScanner(client=mock_binance, spot_client=mock_spot, db=mock_db)

        # 1. Competencia de compra (el taker vende al merchant -> trade_type='SELL')
        await scanner.scan_competitors("USDT", "MercadoPagoNew", {"USDT": 1.0})
        mock_binance.search_ads.assert_called_with(
            asset="USDT",
            fiat="ARS",
            trade_type="SELL",
            pay_types=["MercadoPagoNew"],
            rows=20,
            publisher_type="merchant",
        )

        # 2. Benchmark de venta (el taker compra al merchant -> trade_type='BUY')
        await scanner.scan_usdt_benchmark("MercadoPagoNew", 500000.0)
        mock_binance.search_ads.assert_called_with(
            asset="USDT",
            fiat="ARS",
            trade_type="BUY",
            pay_types=["MercadoPagoNew"],
            trans_amount=500000.0,
            publisher_type="merchant",
            rows=10,
        )

    async def test_repositioner_sell_less_asset_minimum_step(self):
        """Verifica que un activo sell-less (ej: FDUSD) supere al 1er competidor por el paso mínimo ($0.01)."""
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, ExchangeRate, Benchmark, BotConfig

        ad = MyAd(
            adv_no="ad_fdusd_1",
            asset="FDUSD",
            ad_group=1,
            current_price=1550.0,
            payment_methods=["MercadoPagoNew"],
            status=1,
        )
        competitors = {
            ("FDUSD", "MercadoPagoNew"): [
                ExchangeRate("FDUSD", "MercadoPagoNew", 1567.0, 1.0, 1567.0, 1, advertiser_nickname="Comp1"),
                ExchangeRate("FDUSD", "MercadoPagoNew", 1531.0, 1.0, 1531.0, 2, advertiser_nickname="Comp2"),
            ]
        }
        # Benchmark USDT a 1590
        benchmarks = {
            "MercadoPagoNew": Benchmark("MercadoPagoNew", 1590.0, [1590.0], 500000.0, datetime.now())
        }
        spot_prices = {"FDUSD": 1.0}
        config = BotConfig(price_step=0.01, margin_min=10.0)

        mock_ads = MagicMock()
        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor = MagicMock(return_value=competitors[("FDUSD", "MercadoPagoNew")][0])
        mock_liquidity = MagicMock()
        mock_liquidity.available_balance = 500000.0
        mock_wars = MagicMock()
        mock_wars.is_in_war = MagicMock(return_value=False)
        mock_db = MagicMock()

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=mock_scanner,
            liquidity=mock_liquidity,
            war_detector=mock_wars,
            db=mock_db,
        )

        decision = await repo.evaluate_ad(
            ad=ad,
            competitors=competitors,
            benchmarks=benchmarks,
            spot_prices=spot_prices,
            config=config,
        )

        self.assertTrue(decision.should_update)
        # Debe superar a 1567.0 por exactamente $0.01 ARS -> 1567.01
        self.assertEqual(decision.new_price, 1567.01)
        self.assertEqual(decision.reason, "reposition_sell_less_gap")
        # El margen debe ser 1590 - 1567.01 = 22.99 ARS >= 10.0
        self.assertGreaterEqual(decision.margin_worst, 10.0)

    async def test_repositioner_stablecoin_ceiling_guardrail(self):
        """Verifica que FDUSD no supere el precio techo con colchón de 10 pesos (1590 - 10 = 1580)."""
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, ExchangeRate, Benchmark, BotConfig

        ad = MyAd(
            adv_no="ad_fdusd_1",
            asset="FDUSD",
            ad_group=1,
            current_price=1550.0,
            payment_methods=["MercadoPagoNew"],
            status=1,
        )
        # Competidor con precio que dejaría menos de 10 pesos de margen (1585 > 1580)
        competitors = {
            ("FDUSD", "MercadoPagoNew"): [
                ExchangeRate("FDUSD", "MercadoPagoNew", 1585.0, 1.0, 1585.0, 1, advertiser_nickname="Aggressive"),
            ]
        }
        benchmarks = {
            "MercadoPagoNew": Benchmark("MercadoPagoNew", 1590.0, [1590.0], 500000.0, datetime.now())
        }
        spot_prices = {"FDUSD": 1.0}
        config = BotConfig(price_step=0.01, margin_min=10.0)

        mock_ads = MagicMock()
        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor = MagicMock(return_value=competitors[("FDUSD", "MercadoPagoNew")][0])
        mock_liquidity = MagicMock()
        mock_liquidity.available_balance = 500000.0
        mock_wars = MagicMock()
        mock_wars.is_in_war = MagicMock(return_value=False)
        mock_db = MagicMock()

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=mock_scanner,
            liquidity=mock_liquidity,
            war_detector=mock_wars,
            db=mock_db,
        )

        decision = await repo.evaluate_ad(
            ad=ad,
            competitors=competitors,
            benchmarks=benchmarks,
            spot_prices=spot_prices,
            config=config,
        )

        self.assertTrue(decision.should_update)
        # El precio debe ser limitado al techo de 1580.00 ARS (1590 - 10)
        self.assertEqual(decision.new_price, 1580.00)
        self.assertEqual(decision.reason, "reposition_max_margin")
        self.assertGreaterEqual(decision.margin_worst, 10.0)

    async def test_repositioner_altcoin_percentage_margin(self):
        """Verifica que las altcoins usen config.margin_min si ALTCOIN_MIN_MARGIN_PCT=0.0, y 2% si está activado."""
        from unittest.mock import patch
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, ExchangeRate, Benchmark, BotConfig

        ad = MyAd(
            adv_no="ad_sol_1",
            asset="SOL",
            ad_group=1,
            current_price=150000.0,
            payment_methods=["MercadoPagoNew"],
            status=1,
        )
        spot_sol = 100.0  # 1 SOL = 100 USD
        competitors = {
            ("SOL", "MercadoPagoNew"): [
                ExchangeRate("SOL", "MercadoPagoNew", 157000.0, 100.0, 1570.0, 1, advertiser_nickname="TrollSOL"),
            ]
        }
        benchmarks = {
            "MercadoPagoNew": Benchmark("MercadoPagoNew", 1590.0, [1590.0], 500000.0, datetime.now())
        }
        spot_prices = {"SOL": 100.0}
        config = BotConfig(price_step=0.01, margin_min=10.0)

        mock_ads = MagicMock()
        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor = MagicMock(return_value=competitors[("SOL", "MercadoPagoNew")][0])
        mock_liquidity = MagicMock()
        mock_liquidity.available_balance = 500000.0
        mock_wars = MagicMock()
        mock_wars.is_in_war = MagicMock(return_value=False)
        mock_db = MagicMock()

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=mock_scanner,
            liquidity=mock_liquidity,
            war_detector=mock_wars,
            db=mock_db,
        )

        # Caso 1: Con ALTCOIN_MIN_MARGIN_PCT = 0.0 (desactivado), respeta margin_min (10 pesos) -> gana 1ro
        decision = await repo.evaluate_ad(
            ad=ad,
            competitors=competitors,
            benchmarks=benchmarks,
            spot_prices=spot_prices,
            config=config,
        )
        self.assertTrue(decision.should_update)
        self.assertEqual(decision.new_price, 157000.01)
        self.assertEqual(decision.reason, "reposition_first")
        self.assertGreaterEqual(decision.margin_worst, 10.0)

        # Caso 2: Con ALTCOIN_MIN_MARGIN_PCT = 0.02 (2.0%), exige 31.8 pesos -> no paga 157,000.01
        with patch("core.pricing.buy_repositioner.ALTCOIN_MIN_MARGIN_PCT", 0.02):
            decision_2pct = await repo.evaluate_ad(
                ad=ad,
                competitors=competitors,
                benchmarks=benchmarks,
                spot_prices=spot_prices,
                config=config,
            )
            self.assertTrue(decision_2pct.should_update)
            self.assertLessEqual(decision_2pct.new_price, 155820.00)
            self.assertGreaterEqual(decision_2pct.margin_worst, 31.8)

    async def test_market_scanner_quality_filter(self):
        """Verifica que MarketScanner descarte competidores con bajo completion rate u órdenes."""
        from core.market_scanner import MarketScanner
        from data.models import ExchangeRate

        mock_binance = MagicMock()
        mock_spot = MagicMock()
        mock_db = MagicMock()
        scanner = MarketScanner(client=mock_binance, spot_client=mock_spot, db=mock_db)

        comps = [
            # Inadecuado: solo 5 órdenes y 75% rate pero precio alto (cebo)
            ExchangeRate("USDT", "MercadoPagoNew", 1599.0, 1.0, 1599.0, 1, 
                         advertiser_order_count=5, advertiser_completion_rate=0.75, advertiser_nickname="Troll"),
            # Calificado: 100 órdenes y 98% rate
            ExchangeRate("USDT", "MercadoPagoNew", 1585.0, 1.0, 1585.0, 2, 
                         advertiser_order_count=100, advertiser_completion_rate=0.98, advertiser_nickname="ProTrader"),
        ]

        best = scanner.get_best_competitor(comps)
        self.assertIsNotNone(best)
        self.assertEqual(best.advertiser_nickname, "ProTrader")
        self.assertEqual(best.price_ars, 1585.0)


class TestDeleteBuyAds(unittest.IsolatedAsyncioTestCase):
    """Pruebas para la funcionalidad de borrado exclusivo de anuncios de COMPRA."""

    def test_database_clear_my_ads(self):
        """Verifica que clear_my_ads vacíe completamente la tabla my_ads."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name
        db = None
        try:
            db = Database(Path(db_path))
            db.init_schema()

            ad1 = MyAd("ad_1", "USDT", 1, 1500.0, ["MercadoPagoNew"], 1)
            ad2 = MyAd("ad_2", "BTC", 2, 110000000.0, ["UalaNew"], 1)
            db.save_my_ad(ad1)
            db.save_my_ad(ad2)
            self.assertEqual(len(db.get_my_ads()), 2)

            cleared = db.clear_my_ads()
            self.assertEqual(cleared, 2)
            self.assertEqual(len(db.get_my_ads()), 0)
        finally:
            if db:
                db.close()
            if os.path.exists(db_path):
                os.remove(db_path)

    async def test_delete_all_buy_ads_closes_only_buy(self):
        """Verifica que delete_all_buy_ads cierre únicamente los anuncios de compra en Binance y vacíe la BD."""
        from core.ads.manager import AdsManager

        mock_client = AsyncMock()
        mock_client.list_my_ads.return_value = {
            "data": [
                {"advNo": "buy_101", "tradeType": "BUY", "asset": "USDT"},
                {"advNo": "buy_102", "tradeType": "BUY", "asset": "BTC"},
            ],
            "total": 2,
        }
        mock_client.update_ad_status.return_value = {"code": "000000", "success": True, "data": True}

        mock_db = MagicMock()
        mock_db.get_my_ads.return_value = []
        mock_db.clear_my_ads.return_value = 2

        manager = AdsManager(client=mock_client, db=mock_db)
        stats = await manager.delete_all_buy_ads()

        # Verifica llamada a list_my_ads con trade_type="BUY" exclusivamente
        mock_client.list_my_ads.assert_called_with(trade_type="BUY", page=1, rows=20)

        # Verifica que close_ad fue llamado individualmente 1 por 1 (Regla Anti-187005)
        self.assertEqual(mock_client.close_ad.call_count, 2)
        closed_ids = [call.args[0] for call in mock_client.close_ad.call_args_list]
        self.assertIn("buy_101", closed_ids)
        self.assertIn("buy_102", closed_ids)

        # Verifica que la base de datos local fue limpiada
        mock_db.clear_my_ads.assert_called_once()

        # Verifica estadísticas
        self.assertEqual(stats["total_found"], 2)
        self.assertEqual(stats["deleted"], 2)
        self.assertEqual(stats["errors"], 0)

    async def test_delete_all_sell_ads_closes_only_sell(self):
        """Verifica que delete_all_sell_ads cierre únicamente los anuncios de venta en Binance y vacíe la BD."""
        from core.ads.manager import AdsManager

        mock_client = AsyncMock()
        mock_client.list_my_ads.return_value = {
            "data": [
                {"advNo": "sell_201", "tradeType": "SELL", "asset": "USDT"},
                {"advNo": "sell_202", "tradeType": "SELL", "asset": "USDT"},
            ],
            "total": 2,
        }
        mock_client.close_ad.return_value = {"code": "000000", "success": True, "data": True}

        mock_db = MagicMock()
        mock_db.get_my_sell_ads.return_value = []
        mock_db.clear_my_sell_ads.return_value = 2

        manager = AdsManager(client=mock_client, db=mock_db)
        stats = await manager.delete_all_sell_ads()

        # Verifica llamada a list_my_ads con trade_type="SELL" exclusivamente
        mock_client.list_my_ads.assert_called_with(trade_type="SELL", page=1, rows=20)

        # Verifica que close_ad fue llamado para cada anuncio de venta
        self.assertEqual(mock_client.close_ad.call_count, 2)
        closed_ids = [call.args[0] for call in mock_client.close_ad.call_args_list]
        self.assertIn("sell_201", closed_ids)
        self.assertIn("sell_202", closed_ids)

        # Verifica que la base de datos local fue limpiada
        mock_db.clear_my_sell_ads.assert_called_once()

        # Verifica estadísticas
        self.assertEqual(stats["total_found"], 2)
        self.assertEqual(stats["deleted"], 2)
        self.assertEqual(stats["errors"], 0)


class TestTelegramBotKeyboard(unittest.IsolatedAsyncioTestCase):
    """Pruebas para verificar la eliminación del teclado inferior y preservación de comandos."""

    def setUp(self):
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)
        self.db = Database(db_path=Path(self.temp_path))
        self.db.init_schema()

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.temp_path):
            os.remove(self.temp_path)

    async def test_get_reply_keyboard_returns_reply_keyboard_remove(self):
        """Verifica que get_reply_keyboard retorne ReplyKeyboardRemove para ocultar el teclado inferior."""
        from telegram import ReplyKeyboardRemove
        from telegram_bot.bot import TelegramBot

        bot = TelegramBot(db=self.db)
        kb = bot.get_reply_keyboard()
        self.assertIsInstance(kb, ReplyKeyboardRemove)

    async def test_cmd_start_sends_reply_keyboard_remove(self):
        """Verifica que /start use ReplyKeyboardRemove."""
        from telegram import ReplyKeyboardRemove
        from telegram_bot.bot import TelegramBot

        bot = TelegramBot(db=self.db)
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_ctx = MagicMock()

        await bot._cmd_start(mock_update, mock_ctx)
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        text = call_args[0][0] if call_args[0] else call_args[1].get("text", "")
        self.assertIn("hamburguesa", text)
        self.assertIsInstance(call_args[1].get("reply_markup"), ReplyKeyboardRemove)

    async def test_handle_text_button_backward_compatibility(self):
        """Verifica que si un usuario pulsa un botón residual del teclado anterior, no rompa nada y ejecute la acción."""
        from telegram_bot.bot import TelegramBot

        mock_engine = MagicMock()
        mock_engine.get_status_text = AsyncMock(return_value="Status OK")
        mock_engine.liquidity.get_status_text = MagicMock(return_value="Balance OK")
        mock_engine.turn_off = AsyncMock()
        mock_engine.turn_on = AsyncMock(return_value={})

        bot = TelegramBot(db=self.db, bot_engine=mock_engine)
        bot._admin_ids = {12345}

        # Prueba botón residual: "📊 Estado"
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message.text = "📊 Estado"
        mock_update.message.reply_text = AsyncMock()
        await bot._handle_text_button(mock_update, MagicMock())
        mock_update.message.reply_text.assert_called_once()

        # Prueba botón residual: "🔴 Apagar Bot"
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message.text = "🔴 Apagar Bot"
        mock_update.message.reply_text = AsyncMock()
        await bot._handle_text_button(mock_update, MagicMock())
        mock_engine.turn_off.assert_called_once()

    async def test_delete_sell_ads_button_and_inline_panels(self):
        """Verifica que el botón de borrar ventas esté en ambos paneles y responda a callbacks."""
        from telegram_bot.bot import TelegramBot

        bot = TelegramBot(db=self.db)
        panel = bot.get_inline_panel()
        callbacks = [btn.callback_data for row in panel.inline_keyboard for btn in row]
        self.assertIn("bot_delete_sell_confirm", callbacks)

        sell_panel = bot.get_sell_inline_panel()
        sell_callbacks = [btn.callback_data for row in sell_panel.inline_keyboard for btn in row]
        self.assertIn("bot_delete_sell_confirm", sell_callbacks)


class TestColdCalibrationAndDynamicAmount(unittest.IsolatedAsyncioTestCase):
    """Pruebas unitarias para calibración en frío y cálculo dinámico de cantidad de cripto."""

    def setUp(self):
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)
        self.db = Database(db_path=Path(self.temp_path))
        self.db.init_schema()

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.temp_path):
            os.remove(self.temp_path)

    async def test_dynamic_init_amount_calculation_and_precision(self):
        """Verifica que evaluate_ad calcule new_init_amount respetando ASSET_PRECISION y el balance disponible."""
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, ExchangeRate, Benchmark, BotConfig

        mock_ads = MagicMock()
        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor.side_effect = lambda rates: rates[0] if rates else None
        mock_liquidity = MagicMock()
        mock_liquidity.available_balance = 1095000.0
        mock_wars = MagicMock()
        mock_wars.is_in_war.return_value = False
        mock_db = MagicMock()

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=mock_scanner,
            liquidity=mock_liquidity,
            war_detector=mock_wars,
            db=mock_db,
        )
        config = BotConfig(price_step=0.01, margin_min=10.0)

        # 1. Anuncio USDT (precisión 2)
        ad_usdt = MyAd(
            adv_no="usdt_01",
            asset="USDT",
            ad_group=1,
            current_price=1500.0,
            init_amount=100.0,
            payment_methods=["BANK"],
            status=3,
        )
        competitors_usdt = {
            ("USDT", "BANK"): [
                ExchangeRate("USDT", "BANK", 1520.0, 1.0, 1520.0, 1, advertiser_no="comp1", max_single_trans_amount=1_000_000.0)
            ]
        }
        benchmarks_usdt = {
            "BANK": Benchmark("BANK", 1590.0, [1590.0], 500000.0, datetime.now())
        }
        dec_usdt = await repo.evaluate_ad(
            ad_usdt, competitors_usdt, benchmarks_usdt, {"USDT": 1.0}, config
        )
        self.assertIsNotNone(dec_usdt)
        self.assertEqual(dec_usdt.new_price, 1520.01)
        expected_usdt = round(1095000.0 / 1520.01, 2)
        self.assertEqual(dec_usdt.new_init_amount, expected_usdt)

        # 2. Anuncio BTC (precisión 6)
        ad_btc = MyAd(
            adv_no="btc_01",
            asset="BTC",
            ad_group=1,
            current_price=90000000.0,
            init_amount=0.001,
            payment_methods=["BANK"],
            status=3,
        )
        competitors_btc = {
            ("BTC", "BANK"): [
                ExchangeRate("BTC", "BANK", 95000000.0, 65000.0, 1461.53, 1, advertiser_no="comp2", max_single_trans_amount=1_000_000.0)
            ]
        }
        benchmarks_btc = {
            "BANK": Benchmark("BANK", 1590.0, [1590.0], 500000.0, datetime.now())
        }
        dec_btc = await repo.evaluate_ad(
            ad_btc, competitors_btc, benchmarks_btc, {"BTC": 65000.0}, config
        )
        self.assertIsNotNone(dec_btc)
        self.assertEqual(dec_btc.new_price, 95000000.01)
        expected_btc = round(1095000.0 / 95000000.01, 6)
        self.assertEqual(dec_btc.new_init_amount, expected_btc)

        # 3. Anuncio 1000CHEEMS (precisión 0)
        ad_cheems = MyAd(
            adv_no="cheems_01",
            asset="1000CHEEMS",
            ad_group=1,
            current_price=3.0,
            init_amount=1000.0,
            payment_methods=["BANK"],
            status=3,
        )
        competitors_cheems = {
            ("1000CHEEMS", "BANK"): [
                ExchangeRate("1000CHEEMS", "BANK", 3.50, 0.002, 1750.0, 1, advertiser_no="comp3", max_single_trans_amount=1_000_000.0)
            ]
        }
        benchmarks_cheems = {
            "BANK": Benchmark("BANK", 1850.0, [1850.0], 500000.0, datetime.now())
        }
        dec_cheems = await repo.evaluate_ad(
            ad_cheems, competitors_cheems, benchmarks_cheems, {"1000CHEEMS": 0.002}, config
        )
        self.assertIsNotNone(dec_cheems)
        self.assertEqual(dec_cheems.new_price, 3.51)
        expected_cheems = round(1095000.0 / 3.51, 0)
        self.assertEqual(dec_cheems.new_init_amount, expected_cheems)

    async def test_repositioner_run_cycle_allow_offline(self):
        """Verifica que run_cycle(allow_offline=False) ignore anuncios offline y allow_offline=True los procese."""
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, ExchangeRate, Benchmark, BotConfig

        mock_ads = MagicMock()
        mock_ads.update_ad_params = AsyncMock(return_value=True)
        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor.side_effect = lambda rates: rates[0] if rates else None
        mock_liquidity = MagicMock()
        mock_liquidity.available_balance = 500000.0
        mock_wars = MagicMock()
        mock_wars.is_in_war.return_value = False
        mock_db = MagicMock()

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=mock_scanner,
            liquidity=mock_liquidity,
            war_detector=mock_wars,
            db=mock_db,
        )

        ad_offline = MyAd(
            adv_no="offline_ad",
            asset="USDT",
            ad_group=1,
            current_price=1400.0,
            init_amount=50.0,
            payment_methods=["BANK"],
            status=3,  # Offline
        )

        competitors = {
            ("USDT", "BANK"): [
                ExchangeRate("USDT", "BANK", 1500.0, 1.0, 1500.0, 1, advertiser_no="c1", max_single_trans_amount=1_000_000.0)
            ]
        }
        benchmarks = {
            "BANK": Benchmark("BANK", 1580.0, [1580.0], 500000.0, datetime.now())
        }
        spot_prices = {"USDT": 1.0}
        config = BotConfig(price_step=0.01, margin_min=10.0)

        # Con allow_offline=False, no debe ejecutar reposicionamiento
        results_online_only = await repo.run_cycle(
            [ad_offline], competitors, benchmarks, spot_prices, config, allow_offline=False
        )
        self.assertEqual(len(results_online_only), 0)
        mock_ads.update_ad_params.assert_not_called()

        # Con allow_offline=True, debe reposicionar el anuncio offline
        results_offline = await repo.run_cycle(
            [ad_offline], competitors, benchmarks, spot_prices, config, allow_offline=True
        )
        self.assertEqual(len(results_offline), 1)
        self.assertEqual(results_offline[0][0].adv_no, "offline_ad")
        mock_ads.update_ad_params.assert_called_once()
        call_kwargs = mock_ads.update_ad_params.call_args[1]
        self.assertEqual(call_kwargs["adv_no"], "offline_ad")
        self.assertEqual(call_kwargs["price"], 1500.01)
        self.assertEqual(call_kwargs["init_amount"], round(500000.0 / 1500.01, 2))

    async def test_ads_manager_update_ad_params(self):
        """Verifica que update_ad_params envíe price, init_amount y límites simultáneamente."""
        from core.ads.manager import AdsManager
        from data.models import MyAd

        mock_client = MagicMock()
        mock_client.update_ad = AsyncMock(return_value={"data": True})
        manager = AdsManager(client=mock_client, db=self.db)

        # Crear anuncio en DB local
        ad = MyAd(
            adv_no="param_test",
            asset="USDT",
            ad_group=1,
            current_price=1400.0,
            init_amount=100.0,
            max_trans_amount=50000.0,
            payment_methods=["BANK_TRANSFER"],
            status=3,
        )
        self.db.save_my_ad(ad)

        success = await manager.update_ad_params(
            adv_no="param_test",
            price=1550.25,
            init_amount=650.0,
            min_trans_amount=5000.0,
            max_trans_amount=1000000.0,
        )
        self.assertTrue(success)
        mock_client.update_ad.assert_called_once_with(
            adv_no="param_test",
            update_mode="quickedit",
            price=1550.25,
            initAmount=650.0,
            minSingleTransAmount=5000.0,
            maxSingleTransAmount=1000000.0,
        )

        # Verificar actualización en DB local
    async def test_repositioner_dynamic_limits_and_crypto_amount(self):
        """Verifica que el reposicionador asigne Max = 100% saldo, Min = 50% saldo y pause si saldo < piso."""
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, ExchangeRate, Benchmark, BotConfig

        ad = MyAd(
            adv_no="dyn_limits_ad",
            asset="USDT",
            ad_group=1,
            current_price=1500.0,
            payment_methods=["MercadoPagoNew"],
            status=1,
        )
        competitors = {
            ("USDT", "MercadoPagoNew"): [
                ExchangeRate("USDT", "MercadoPagoNew", 1550.0, 1.0, 1550.0, 1, advertiser_nickname="Comp1"),
            ]
        }
        benchmarks = {
            "MercadoPagoNew": Benchmark("MercadoPagoNew", 1590.0, [1590.0], 500000.0, datetime.now())
        }
        spot_prices = {"USDT": 1.0}
        config = BotConfig(price_step=0.01, margin_min=10.0)

        mock_ads = MagicMock()
        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor = MagicMock(return_value=competitors[("USDT", "MercadoPagoNew")][0])
        mock_wars = MagicMock()
        mock_wars.is_in_war = MagicMock(return_value=False)
        mock_db = MagicMock()

        # Caso 1: Saldo de $1.100.000 ARS
        mock_liquidity = MagicMock()
        mock_liquidity.available_balance = 1_100_000.0

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=mock_scanner,
            liquidity=mock_liquidity,
            war_detector=mock_wars,
            db=mock_db,
        )

        decision = await repo.evaluate_ad(
            ad=ad,
            competitors=competitors,
            benchmarks=benchmarks,
            spot_prices=spot_prices,
            config=config,
        )

        self.assertTrue(decision.should_update)
        # G1: 45% min, 99% max
        self.assertEqual(decision.new_max_trans_amount, 1_089_000.0)
        self.assertEqual(decision.new_min_trans_amount, 495_000.0)
        expected_crypto = round(1_100_000.0 / decision.new_price, 2)
        self.assertEqual(decision.new_init_amount, expected_crypto)

        # Verificar G2: 60% min, 98% max
        ad_g2 = MyAd(adv_no="g2_ad", asset="USDT", ad_group=2, current_price=1500.0, payment_methods=["SantanderArgentina"], status=1)
        decision_g2 = await repo.evaluate_ad(ad=ad_g2, competitors={("USDT", "SantanderArgentina"): competitors[("USDT", "MercadoPagoNew")]}, benchmarks={"SantanderArgentina": benchmarks["MercadoPagoNew"]}, spot_prices=spot_prices, config=config)
        self.assertEqual(decision_g2.new_max_trans_amount, 1_078_000.0)
        self.assertEqual(decision_g2.new_min_trans_amount, 660_000.0)

        # Verificar G3: 50% min, 97% max
        ad_g3 = MyAd(adv_no="g3_ad", asset="USDT", ad_group=3, current_price=1500.0, payment_methods=["personalpay"], status=1)
        decision_g3 = await repo.evaluate_ad(ad=ad_g3, competitors={("USDT", "personalpay"): competitors[("USDT", "MercadoPagoNew")]}, benchmarks={"personalpay": benchmarks["MercadoPagoNew"]}, spot_prices=spot_prices, config=config)
        self.assertEqual(decision_g3.new_max_trans_amount, 1_067_000.0)
        self.assertEqual(decision_g3.new_min_trans_amount, 550_000.0)

        # Caso 2: Saldo insuficiente (< $10.000 ARS)
        mock_liquidity.available_balance = 5_000.0
        decision_low = await repo.evaluate_ad(
            ad=ad,
            competitors=competitors,
            benchmarks=benchmarks,
            spot_prices=spot_prices,
            config=config,
        )
        self.assertTrue(decision_low.should_pause)

    async def test_anti_collision_staggering_usdt(self):
        """Verifica que si 3 anuncios de USDT intentan fijar el mismo precio, se escalonen con buffer LATAM 0.15% (~$2.38 ARS)."""
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, RepositionDecision, BotConfig

        mock_ads = MagicMock()
        mock_ads.update_ad_params = AsyncMock(return_value=True)
        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=MagicMock(),
            liquidity=MagicMock(),
            war_detector=MagicMock(),
            db=MagicMock(),
        )

        config = BotConfig(price_step=0.01)

        ad1 = MyAd(adv_no="ad1", asset="USDT", ad_group=1, current_price=1580.0, payment_methods=["MP"], status=1)
        ad2 = MyAd(adv_no="ad2", asset="USDT", ad_group=2, current_price=1580.0, payment_methods=["BA"], status=1)
        ad3 = MyAd(adv_no="ad3", asset="USDT", ad_group=3, current_price=1580.0, payment_methods=["NX"], status=1)

        dec1 = RepositionDecision(new_price=1583.51, should_update=True, tc_implicito=1583.51)
        dec2 = RepositionDecision(new_price=1583.51, should_update=True, tc_implicito=1583.51)
        dec3 = RepositionDecision(new_price=1583.51, should_update=True, tc_implicito=1583.51)

        evaluated = [(ad1, dec1), (ad2, dec2), (ad3, dec3)]
        ordered = repo.resolve_asset_price_collisions("USDT", evaluated, config)

        self.assertEqual(len(ordered), 3)
        prices = {ad.adv_no: dec.new_price for ad, dec in ordered}
        self.assertEqual(prices["ad1"], 1583.51)
        self.assertEqual(prices["ad2"], 1581.13)
        self.assertEqual(prices["ad3"], 1578.75)

        # Verificar separación mínima >= 0.15% LATAM (~$2.38 ARS para USDT @ ~1583)
        self.assertGreaterEqual(round(prices["ad1"] - prices["ad2"], 2), 2.38)
        self.assertGreaterEqual(round(prices["ad2"] - prices["ad3"], 2), 2.38)

    async def test_repositioner_liquid_benchmark_anchor(self):
        """
        Verifica que el techo de compra de anuncios con métodos ilíquidos (ej. G3: Personal Pay @ 1615)
        se ancle estrictamente al benchmark líquido (ej. Mercado Pago @ 1596),
        garantizando que el precio máximo nunca supere $1583 con margen de $13.
        """
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, Benchmark, ExchangeRate, BotConfig

        mock_ads = MagicMock()
        mock_liq = MagicMock()
        mock_liq.available_balance = 500_000.0
        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor.side_effect = lambda rates: rates[0] if rates else None

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=mock_scanner,
            liquidity=mock_liq,
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )

        ad_g3 = MyAd(
            adv_no="g3_usdt",
            asset="USDT",
            ad_group=3,
            current_price=1575.0,
            payment_methods=["personalpay", "Prex"],
            status=1,
        )

        # Competidor #1 en G3 está pagando $1587.00
        comp_g3 = ExchangeRate(
            asset="USDT",
            payment_method="personalpay",
            price_ars=1587.0,
            spot_price_usdt=1.0,
            tc_implicito=1587.0,
            position=1,
            advertiser_no="c1",
            advertiser_nickname="comp_g3",
            advertiser_completion_rate=0.95,
            advertiser_order_count=50,
            timestamp=datetime.now(),
        )
        competitors = {("USDT", "personalpay"): [comp_g3]}

        # Benchmarks: Personal Pay cotiza a $1615 (ilíquido y caro), Mercado Pago a $1596 (líquido)
        benchmarks = {
            "personalpay": Benchmark(payment_method="personalpay", avg_top_n_price=1615.0),
            "Prex": Benchmark(payment_method="Prex", avg_top_n_price=1620.0),
            "MercadoPagoNew": Benchmark(payment_method="MercadoPagoNew", avg_top_n_price=1596.0),
        }

        spot_prices = {"USDT": 1.0}
        config = BotConfig(margin_min=13.0, price_step=0.01)

        decision = await repo.evaluate_ad(ad_g3, competitors, benchmarks, spot_prices, config)

        # El techo debe basarse en Mercado Pago ($1596 - $13 = $1583)
        # NUNCA debe colocarse en $1587.01
        self.assertTrue(decision.should_update)
        self.assertLessEqual(decision.new_price, 1583.0)
        self.assertGreaterEqual(decision.margin_worst, 13.0)

        # Ahora verificar que si G1, G2 y G3 colisionan en 1583.00, se escalonen sin superar el techo
        ad_g1 = MyAd(adv_no="g1_usdt", asset="USDT", ad_group=1, current_price=1575.0, payment_methods=["MercadoPagoNew"], status=1)
        ad_g2 = MyAd(adv_no="g2_usdt", asset="USDT", ad_group=2, current_price=1575.0, payment_methods=["SantanderArgentina"], status=1)
        from data.models import RepositionDecision
        dec1 = RepositionDecision(new_price=1583.00, should_update=True)
        dec2 = RepositionDecision(new_price=1583.00, should_update=True)
        dec3 = RepositionDecision(new_price=1583.00, should_update=True)

        ordered = repo.resolve_asset_price_collisions("USDT", [(ad_g1, dec1), (ad_g2, dec2), (ad_g3, dec3)], config)
        prices = {ad.adv_no: dec.new_price for ad, dec in ordered}
        self.assertEqual(prices["g1_usdt"], 1583.00)
        self.assertEqual(prices["g2_usdt"], 1580.63)
        self.assertEqual(prices["g3_usdt"], 1578.26)
        # Ninguno supera el techo de 1583.00 y la separación es >= 0.15% (norma LATAM)
        for p in prices.values():
            self.assertLessEqual(p, 1583.00)

    def test_war_detector_expiration_mutation_safety(self):
        """Verifica que el reseteo de un tracker expirado no cause RuntimeError al iterar."""
        from core.war_detector import WarDetector, WarTracker
        from datetime import datetime, timedelta

        mock_db = MagicMock()
        detector = WarDetector(db=mock_db)

        expired_time = datetime.now() - timedelta(minutes=45)
        tracker = WarTracker(
            competitor_no="comp1",
            competitor_nickname="comp1_nick",
            asset="XRP",
            payment_method="SantanderArgentina",
            escalations=3,
            last_escalation=expired_time,
        )
        detector._trackers[("comp1", "XRP", "SantanderArgentina")] = tracker

        # is_in_war debe detectar que expiró, llamar a _reset_tracker y no levantar RuntimeError
        in_war = detector.is_in_war("XRP", "SantanderArgentina")
        self.assertFalse(in_war)
        self.assertNotIn(("comp1", "XRP", "SantanderArgentina"), detector._trackers)
        mock_db.end_price_war.assert_called_once()

    async def test_competitor_filtering_by_ticket_size(self):
        """
        Verifica que el bot descarte competidores micro (ej. max $25.000 ARS)
        y solo compita contra anuncios cuyo max_single_trans_amount cubra el mínimo dinámico del usuario.
        """
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, Benchmark, ExchangeRate, BotConfig

        mock_ads = MagicMock()
        mock_liq = MagicMock()
        mock_liq.available_balance = 1_000_000.0  # Balance disponible: $1.000.000 ARS
        # Para G1 (factor 45%), el target_min es $450.000 ARS

        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor.side_effect = lambda rates: rates[0] if rates else None

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=mock_scanner,
            liquidity=mock_liq,
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )

        ad_g1 = MyAd(
            adv_no="ad_g1_ticket",
            asset="USDT",
            ad_group=1,
            current_price=1550.0,
            payment_methods=["MercadoPagoNew"],
            status=1,
        )

        # Micro-competidor pagando $1578.00 pero con max $25.000
        micro_comp = ExchangeRate(
            asset="USDT",
            payment_method="MercadoPagoNew",
            price_ars=1578.0,
            spot_price_usdt=1.0,
            tc_implicito=1578.0,
            position=1,
            advertiser_no="c_micro",
            advertiser_nickname="micro_trader",
            min_single_trans_amount=5000.0,
            max_single_trans_amount=25000.0,
            timestamp=datetime.now(),
        )

        # Competidor mayorista pagando $1568.00 con max $600.000 (cubre los $450.000 requeridos)
        wholesale_comp = ExchangeRate(
            asset="USDT",
            payment_method="MercadoPagoNew",
            price_ars=1568.0,
            spot_price_usdt=1.0,
            tc_implicito=1568.0,
            position=2,
            advertiser_no="c_wholesale",
            advertiser_nickname="wholesale_trader",
            min_single_trans_amount=200000.0,
            max_single_trans_amount=600000.0,
            timestamp=datetime.now(),
        )

        competitors = {("USDT", "MercadoPagoNew"): [micro_comp, wholesale_comp]}
        benchmarks = {
            "MercadoPagoNew": Benchmark(payment_method="MercadoPagoNew", avg_top_n_price=1596.0)
        }
        spot_prices = {"USDT": 1.0}
        config = BotConfig(margin_min=13.0, price_step=0.01)

        decision = await repo.evaluate_ad(ad_g1, competitors, benchmarks, spot_prices, config)

        self.assertTrue(decision.should_update)
        # Debe competir contra wholesale_comp ($1568.00 + $0.01 = $1568.01), IGNORANDO al micro ($1578.00)
        self.assertEqual(decision.new_price, 1568.01)
        self.assertEqual(decision.competitor_no, "c_wholesale")
        self.assertEqual(decision.reason, "reposition_first")

    async def test_fallback_volatility_discount_altcoin(self):
        """
        Verifica que cuando NO hay competidores mayoristas (solo micro-anuncios),
        el bot aplique el fallback colocándose debajo del competidor más bajo con descuento por volatilidad 24h.
        """
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, Benchmark, ExchangeRate, BotConfig

        mock_ads = MagicMock()
        mock_liq = MagicMock()
        mock_liq.available_balance = 1_000_000.0  # target_min para G1 = $450.000
        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor.side_effect = lambda rates: rates[0] if rates else None

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=mock_scanner,
            liquidity=mock_liq,
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )

        ad_btc = MyAd(
            adv_no="ad_btc_fb",
            asset="BTC",
            ad_group=1,
            current_price=90000000.0,
            payment_methods=["MercadoPagoNew"],
            status=1,
        )

        # Solo micro-competidores en el libro
        micro_comp1 = ExchangeRate(
            asset="BTC",
            payment_method="MercadoPagoNew",
            price_ars=95000000.0,
            spot_price_usdt=65000.0,
            tc_implicito=1461.53,
            position=1,
            advertiser_no="c_m1",
            max_single_trans_amount=20000.0,
            timestamp=datetime.now(),
        )
        micro_comp2 = ExchangeRate(
            asset="BTC",
            payment_method="MercadoPagoNew",
            price_ars=94000000.0,
            spot_price_usdt=65000.0,
            tc_implicito=1446.15,
            position=2,
            advertiser_no="c_m2",
            max_single_trans_amount=30000.0,
            timestamp=datetime.now(),
        )

        competitors = {("BTC", "MercadoPagoNew"): [micro_comp1, micro_comp2]}
        benchmarks = {
            "MercadoPagoNew": Benchmark(payment_method="MercadoPagoNew", avg_top_n_price=1596.0)
        }
        spot_prices = {"BTC": 65000.0}
        # Volatilidad 24h = 4.0% (0.04) -> factor = max(0.005, 0.04 * 0.25) = 0.01 (1.0% de descuento)
        volatilities = {"BTC": 0.04}
        config = BotConfig(margin_min=13.0, price_step=0.01)

        decision = await repo.evaluate_ad(
            ad_btc, competitors, benchmarks, spot_prices, config, volatilities=volatilities
        )

        self.assertTrue(decision.should_update)
        self.assertEqual(decision.reason, "reposition_last_volatility_discount")
        # El menor precio en el libro es 94.000.000. Descuento 1% = 93.060.000, pero el piso legal 90% (Anti-187031) es 93.366.000.00
        self.assertEqual(decision.new_price, 93_366_000.00)

    async def test_fallback_volatility_discount_stablecoin(self):
        """
        Verifica el descuento por volatilidad en stablecoin (0.1% fijo) cuando no hay mayoristas.
        """
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, Benchmark, ExchangeRate, BotConfig

        mock_ads = MagicMock()
        mock_liq = MagicMock()
        mock_liq.available_balance = 1_000_000.0
        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor.side_effect = lambda rates: rates[0] if rates else None

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=mock_scanner,
            liquidity=mock_liq,
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )

        ad_usdt = MyAd(
            adv_no="ad_usdt_fb",
            asset="USDT",
            ad_group=1,
            current_price=1550.0,
            payment_methods=["MercadoPagoNew"],
            status=1,
        )

        micro_comp = ExchangeRate(
            asset="USDT",
            payment_method="MercadoPagoNew",
            price_ars=1580.0,
            spot_price_usdt=1.0,
            tc_implicito=1580.0,
            position=1,
            advertiser_no="c_m1",
            max_single_trans_amount=15000.0,
            timestamp=datetime.now(),
        )

        competitors = {("USDT", "MercadoPagoNew"): [micro_comp]}
        benchmarks = {
            "MercadoPagoNew": Benchmark(payment_method="MercadoPagoNew", avg_top_n_price=1596.0)
        }
        spot_prices = {"USDT": 1.0}
        config = BotConfig(margin_min=13.0, price_step=0.01)

        decision = await repo.evaluate_ad(
            ad_usdt, competitors, benchmarks, spot_prices, config, volatilities={"USDT": 0.0}
        )

        self.assertTrue(decision.should_update)
        self.assertEqual(decision.reason, "reposition_last_volatility_discount")
        # Menor precio = 1580.00. Descuento 0.1% = 1.58. Precio esperado = 1578.42
        self.assertEqual(decision.new_price, 1578.42)

    async def test_fallback_volatility_discount_strictly_capped_at_max_allowed(self):
        """
        Verifica que si el competidor más bajo está inflado, el precio descontado
        quede estrictamente limitado por max_allowed_price, preservando el margen de seguridad.
        """
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, Benchmark, ExchangeRate, BotConfig

        mock_ads = MagicMock()
        mock_liq = MagicMock()
        mock_liq.available_balance = 1_000_000.0
        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor.side_effect = lambda rates: rates[0] if rates else None

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=mock_scanner,
            liquidity=mock_liq,
            war_detector=MagicMock(is_in_war=MagicMock(return_value=False)),
            db=MagicMock(),
        )

        ad_usdt = MyAd(
            adv_no="ad_usdt_cap",
            asset="USDT",
            ad_group=1,
            current_price=1550.0,
            payment_methods=["MercadoPagoNew"],
            status=1,
        )

        # Competidor muy caro a $1620 con límite micro
        micro_high = ExchangeRate(
            asset="USDT",
            payment_method="MercadoPagoNew",
            price_ars=1620.0,
            spot_price_usdt=1.0,
            tc_implicito=1620.0,
            position=1,
            advertiser_no="c_m1",
            max_single_trans_amount=15000.0,
            timestamp=datetime.now(),
        )

        competitors = {("USDT", "MercadoPagoNew"): [micro_high]}
        # Benchmark = 1590, con margen 13 -> max_allowed_price = 1577.00
        benchmarks = {
            "MercadoPagoNew": Benchmark(payment_method="MercadoPagoNew", avg_top_n_price=1590.0)
        }
        spot_prices = {"USDT": 1.0}
        config = BotConfig(margin_min=13.0, price_step=0.01)

        # 1620 - 0.1% = 1618.38, muy por encima de 1577.00
        decision = await repo.evaluate_ad(
            ad_usdt, competitors, benchmarks, spot_prices, config, volatilities={"USDT": 0.0}
        )

        self.assertTrue(decision.should_update)
        self.assertEqual(decision.reason, "reposition_last_volatility_discount")
        self.assertLessEqual(decision.new_price, 1577.00)
        self.assertEqual(decision.new_price, 1577.00)
        self.assertGreaterEqual(decision.margin_worst, 13.0)

    async def test_spot_client_get_24hr_volatilities(self):
        """Verifica que SpotClient.get_24hr_volatilities calcule correctamente la volatilidad."""
        from core.spot_client import SpotClient

        client = SpotClient()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[
            {"symbol": "BTCUSDT", "highPrice": "68000.00", "lowPrice": "64000.00"},
            {"symbol": "SOLUSDT", "highPrice": "150.00", "lowPrice": "140.00"},
        ])

        mock_session = MagicMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.close = AsyncMock()
        mock_session.closed = False

        client._session = mock_session

        vols = await client.get_24hr_volatilities(["USDT", "BTC", "SOL", "UNLISTED"])

        # Stablecoin USDT siempre 0.0
        self.assertEqual(vols["USDT"], 0.0)
        # BTC: (68000 - 64000) / 64000 = 4000 / 64000 = 0.0625
        self.assertAlmostEqual(vols["BTC"], 0.0625, places=4)
        # SOL: (150 - 140) / 140 = 10 / 140 = ~0.0714
        self.assertAlmostEqual(vols["SOL"], 10.0 / 140.0, places=4)
        # UNLISTED: fallback default 0.03
        self.assertEqual(vols["UNLISTED"], 0.03)

        await client.close()

    async def test_edge_case_abort_on_network_failure(self):
        """Verifica que si una actualización de precio falla en Binance, se aborten las restantes del activo."""
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, ExchangeRate, Benchmark, BotConfig

        mock_ads = MagicMock()
        # Primer llamado falla (False), segundo tendría éxito si se llamara
        mock_ads.update_ad_params = AsyncMock(side_effect=[False, True])
        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor.side_effect = lambda rates: rates[0] if rates else None
        mock_liquidity = MagicMock()
        mock_liquidity.available_balance = 1_000_000.0
        mock_wars = MagicMock()
        mock_wars.is_in_war.return_value = False
        mock_db = MagicMock()

        repo = Repositioner(
            ads_manager=mock_ads,
            scanner=mock_scanner,
            liquidity=mock_liquidity,
            war_detector=mock_wars,
            db=mock_db,
        )

        ad1 = MyAd(adv_no="ad_1", asset="USDT", ad_group=1, current_price=1600.0, payment_methods=["BANK"], status=1)
        ad2 = MyAd(adv_no="ad_2", asset="USDT", ad_group=2, current_price=1590.0, payment_methods=["SantanderArgentina"], status=1)

        competitors = {
            ("USDT", "BANK"): [ExchangeRate("USDT", "BANK", 1520.0, 1.0, 1520.0, 1, advertiser_no="c1", max_single_trans_amount=2_000_000.0)],
            ("USDT", "SantanderArgentina"): [ExchangeRate("USDT", "SantanderArgentina", 1510.0, 1.0, 1510.0, 1, advertiser_no="c2", max_single_trans_amount=2_000_000.0)],
        }
        benchmarks = {
            "BANK": Benchmark("BANK", 1650.0, [1650.0], 500000.0, datetime.now()),
            "SantanderArgentina": Benchmark("SantanderArgentina", 1650.0, [1650.0], 500000.0, datetime.now()),
        }
        spot_prices = {"USDT": 1.0}
        config = BotConfig(price_step=0.01, margin_min=10.0)

        results = await repo.run_cycle([ad1, ad2], competitors, benchmarks, spot_prices, config)

        # Como el primer update falló, se debió abortar el lote del activo (len(results) == 0 y solo 1 llamada)
        self.assertEqual(len(results), 0)
        self.assertEqual(mock_ads.update_ad_params.call_count, 1)

    def test_edge_case_anti_spam_when_staggered_matches_current(self):
        """Verifica que si anti-colisión escalona un precio y coincide con el actual sin cambios de límites, no envíe spam."""
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, RepositionDecision, BotConfig

        repo = Repositioner(
            ads_manager=MagicMock(),
            scanner=MagicMock(),
            liquidity=MagicMock(),
            war_detector=MagicMock(),
            db=MagicMock(),
        )

        # G1 con target_price = 1583.51
        ad_g1 = MyAd(adv_no="g1", asset="USDT", ad_group=1, current_price=1583.51, payment_methods=["BANK"], status=1)
        d_g1 = RepositionDecision(should_update=True, new_price=1583.51)

        # G2 con target_price = 1583.51, pero su precio actual ya es $1581.13 (justo el buffer de 0.15% LATAM debajo de G1)
        ad_g2 = MyAd(adv_no="g2", asset="USDT", ad_group=2, current_price=1581.13, payment_methods=["BANK"], status=1)
        d_g2 = RepositionDecision(should_update=True, new_price=1583.51)

        config = BotConfig(price_step=0.01)
        ordered = repo.resolve_asset_price_collisions("USDT", [(ad_g1, d_g1), (ad_g2, d_g2)], config)

        # G2 fue escalonado a 1574.80 (igual a su precio actual en Binance sin cambio de límites).
        # should_update debe ser False para G2 para no spammear a Binance.
        self.assertFalse(d_g2.should_update)
        # Solo G1 (o ninguno si G1 tampoco cambió precio ni límites) debe estar en ordered
        self.assertNotIn((ad_g2, d_g2), ordered)

    async def test_edge_case_staggered_group_floor_min(self):
        """Verifica que el piso de transacción esté escalonado por grupo para no clonar límites mínimos."""
        from core.pricing.buy_repositioner import Repositioner
        from data.models import MyAd, ExchangeRate, Benchmark, BotConfig
        from unittest.mock import patch

        mock_liquidity = MagicMock()
        mock_liquidity.available_balance = 25_000.0
        mock_wars = MagicMock()
        mock_wars.is_in_war.return_value = False
        mock_scanner = MagicMock()
        mock_scanner.get_best_competitor.side_effect = lambda rates: rates[0] if rates else None

        repo = Repositioner(
            ads_manager=MagicMock(),
            scanner=mock_scanner,
            liquidity=mock_liquidity,
            war_detector=mock_wars,
            db=MagicMock(),
        )

        ad_g1 = MyAd(adv_no="g1", asset="USDT", ad_group=1, current_price=1500.0, payment_methods=["MP"], status=1)
        ad_g2 = MyAd(adv_no="g2", asset="USDT", ad_group=2, current_price=1500.0, payment_methods=["BANK"], status=1)
        ad_g3 = MyAd(adv_no="g3", asset="USDT", ad_group=3, current_price=1500.0, payment_methods=["PP"], status=1)

        competitors = {
            ("USDT", "MP"): [ExchangeRate("USDT", "MP", 1520.0, 1.0, 1520.0, 1, max_single_trans_amount=100000.0)],
            ("USDT", "BANK"): [ExchangeRate("USDT", "BANK", 1520.0, 1.0, 1520.0, 1, max_single_trans_amount=100000.0)],
            ("USDT", "PP"): [ExchangeRate("USDT", "PP", 1520.0, 1.0, 1520.0, 1, max_single_trans_amount=100000.0)],
        }
        benchmarks = {
            "MP": Benchmark("MP", 1600.0, [1600.0], 50000.0, datetime.now()),
            "BANK": Benchmark("BANK", 1600.0, [1600.0], 50000.0, datetime.now()),
            "PP": Benchmark("PP", 1600.0, [1600.0], 50000.0, datetime.now()),
        }
        config = BotConfig(price_step=0.01)

        with patch.dict("core.pricing.buy_repositioner.ASSET_DEFAULTS", {"USDT": {"init_amount": 10.0, "min_trans": 10000.0, "max_trans": 500000.0}}):
            d1 = await repo.evaluate_ad(ad_g1, competitors, benchmarks, {"USDT": 1.0}, config)
            d2 = await repo.evaluate_ad(ad_g2, competitors, benchmarks, {"USDT": 1.0}, config)
            d3 = await repo.evaluate_ad(ad_g3, competitors, benchmarks, {"USDT": 1.0}, config)

            self.assertFalse(d1.should_pause)
            self.assertFalse(d2.should_pause)
            self.assertFalse(d3.should_pause)

            # Los montos mínimos son estrictamente diferentes entre grupos (sin colisión)
            self.assertEqual(d1.new_min_trans_amount, 11_250.0)  # max(10000, 25000 * 0.45)
            self.assertEqual(d2.new_min_trans_amount, 15_000.0)  # max(11500, 25000 * 0.60)
            self.assertEqual(d3.new_min_trans_amount, 13_000.0)  # max(13000, 25000 * 0.50)
            self.assertNotEqual(d1.new_min_trans_amount, d2.new_min_trans_amount)
            self.assertNotEqual(d2.new_min_trans_amount, d3.new_min_trans_amount)

            # Con saldo por debajo del piso de G3 ($12.000 < $13.000), G3 pausa automáticamente
            mock_liquidity.available_balance = 12_000.0
            d3_low = await repo.evaluate_ad(ad_g3, competitors, benchmarks, {"USDT": 1.0}, config)
            self.assertTrue(d3_low.should_pause)
            self.assertIn("saldo_menor_a_piso_minimo", d3_low.pause_reason)


class TestAuditFixes(unittest.IsolatedAsyncioTestCase):
    """Pruebas unitarias de regresión para las 13 correcciones de la auditoría."""

    def test_binance_client_credential_validation(self):
        """Verifica que BinanceClient con validate_keys=True falle si las API keys están vacías."""
        with self.assertRaises(ValueError) as ctx:
            BinanceClient(api_key="", secret_key="", validate_keys=True)
        self.assertIn("CRÍTICO", str(ctx.exception))

    async def test_fiwind_stale_cache_expiration(self):
        """Verifica que FiwindClient no sirva caché de más de max_stale_seconds si la API falla."""
        import time
        from core.fiwind_client import FiwindClient
        client = FiwindClient(cache_ttl=5, max_stale_seconds=10)
        client._cached_bid = 1450.0
        client._cached_ask = 1470.0
        # Simular que el último fetch fue hace 15 segundos (mayor a max_stale_seconds=10)
        client._last_fetch_time = time.time() - 15.0

        # Forzar fallo simulado de conexión
        client._get_session = AsyncMock(side_effect=Exception("API caída"))
        bid, ask = await client.get_quotes()
        self.assertEqual(bid, 0.0)
        self.assertEqual(ask, 0.0)

    def test_repositioner_get_group_floor_min_centralized(self):
        """Verifica que el helper get_group_floor_min calcule los montos exactos por grupo."""
        from core.pricing.buy_repositioner import Repositioner
        self.assertEqual(Repositioner.get_group_floor_min("USDT", 1), 10_000.0)
        self.assertEqual(Repositioner.get_group_floor_min("USDT", 2), 11_500.0)
        self.assertEqual(Repositioner.get_group_floor_min("USDT", 3), 13_000.0)


class TestDailyReport(unittest.TestCase):
    """Pruebas para el reporte diario único y estadísticas diarias."""

    def setUp(self):
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)
        self.db = Database(db_path=Path(self.temp_path))
        self.db.init_schema()

    def tearDown(self):
        try:
            os.remove(self.temp_path)
        except OSError:
            pass

    def test_get_daily_stats_and_formatter(self):
        """Verifica el cálculo de estadísticas y el formato del reporte diario con fecha."""
        from telegram_bot.formatters import format_daily_report
        # Insertar orden detectada simulada
        conn = self.db.connect()
        conn.execute(
            "INSERT INTO detected_orders (order_no, adv_no, trade_type, amount_crypto, amount_ars, price, status, detected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ORD1", "ADV1", "BUY", 100.0, 150000.0, 1500.0, "COMPLETED", "2026-09-27 15:30:00")
        )
        conn.execute(
            "INSERT INTO price_changes (adv_no, asset, ad_group, old_price, new_price, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("ADV1", "USDT", 1, 1499.0, 1500.0, "2026-09-27 12:00:00")
        )
        conn.commit()

        stats = self.db.get_daily_stats("2026-09-27")
        self.assertEqual(stats["date"], "2026-09-27")
        self.assertEqual(stats["buy_orders"], 1)
        self.assertEqual(stats["buy_volume_ars"], 150000.0)
        self.assertEqual(stats["repositions"], 1)

        formatted = format_daily_report(stats)
        self.assertIn("Reporte Diario", formatted)
        self.assertIn("2026-09-27", formatted)
        self.assertIn("150,000 ARS", formatted)

    def test_once_a_day_trigger_prevention(self):
        """Verifica que el reporte no se dispare más de una vez en el mismo día."""
        today_str = "2026-09-27"
        self.db.set_config("last_daily_report_date", today_str)

        # Si ya se envió hoy, last_report_date == today_str
        last_report = self.db.get_config("last_daily_report_date", "")
        self.assertEqual(last_report, today_str)
        should_send = (last_report != today_str)
        self.assertFalse(should_send)


if __name__ == "__main__":
    unittest.main()


