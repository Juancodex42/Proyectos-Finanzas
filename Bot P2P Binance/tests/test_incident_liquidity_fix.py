"""
Pruebas unitarias para validar las soluciones a los 5 fallos críticos del incidente de liquidez
y el blindaje estricto de anuncios de venta.
"""
import unittest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from data.models import MyAd, BotConfig, RepositionDecision, DetectedOrder
from core.pricing.buy_repositioner import Repositioner
from core.liquidity.liquidity_manager import LiquidityTracker
from core.ads.manager import AdsManager


class TestIncidentLiquidityFixes(unittest.IsolatedAsyncioTestCase):

    def test_binance_floor_pause_when_unaffordable(self):
        """
        Validación de protección de capital cuando el saldo no alcanza para min_crypto (ej. 35 USDC < 100 USDC).
        El bot NO pausa el anuncio si hay remanente y saldo suficiente para operar (>= group_floor_min),
        sino que mantiene initAmount intacto (None) y acota maxSingleTransAmount al saldo real.
        """
        mock_ads = MagicMock()
        mock_scanner = MagicMock()
        mock_liquidity = MagicMock()
        mock_liquidity.available_balance = 56317.0
        mock_wars = MagicMock()
        mock_db = MagicMock()

        repositioner = Repositioner(mock_ads, mock_scanner, mock_liquidity, mock_wars, mock_db)
        ad = MyAd(
            adv_no="USDC_G1",
            asset="USDC",
            ad_group=1,
            current_price=1607.51,
            payment_methods=["BANK"],
            status=1,
            init_amount=516.0,
            surplus_amount=516.0,
            min_trans_amount=10000.0,
            max_trans_amount=821700.0,
        )
        decision = RepositionDecision()
        config = BotConfig(price_step=0.01)

        # max_affordable_crypto = 56317 / 1607.51 = ~35.03 USDC (< 100 min_crypto)
        repositioner._recompute_ad_amounts_and_limits(ad, decision, 1607.51, config)

        self.assertFalse(decision.should_pause, "El anuncio no debe pausarse si tiene saldo y remanente para operar")
        self.assertTrue(decision.should_update, "should_update debe ser True para acotar los límites excesivos")
        self.assertIsNone(decision.new_init_amount, "initAmount no debe modificarse en Binance si es menor al piso")
        self.assertLessEqual(decision.new_max_trans_amount, 56317.0, "max_trans_amount debe quedar acotado al saldo real")
        self.assertGreaterEqual(decision.new_max_trans_amount, decision.new_min_trans_amount)

    def test_emergency_liquidity_escape_from_passive_cooldown(self):
        """
        Fallo 2: Si el saldo disponible cae y los límites publicados exceden la capacidad,
        el bot debe ignorar el cooldown pasivo de 120s y actualizar inmediatamente los límites.
        """
        mock_ads = MagicMock()
        mock_scanner = MagicMock()
        mock_liquidity = MagicMock()
        # Saldo disponible de $250,000 ARS (alcanza para ~155 USDT > 100 min_crypto)
        mock_liquidity.available_balance = 250000.0
        mock_wars = MagicMock()
        mock_db = MagicMock()

        repositioner = Repositioner(mock_ads, mock_scanner, mock_liquidity, mock_wars, mock_db)
        ad = MyAd(
            adv_no="USDT_G1",
            asset="USDT",
            ad_group=1,
            current_price=1600.0,
            payment_methods=["BANK"],
            status=1,
            init_amount=516.0,
            surplus_amount=516.0,
            min_trans_amount=10000.0,
            max_trans_amount=800000.0,  # Límite viejo que excede ampliamente los 250k disponibles
        )
        # Simular que se actualizó hace solo 30s (menos de 120s de PASSIVE_UPDATE_COOLDOWN_SECONDS)
        repositioner._last_update_ts[ad.adv_no] = time.time() - 30.0

        decision = RepositionDecision()
        config = BotConfig(price_step=0.01)

        # Mismo precio ($1600.0), sin cambio de precio
        repositioner._recompute_ad_amounts_and_limits(ad, decision, 1600.0, config)

        self.assertTrue(decision.should_update, "Debió escapar del cooldown pasivo por emergencia de liquidez")
        self.assertIsNotNone(decision.new_max_trans_amount, "Debió calcular nuevo límite máximo ajustado")
        self.assertLessEqual(decision.new_max_trans_amount, 250000.0, "El nuevo límite máximo no puede superar el disponible")
        self.assertEqual(decision.reason, "amount_or_limits_sync")

    async def test_realtime_surplus_decrement_on_status_1(self):
        """
        Fallo 4: Al entrar una orden en curso (status=1), el remanente (surplus) debe descontarse
        de inmediato en la DB, y no debe descontarse dos veces al completarse (status=4).
        """
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_db.get_all_detected_order_nos.return_value = set()
        mock_db.decrement_ad_surplus.return_value = 22.49

        tracker = LiquidityTracker(client=mock_client, db=mock_db)
        tracker._balance = 850000.0

        # Simular orden abierta de compra por 493.51 USDT
        mock_client.list_orders = AsyncMock(side_effect=[
            # list_orders BUY status [1,2,3,5]
            {
                "data": [
                    {
                        "orderNumber": "ORD_123",
                        "orderStatus": "1",
                        "asset": "USDT",
                        "amount": "493.51",
                        "totalPrice": "793682.0",
                        "advNo": "ADV_USDT_G1",
                    }
                ]
            },
            # list_orders SELL status [1,2,3,5]
            {"data": []},
            # list_orders BUY status [4] (todavía vacía)
            {"data": []},
            # list_orders SELL status [4]
            {"data": []},
        ])

        new_orders = await tracker.sync_orders(spot_prices={"USDT": 1.0})
        self.assertEqual(len(new_orders), 0)  # No es completada
        self.assertEqual(len(tracker._new_incoming_orders), 1)

        # Verificar que decrement_ad_surplus fue llamado en tiempo real con status 1
        mock_db.decrement_ad_surplus.assert_called_once_with("ADV_USDT_G1", 493.51)
        self.assertIn("ORD_123", tracker._surplus_decremented_orders)

        # Ahora simular que en el ciclo siguiente la orden pasa a status 4 (completada)
        mock_db.decrement_ad_surplus.reset_mock()
        mock_client.list_orders = AsyncMock(side_effect=[
            # list_orders BUY status [1,2,3,5] (ya no está abierta)
            {"data": []},
            # list_orders SELL status [1,2,3,5]
            {"data": []},
            # list_orders BUY status [4] (ahora completada)
            {
                "data": [
                    {
                        "orderNumber": "ORD_123",
                        "orderStatus": "4",
                        "asset": "USDT",
                        "amount": "493.51",
                        "totalPrice": "793682.0",
                        "advNo": "ADV_USDT_G1",
                    }
                ]
            },
            # list_orders SELL status [4]
            {"data": []},
        ])

        comp_orders = await tracker.sync_orders(spot_prices={"USDT": 1.0})
        self.assertEqual(len(comp_orders), 1)
        # Verificar que NO se volvió a decrementar (evita doble descuento)
        mock_db.decrement_ad_surplus.assert_not_called()

    async def test_batch_pause_calls_update_ad_status_with_list(self):
        """
        Fallo 5: Pausa masiva debe enviar la lista advNos en batch a update_ad_status.
        """
        mock_client = MagicMock()
        mock_client.update_ad_status = AsyncMock(return_value={"code": "000000", "data": True, "success": True})
        mock_db = MagicMock()

        ads_mgr = AdsManager(mock_client, mock_db)
        adv_list = [f"AD_{i}" for i in range(15)]
        paused_count = await ads_mgr.pause_ads_batch(adv_list, chunk_size=15)

        self.assertEqual(paused_count, 15)
        mock_client.update_ad_status.assert_called_once_with(
            adv_nos=adv_list,
            status=3,
        )
        self.assertEqual(mock_db.update_ad_status.call_count, 15)

    async def test_resume_all_never_resumes_sell_ads(self):
        """
        Seguridad de Ventas: resume_all JAMÁS debe incluir anuncios de venta en la reactivación.
        """
        mock_client = MagicMock()
        mock_client.update_ad_status = AsyncMock(return_value={"code": "000000", "data": True, "success": True})
        mock_db = MagicMock()

        # Configurar anuncios de compra en BD
        buy_ad = MyAd(adv_no="BUY_1", asset="USDT", ad_group=1, current_price=1600.0, payment_methods=["BANK"], status=3, init_amount=100.0)
        mock_db.get_my_ads.return_value = [buy_ad]

        # Configurar anuncios de venta en BD
        sell_ad = MyAd(adv_no="SELL_1", asset="USDT", ad_group=1, current_price=1600.0, payment_methods=["BANK"], status=3, init_amount=100.0, trade_type="SELL")
        mock_db.get_my_sell_ads.return_value = [sell_ad]

        ads_mgr = AdsManager(mock_client, mock_db)
        config = BotConfig()

        resumed_count = await ads_mgr.resume_all(config=config)
        self.assertEqual(resumed_count, 1)

        # Verificar que SOLO se envió BUY_1 y NUNCA SELL_1
        mock_client.update_ad_status.assert_called_once_with(
            adv_nos=["BUY_1"],
            status=1,
        )


if __name__ == "__main__":
    unittest.main()
