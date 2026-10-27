import sys
import os
sys.path.insert(0, os.path.abspath("."))
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from data.models import MyAd
from core.pricing.sell_repositioner import SellRepositioner, SellDecision
from core.ads.manager import AdsManager

class TestSellSharedInventorySync(unittest.IsolatedAsyncioTestCase):
    async def test_execute_sell_decisions_downsizes_ad_on_shared_inventory_drop(self):
        """
        Anti-187049: Verifica que si el saldo libre en Fondos baja (ej. de 700 a 150 USDT tras una venta en G1),
        el anuncio hermano G2 (que aún tiene surplus 700 USDT registrado en Binance) envíe su nuevo initAmount menor.
        """
        mock_ads = MagicMock()
        mock_ads.update_sell_ad_params = AsyncMock(return_value=True)
        mock_ads.resume_sell_ad = AsyncMock(return_value=True)
        mock_db = MagicMock()

        # Anuncio G2 en Binance con 700 USDT registrados (no hubo venta directa en él)
        ad_g2 = MyAd(
            adv_no="ADV_G2_700",
            asset="USDT",
            ad_group=2,
            init_amount=700.0,
            surplus_amount=700.0,
            current_price=1625.0,
            payment_methods=["SantanderArgentina"],
            status=1,
        )
        mock_db.get_my_sell_ads.return_value = [ad_g2]
        mock_profit = MagicMock()
        repo = SellRepositioner(db=mock_db, ads_manager=mock_ads, profit_tracker=mock_profit)

        # Tras la venta en G1, Fondos ahora tiene 150 USDT disponibles
        dec_downsize = SellDecision(
            cluster_id=2,
            title="G2",
            anchor_method="Santander",
            suggested_price=1625.5,
            top1_price=1625.0,
            spread_added=0.5,
            estimated_position="Puesto #2",
            wac_cost=1550.0,
            fiwind_bid=1610.0,
            is_safe=True,
            safety_reason="OK",
            adv_no="ADV_G2_700",
            status=1,
            methods=["Santander"],
            speed_label="Med",
            should_update=True,
            new_init_amount=150.0,  # Saldo real en Fondos
            new_min_trans_amount=120000.0,
            new_max_trans_amount=240000.0,
        )

        results = await repo.execute_sell_decisions([dec_downsize])
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0][1])

        mock_ads.update_sell_ad_params.assert_called_once()
        k = mock_ads.update_sell_ad_params.call_args.kwargs
        # Debe enviar init_amount = 150.0 para reducir el stock en Binance y evitar 187049
        self.assertEqual(k["init_amount"], 150.0)

    async def test_execute_sell_decisions_reloads_ad_below_min_transaction(self):
        """
        Anti-187040 / Anti-187006: Verifica que si un anuncio tiene 59 USDT de surplus pero el mínimo
        es 120 USDT ($195k ARS), el bot lo detecte como insuficiente y envíe initAmount para recargarlo
        al saldo de Fondos disponible.
        """
        mock_ads = MagicMock()
        mock_ads.update_sell_ad_params = AsyncMock(return_value=True)
        mock_ads.resume_sell_ad = AsyncMock(return_value=True)
        mock_db = MagicMock()

        # Anuncio G1 con 59 USDT restantes y 644 USDT ejecutados previamente (total original 703 USDT)
        ad_g1 = MyAd(
            adv_no="ADV_G1_LOW",
            asset="USDT",
            ad_group=1,
            init_amount=703.0,
            surplus_amount=59.0,
            current_price=1624.0,
            payment_methods=["MercadoPagoNew"],
            status=3,
        )
        mock_db.get_my_sell_ads.return_value = [ad_g1]
        mock_profit = MagicMock()
        repo = SellRepositioner(db=mock_db, ads_manager=mock_ads, profit_tracker=mock_profit)

        # Fondos tiene 240 USDT disponibles, mínimo calculado es $195.000 ARS (~120 USDT)
        dec_reload = SellDecision(
            cluster_id=1,
            title="G1",
            anchor_method="MP",
            suggested_price=1624.0,
            top1_price=1623.5,
            spread_added=0.5,
            estimated_position="Puesto #1",
            wac_cost=1550.0,
            fiwind_bid=1610.0,
            is_safe=True,
            safety_reason="OK",
            adv_no="ADV_G1_LOW",
            status=3,
            methods=["MP"],
            speed_label="Fast",
            should_update=True,
            new_init_amount=240.0,  # Saldo disponible a asignar
            new_min_trans_amount=195000.0,  # ~120 USDT > 59 USDT actuales
            new_max_trans_amount=390000.0,
        )

        results = await repo.execute_sell_decisions([dec_reload])
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0][1])

        mock_ads.update_sell_ad_params.assert_called_once()
        k = mock_ads.update_sell_ad_params.call_args.kwargs
        # executed = 703 - 59 = 644. total_init = 644 + 240 = 884.0
        self.assertEqual(k["init_amount"], 884.0)

    async def test_reconcile_sell_ads_syncs_under_threshold_and_desynced(self):
        """
        Verifica que reconcile_sell_ads detecte anuncios con surplus inferior al mínimo
        o desfasados respecto a Fondos, y los sincronice vía quickedit.
        """
        mock_client = MagicMock()
        mock_client.close_ad = AsyncMock()
        mock_client.update_ad = AsyncMock(return_value={"code": "000000", "data": True, "success": True})
        mock_db = MagicMock()

        # G1 con 59 USDT (por debajo de su mínimo de $195k ARS)
        ad_g1 = MyAd(
            adv_no="ADV_G1",
            asset="USDT",
            ad_group=1,
            init_amount=703.0,
            surplus_amount=59.0,
            current_price=1624.0,
            min_trans_amount=195000.0,
            max_trans_amount=390000.0,
            payment_methods=["MercadoPagoNew"],
            status=1,
        )
        mock_db.get_my_sell_ads.return_value = [ad_g1]

        mgr = AdsManager(client=mock_client, db=mock_db)
        mgr.sync_my_sell_ads = AsyncMock(return_value=[ad_g1])

        pay_id_map = {"MercadoPagoNew": 1}

        stats = await mgr.reconcile_sell_ads(
            pay_id_map=pay_id_map,
            available_crypto_stock=240.0,
            set_online=False,
        )

        self.assertEqual(stats["updated"], 1)
        # target_init = (703 - 59) + 240 = 884.0
        self.assertEqual(ad_g1.init_amount, 884.0)
        self.assertEqual(ad_g1.surplus_amount, 240.0)

if __name__ == "__main__":
    unittest.main()
