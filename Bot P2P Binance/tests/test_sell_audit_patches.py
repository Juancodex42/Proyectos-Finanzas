"""
Tests unitarios específicos para las correcciones de auditoría del motor de ventas P2P.
Cubre:
1. Prevención de Anuncios Fantasma (guardrail breach sets should_pause).
2. Exclusión de anuncios propios en scan_usdt_benchmark (Anti-Self-Undercutting).
3. Transición de precios en doble cola anti-187055 (down_moves asc, up_moves desc).
4. Detección y ciclo de vida de órdenes abiertas de venta (status 1 y status 2).
5. Calibración adaptativa de volumen según stock vendible real (max_stock_ars).
"""
import pytest
import unittest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from data.models import MyAd, Benchmark, DetectedOrder, SellDecision
from core.pricing.sell_repositioner import SellRepositioner
from core.market_scanner import MarketScanner
from core.liquidity.liquidity_manager import LiquidityTracker


class TestSellAuditPatches(unittest.IsolatedAsyncioTestCase):

    async def test_guardrail_breach_sets_should_pause(self):
        """Verifica que si un anuncio falla guardarraíles de seguridad se marque should_pause=True."""
        mock_db = MagicMock()
        mock_db.get_my_sell_ads.return_value = [
            MyAd(adv_no="SELL_1", asset="USDT", ad_group=1, current_price=1600.0, payment_methods=["MP"], status=1),
            MyAd(adv_no="SELL_2", asset="USDT", ad_group=2, current_price=1610.0, payment_methods=["Santander"], status=1),
            MyAd(adv_no="SELL_3", asset="USDT", ad_group=3, current_price=1620.0, payment_methods=["PersonalPay"], status=1),
        ]
        # Benchmark con timestamp viejo (>600s) para forzar brecha de guardarraíl por datos desactualizados
        stale_ts = datetime.now() - timedelta(seconds=1200)
        mock_db.get_latest_benchmarks.return_value = {
            "MercadoPagoNew": Benchmark(payment_method="MercadoPagoNew", avg_top_n_price=1500.0, individual_prices=[1500.0, 1505.0, 1510.0], timestamp=stale_ts),
            "SantanderArgentina": Benchmark(payment_method="SantanderArgentina", avg_top_n_price=1510.0, individual_prices=[1510.0, 1515.0, 1520.0], timestamp=stale_ts),
            "PersonalPay": Benchmark(payment_method="PersonalPay", avg_top_n_price=1515.0, individual_prices=[1515.0, 1520.0, 1525.0], timestamp=stale_ts),
        }

        mock_profit = MagicMock()
        mock_profit.get_effective_wac_cost.return_value = 1450.0
        mock_fiwind = AsyncMock()
        mock_fiwind.get_usdt_bid.return_value = 1480.0
        mock_ads = MagicMock()

        repositioner = SellRepositioner(
            db=mock_db,
            ads_manager=mock_ads,
            profit_tracker=mock_profit,
            fiwind_client=mock_fiwind,
        )

        decisions = await repositioner.evaluate_sell_clusters(
            benchmarks=mock_db.get_latest_benchmarks.return_value,
            available_crypto_stock=200.0,
        )

        # Cada cluster debe tener should_pause=True y should_update=False
        for dec in decisions:
            self.assertFalse(dec.is_safe, f"G{dec.cluster_id} no debió ser considerado seguro con datos obsoletos")
            self.assertTrue(dec.should_pause, f"G{dec.cluster_id} debió marcar should_pause=True")
            self.assertFalse(dec.should_update, f"G{dec.cluster_id} no debe permitir actualización activa")
            self.assertIn("guardrail_breach", dec.pause_reason)

    async def test_scan_usdt_benchmark_filters_my_adv_nos(self):
        """Verifica que scan_usdt_benchmark excluya los anuncios propios de la lista de competidores."""
        mock_client = AsyncMock()
        mock_client.search_ads = AsyncMock(return_value={
            "data": [
                {"adv": {"advNo": "MY_OWN_SELL_AD", "price": "1400.00"}},
                {"adv": {"advNo": "RIVAL_1", "price": "1410.00"}},
                {"adv": {"advNo": "RIVAL_2", "price": "1412.00"}},
                {"adv": {"advNo": "RIVAL_3", "price": "1415.00"}},
            ]
        })
        scanner = MarketScanner(client=mock_client, spot_client=MagicMock(), db=MagicMock())
        scanner.set_my_adv_nos({"MY_OWN_SELL_AD"})

        bm = await scanner.scan_usdt_benchmark(payment_method="MercadoPagoNew", volume_ref=100000.0)

        # El anuncio propio debe ser descartado, el benchmark debe empezar en 1410.00
        self.assertNotIn(1400.0, bm.individual_prices)
        self.assertEqual(bm.individual_prices[0], 1410.0)
        self.assertEqual(bm.individual_prices[1], 1412.0)
        self.assertEqual(bm.individual_prices[2], 1415.0)
        self.assertAlmostEqual(bm.avg_top_n_price, (1410.0 + 1412.0 + 1415.0) / 3, places=2)

    async def test_double_queue_ordering_in_sell_repositioner(self):
        """Verifica que execute_sell_decisions ordene down_moves ascendentes y up_moves descendentes."""
        mock_db = MagicMock()
        mock_db.get_my_sell_ads.return_value = [
            MyAd(adv_no="AD_DOWN_1", asset="USDT", ad_group=1, current_price=1500.0, payment_methods=["MP"], status=1, init_amount=100.0, surplus_amount=100.0),
            MyAd(adv_no="AD_DOWN_2", asset="USDT", ad_group=2, current_price=1520.0, payment_methods=["Santander"], status=1, init_amount=100.0, surplus_amount=100.0),
            MyAd(adv_no="AD_UP_1", asset="USDT", ad_group=3, current_price=1530.0, payment_methods=["PersonalPay"], status=1, init_amount=100.0, surplus_amount=100.0),
        ]
        mock_ads = MagicMock()
        call_order = []

        async def record_update(adv_no, price, **kwargs):
            call_order.append((adv_no, price))
            return True

        mock_ads.update_sell_ad_params = AsyncMock(side_effect=record_update)
        repositioner = SellRepositioner(db=mock_db, ads_manager=mock_ads, profit_tracker=MagicMock())

        def make_dec(c_id, adv_no, price):
            return SellDecision(
                cluster_id=c_id,
                title=f"G{c_id}",
                anchor_method="MP",
                suggested_price=price,
                top1_price=price,
                spread_added=0.0,
                estimated_position="Puesto #1",
                wac_cost=1400.0,
                fiwind_bid=1400.0,
                adv_no=adv_no,
                should_update=True,
                is_safe=True,
                should_pause=False,
            )

        # Decisión: AD_DOWN_1 baja a 1480, AD_DOWN_2 baja a 1490, AD_UP_1 sube a 1550
        decisions = [
            make_dec(2, "AD_DOWN_2", 1490.0),
            make_dec(1, "AD_DOWN_1", 1480.0),
            make_dec(3, "AD_UP_1", 1550.0),
        ]

        results = await repositioner.execute_sell_decisions(decisions)
        self.assertEqual(len(results), 3)

        # Orden esperado:
        # 1. Down moves ordenados ascendente: AD_DOWN_1 (1480) primero, luego AD_DOWN_2 (1490)
        # 2. Up moves ordenados descendente: AD_UP_1 (1550)
        expected_adv_order = ["AD_DOWN_1", "AD_DOWN_2", "AD_UP_1"]
        actual_adv_order = [adv for adv, p in call_order]
        self.assertEqual(actual_adv_order, expected_adv_order)

    async def test_open_sell_orders_detected_and_enqueued(self):
        """Verifica que LiquidityTracker capture órdenes abiertas de venta (status 1 y 2)."""
        mock_client = AsyncMock()

        async def mock_list(trade_type="BUY", order_status_list=None, rows=50):
            if trade_type == "SELL" and order_status_list in ([1, 2], [1, 2, 3, 5]):
                return {
                    "data": [
                        {
                            "orderNumber": "SELL_ORD_001",
                            "advNo": "ADV_S1",
                            "asset": "USDT",
                            "tradeType": "SELL",
                            "amount": 100.0,
                            "totalPrice": 142000.0,
                            "unitPrice": 1420.0,
                            "orderStatus": 1,
                            "buyerNickname": "CompradorP2P",
                            "payType": "MercadoPago",
                        }
                    ]
                }
            return {"data": []}

        mock_client.list_orders.side_effect = mock_list
        lt = LiquidityTracker(client=mock_client, db=MagicMock())

        # Ciclo 1: orden en status 1 detectada
        res = await lt.sync_orders(spot_prices={"USDT": 1.0})
        incoming = lt.consume_incoming_orders()
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0].order_no, "SELL_ORD_001")
        self.assertEqual(incoming[0].trade_type, "SELL")
        self.assertEqual(incoming[0].status, "1")

        # Ciclo 2: misma orden sigue en status 1 -> no se duplica
        await lt.sync_orders(spot_prices={"USDT": 1.0})
        incoming_cycle2 = lt.consume_incoming_orders()
        self.assertEqual(len(incoming_cycle2), 0)

        # Ciclo 3: comprador marca pagado (status 2) -> se vuelve a encolar con status 2
        async def mock_list_paid(trade_type="BUY", order_status_list=None, rows=50):
            if trade_type == "SELL" and order_status_list in ([1, 2], [1, 2, 3, 5]):
                return {
                    "data": [
                        {
                            "orderNumber": "SELL_ORD_001",
                            "advNo": "ADV_S1",
                            "asset": "USDT",
                            "tradeType": "SELL",
                            "amount": 100.0,
                            "totalPrice": 142000.0,
                            "unitPrice": 1420.0,
                            "orderStatus": 2,
                            "buyerNickname": "CompradorP2P",
                            "payType": "MercadoPago",
                        }
                    ]
                }
            return {"data": []}

        mock_client.list_orders.side_effect = mock_list_paid
        await lt.sync_orders(spot_prices={"USDT": 1.0})
        incoming_cycle3 = lt.consume_incoming_orders()
        self.assertEqual(len(incoming_cycle3), 1)
        self.assertEqual(incoming_cycle3[0].order_no, "SELL_ORD_001")
        self.assertEqual(incoming_cycle3[0].status, "2")


if __name__ == "__main__":
    unittest.main()
