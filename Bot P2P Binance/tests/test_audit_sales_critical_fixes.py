"""
Tests automatizados para las correcciones de auditoría de lógica de negocio crítica en Ventas P2P:
1. Anti-Spoofing: top1 saneado con filtro de mediana en calculate_book_aware_sell_price.
2. Anti-Explosión WAC: Altcoins sin tc_implicito usan fallback de tipo de cambio en vez de u_equiv = crypto.
3. Transición de Inventario y Lookback: compras previas se consideran en WAC y calculate_profit no inventa ganancia con -10.
4. Descongelamiento de Anuncios: Anuncios pausados (status != 1) fuerzan should_update=True para reactivarse.
5. Soberanía del Operador: execute_sell_decisions respeta config.paused_ads y no reactiva a la fuerza.
6. Anti-Error 187040: decrement_ad_surplus descuenta surplus_amount en my_sell_ads.
7. Frescura de Datos: validate_data_freshness rechaza desvíos negativos anómalos (desfase UTC/reloj).
8. Profundidad de Libro: evaluate_sell_clusters busca métodos alternativos con >=2 vendedores en el cluster.
"""
import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from config.settings import DEFAULT_BINANCE_SELL_TC_FALLBACK
from core.sell_advisor import calculate_book_aware_sell_price
from core.sell_guardrails import SellGuardrails
from core.pricing.sell_repositioner import SellRepositioner
from core.profit_tracker import ProfitTracker
from data.database import Database
from data.models import Benchmark, BotConfig, MyAd, SellDecision


class TestAuditSalesCriticalFixes(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_ads = MagicMock()
        self.mock_profit = MagicMock()
        self.mock_fiwind = MagicMock()

    # 1. Anti-Spoofing en Book-Aware
    def test_fix_1_top1_spoofing_sanitized_in_book_aware(self):
        """Verifica que una orden cebo (<2.5% de mediana) no contamine top1 ni el Outlier Cap."""
        # Competidores: 1 spoofing a 1000.0, y 3 reales a 1500.0, 1502.0, 1505.0
        prices_top10 = [1000.0, 1500.0, 1502.0, 1505.0]
        # Con top1 sucio = 1000.0
        suggested = calculate_book_aware_sell_price(
            top1=1000.0,
            prices_top10=prices_top10,
            cluster_id=1,
            default_delta=0.35,
        )
        # El precio sugerido debe estar anclado a ~1501.99 ARS (P2 - 0.01), NUNCA a ~1025.00
        self.assertGreater(suggested, 1400.0, f"Precio sugerido {suggested} cayó en la trampa del spoofing")
        self.assertAlmostEqual(suggested, 1501.99, places=2)

    # 2. Anti-Explosión de WAC en Altcoins
    async def test_fix_2_altcoin_spot_tc_fallback_prevents_wac_explosion(self):
        """Verifica que compras de BTC con tc_implicito=0 no asuman 0.05 BTC = 0.05 USDT inflando WAC a 100M."""
        # Compra de 0.05 BTC por $5.000.000 ARS con tc_implicito = 0.0
        buys_data = [
            {"amount_ars": 5000000.0, "amount_crypto": 0.05, "tc_implicito": 0.0, "asset": "BTC"},
        ]
        mock_conn = MagicMock()
        mock_conn.execute.return_value = MagicMock(fetchall=lambda: buys_data)
        self.mock_db._lock = MagicMock()
        self.mock_db._lock.__enter__ = MagicMock(return_value=None)
        self.mock_db._lock.__exit__ = MagicMock(return_value=None)
        self.mock_db.connect.return_value = mock_conn

        tracker = ProfitTracker(db=self.mock_db)
        wac = tracker.get_effective_wac_cost("2026-10-15")

        # Con 5M ARS y fallback de ~1610 ARS/USDT, equivale a ~3105 USDT.
        # WAC debe ser cercano al tipo de cambio de mercado (~1610), NUNCA $100.000.000
        self.assertLess(wac, 2500.0, f"WAC {wac} explotó anormalmente")
        self.assertGreater(wac, 1000.0)

    # 3. Lookback y Veracidad Contable
    async def test_fix_3_lookback_truthful_accounting(self):
        """Verifica que calculate_profit no invente ganancia con -10.0 si no hay costo conocido."""
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = [
            MagicMock(fetchall=lambda: []),  # buys vacías hoy
            MagicMock(fetchall=lambda: [      # 1 venta de 100 USDT a 1500
                {"order_no": "S1", "asset": "USDT", "amount_crypto": 100.0, "amount_ars": 150000.0, "tc_implicito": 1500.0, "price": 1500.0}
            ]),
            MagicMock(fetchall=lambda: []),  # lookback previo vacío
        ]
        self.mock_db._lock = MagicMock()
        self.mock_db._lock.__enter__ = MagicMock(return_value=None)
        self.mock_db._lock.__exit__ = MagicMock(return_value=None)
        self.mock_db.connect.return_value = mock_conn

        tracker = ProfitTracker(db=self.mock_db)
        with patch.object(tracker, "get_published_sell_price", AsyncMock(return_value=(1500.0, "Test"))):
            report = await tracker.calculate_profit("2026-10-15")

        # Sin historial de compra, no debe inventar ganancia de +$1000 ARS (10 * 100)
        self.assertEqual(report.realized_profit_ars, 0.0)

    # 4. Descongelamiento de Anuncios Pausados
    def test_fix_4_paused_ad_forces_should_update_when_safe(self):
        """Verifica que un anuncio pausado en BD (status=3) fuerce should_update=True aunque el precio no cambie."""
        existing_ad = MyAd(
            adv_no="AD_PAUSED",
            asset="USDT",
            ad_group=1,
            current_price=1585.0,  # Mismo precio sugerido (diferencia 0.0)
            payment_methods=["MP"],
            status=3,              # Pausado OFFLINE
            init_amount=100.0,
            surplus_amount=100.0,
        )
        self.mock_db.get_my_sell_ads.return_value = [existing_ad]

        repositioner = SellRepositioner(
            db=self.mock_db,
            ads_manager=self.mock_ads,
            profit_tracker=self.mock_profit,
            fiwind_client=self.mock_fiwind,
        )

        dec = SellDecision(
            cluster_id=1,
            title="G1",
            anchor_method="MP",
            suggested_price=1585.0,  # Exactamente igual al precio en DB
            top1_price=1584.0,
            spread_added=1.0,
            estimated_position="#2",
            wac_cost=1570.0,
            fiwind_bid=1580.0,
            is_safe=True,
            adv_no="AD_PAUSED",
        )

        resolved = repositioner.resolve_sell_collisions([dec], available_crypto_stock=100.0)
        self.assertEqual(len(resolved), 1)
        # Como estaba pausado en DB, DEBE marcar should_update = True para enviar a Binance y reactivarlo
        self.assertTrue(resolved[0].should_update, "Anuncio pausado debió forzar should_update=True para reactivarse")

    # 5. Soberanía del Operador (config.paused_ads)
    async def test_fix_5_execute_sell_decisions_respects_config_paused_ads(self):
        """Verifica que execute_sell_decisions no reactive un anuncio que está en config.paused_ads."""
        paused_ad = MyAd(
            adv_no="AD_MANUAL_PAUSE",
            asset="USDT",
            ad_group=1,
            current_price=1585.0,
            payment_methods=["MP"],
            status=3,
        )
        self.mock_db.get_my_sell_ads.return_value = [paused_ad]
        cfg = BotConfig(paused_ads=["AD_MANUAL_PAUSE"])
        self.mock_db.load_bot_config.return_value = cfg

        repositioner = SellRepositioner(
            db=self.mock_db,
            ads_manager=self.mock_ads,
            profit_tracker=self.mock_profit,
            fiwind_client=self.mock_fiwind,
        )

        dec = SellDecision(
            cluster_id=1,
            title="G1",
            anchor_method="MP",
            suggested_price=1585.0,
            top1_price=1584.0,
            spread_added=1.0,
            estimated_position="#2",
            wac_cost=1570.0,
            fiwind_bid=1580.0,
            is_safe=True,
            should_update=True,
            adv_no="AD_MANUAL_PAUSE",
        )

        await repositioner.execute_sell_decisions([dec], config=cfg)
        # resume_sell_ad NO debe haber sido llamado
        self.mock_ads.resume_sell_ad.assert_not_called()

    # 6. Anti-Error 187040: decrement_ad_surplus en my_sell_ads
    def test_fix_6_decrement_ad_surplus_supports_sell_ads(self):
        """Verifica que decrement_ad_surplus descuente surplus_amount tanto en my_ads como en my_sell_ads."""
        import tempfile
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tfile.close()
        db = Database(db_path=tfile.name)
        db.init_schema()
        ad_sell = MyAd(
            adv_no="SELL_TEST_1",
            asset="USDT",
            ad_group=1,
            current_price=1500.0,
            payment_methods=["MP"],
            status=1,
            init_amount=500.0,
            surplus_amount=500.0,
            trade_type="SELL",
        )
        db.save_my_sell_ad(ad_sell)

        rem = db.decrement_ad_surplus("SELL_TEST_1", 150.0)
        self.assertEqual(rem, 350.0)

        # Consultar DB directamente
        with db._lock:
            row = db.connect().execute("SELECT surplus_amount FROM my_sell_ads WHERE adv_no = ?", ("SELL_TEST_1",)).fetchone()
            self.assertEqual(row["surplus_amount"], 350.0)

    # 7. Frescura de Datos: rechazo ante reloj adelantado / desfase UTC
    def test_fix_7_data_freshness_rejects_negative_age(self):
        """Verifica que validate_data_freshness rechace timestamps del futuro (desfase UTC -3hs)."""
        future_ts = datetime.now() + timedelta(minutes=10)
        ok, reason = SellGuardrails.validate_data_freshness(future_ts, max_age_seconds=90.0)
        self.assertFalse(ok)
        self.assertIn("desfase", reason.lower())

    # 8. Profundidad de Libro: Fallback a métodos alternativos del cluster
    async def test_fix_8_depth_fallback_to_liquid_method_in_cluster(self):
        """Verifica que si el método ancla tiene 1 vendedor, evaluate_sell_clusters use otro método con >=2."""
        st_now = datetime.now()
        bms = {
            # Ancla con solo 1 vendedor (insuficiente)
            "personalpay": Benchmark(payment_method="personalpay", avg_top_n_price=1590.0, individual_prices=[1590.0], timestamp=st_now),
            # Método secundario del Cluster 3 con 3 vendedores (líquido)
            "Prex": Benchmark(payment_method="Prex", avg_top_n_price=1588.0, individual_prices=[1588.0, 1589.0, 1590.0], timestamp=st_now),
        }
        self.mock_db.get_latest_benchmarks.return_value = bms
        self.mock_profit.get_effective_wac_cost.return_value = 1550.0
        self.mock_fiwind.get_usdt_bid = AsyncMock(return_value=1580.0)

        repositioner = SellRepositioner(
            db=self.mock_db,
            ads_manager=self.mock_ads,
            profit_tracker=self.mock_profit,
            fiwind_client=self.mock_fiwind,
        )

        decisions = await repositioner.evaluate_sell_clusters(benchmarks=bms, available_crypto_stock=200.0)
        g3 = next((d for d in decisions if d.cluster_id == 3), None)
        self.assertIsNotNone(g3)
        # No debe pausarse por profundidad insuficiente porque Prex tenía 3 vendedores
        self.assertTrue(g3.is_safe, f"G3 no debió ser pausado: {g3.safety_reason}")
        self.assertEqual(g3.anchor_method, "Prex")


if __name__ == "__main__":
    unittest.main()
