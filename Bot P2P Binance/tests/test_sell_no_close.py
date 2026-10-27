import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core.ads.manager import AdsManager
from core.pricing.sell_repositioner import SellRepositioner, SellDecision
from data.models import MyAd, BotConfig


class TestSellAdsPermanentNoClose(unittest.IsolatedAsyncioTestCase):
    """
    Verifica que los anuncios de venta sean permanentes:
    - reconcile_sell_ads NUNCA llama a close_ad por remanente agotado o inalcanzable.
    - Se recarga el stock (initAmount) en caliente vía update_sell_ad_params (quickedit).
    - execute_sell_decisions envía initAmount solo cuando hay recarga necesaria.
    """

    async def test_reconcile_sell_ads_recharges_in_place_without_closing(self):
        """Verifica que un anuncio con remanente < 10 USDT sea recargado en caliente sin llamar a close_ad."""
        mock_client = MagicMock()
        mock_client.close_ad = AsyncMock()
        mock_client.create_ad = AsyncMock(return_value={"code": "000000", "data": "ADV_NEW", "success": True})
        mock_client.update_ad = AsyncMock(return_value={"code": "000000", "data": True, "success": True})
        mock_client.list_my_ads = AsyncMock(return_value={"data": []})

        mock_db = MagicMock()
        # Anuncios existentes para los 3 clusters
        ad_g1 = MyAd(
            adv_no="ADV_G1_EXISTING",
            asset="USDT",
            ad_group=1,
            init_amount=100.0,
            surplus_amount=2.0,  # Agotado
            current_price=1620.0,
            payment_methods=["MercadoPagoNew"],
            status=1,
        )
        ad_g2 = MyAd(
            adv_no="ADV_G2_EXISTING",
            asset="USDT",
            ad_group=2,
            init_amount=350.0,
            surplus_amount=350.0,  # Saludable
            current_price=1621.0,
            payment_methods=["SantanderArgentina"],
            status=1,
        )
        ad_g3 = MyAd(
            adv_no="ADV_G3_EXISTING",
            asset="USDT",
            ad_group=3,
            init_amount=350.0,
            surplus_amount=350.0,  # Saludable
            current_price=1620.5,
            payment_methods=["personalpay"],
            status=1,
        )
        mock_db.get_my_sell_ads.return_value = [ad_g1, ad_g2, ad_g3]

        mgr = AdsManager(client=mock_client, db=mock_db)
        mgr.sync_my_sell_ads = AsyncMock(return_value=[ad_g1, ad_g2, ad_g3])

        pay_id_map = {"MercadoPagoNew": 1, "LemonCash": 2, "SantanderArgentina": 3, "bancogalicia": 4, "personalpay": 5}

        stats = await mgr.reconcile_sell_ads(
            pay_id_map=pay_id_map,
            available_crypto_stock=350.0,
            set_online=False,
        )

        # 1. NUNCA debe cerrar el anuncio
        mock_client.close_ad.assert_not_called()

        # 2. Debe haber actualizado el anuncio existente agotado
        self.assertEqual(stats["updated"], 1)

        # 3. executed = 100 - 2 = 98. target_init = 98 + 350 = 448.0
        self.assertEqual(ad_g1.init_amount, 448.0)
        self.assertEqual(ad_g1.surplus_amount, 350.0)

        # 4. update_ad debió llamarse con quickedit e initAmount=448.0
        mock_client.update_ad.assert_called()
        call_kwargs = mock_client.update_ad.call_args.kwargs
        self.assertEqual(call_kwargs["adv_no"], "ADV_G1_EXISTING")
        self.assertEqual(call_kwargs["update_mode"], "quickedit")
        self.assertEqual(call_kwargs["initAmount"], 448.0)

    async def test_reconcile_sell_ads_does_not_close_offline_ad_with_high_surplus(self):
        """Verifica que un anuncio pausado con surplus > available no sea cerrado."""
        mock_client = MagicMock()
        mock_client.close_ad = AsyncMock()
        mock_client.create_ad = AsyncMock(return_value={"code": "000000", "data": "ADV_NEW", "success": True})
        mock_client.update_ad = AsyncMock(return_value={"code": "000000", "data": True, "success": True})
        mock_client.list_my_ads = AsyncMock(return_value={"data": []})

        mock_db = MagicMock()
        ad_g2 = MyAd(
            adv_no="ADV_G2_PAUSED",
            asset="USDT",
            ad_group=2,
            init_amount=100.0,
            surplus_amount=100.0,
            current_price=1625.0,
            payment_methods=["SantanderArgentina"],
            status=3,
        )
        mock_db.get_my_sell_ads.return_value = [ad_g2]

        mgr = AdsManager(client=mock_client, db=mock_db)
        mgr.sync_my_sell_ads = AsyncMock(return_value=[ad_g2])

        pay_id_map = {"SantanderArgentina": 3}

        with patch("asyncio.sleep", AsyncMock()):
            stats = await mgr.reconcile_sell_ads(
                pay_id_map=pay_id_map,
                available_crypto_stock=50.0,
                set_online=False,
            )

        # No debe cerrarse en absoluto
        mock_client.close_ad.assert_not_called()
        self.assertEqual(stats["verified"], 1)

    async def test_execute_sell_decisions_sends_init_amount_only_on_replenish(self):
        """Verifica que sell_repositioner envíe initAmount en recarga y lo omita en cambios de precio rutinarios."""
        mock_ads = MagicMock()
        mock_ads.update_sell_ad_params = AsyncMock(return_value=True)
        mock_ads.resume_sell_ad = AsyncMock(return_value=True)
        mock_db = MagicMock()

        # Anuncio con 1 USDT de surplus (agotado)
        ad_depleted = MyAd(
            adv_no="ADV_DEPLETED",
            asset="USDT",
            ad_group=1,
            init_amount=200.0,
            surplus_amount=1.0,
            current_price=1620.0,
            payment_methods=["MercadoPagoNew"],
            status=1,
        )
        # Anuncio con 300 USDT de surplus (saludable)
        ad_healthy = MyAd(
            adv_no="ADV_HEALTHY",
            asset="USDT",
            ad_group=2,
            init_amount=500.0,
            surplus_amount=300.0,
            current_price=1622.0,
            payment_methods=["SantanderArgentina"],
            status=1,
        )
        mock_db.get_my_sell_ads.return_value = [ad_depleted, ad_healthy]

        mock_profit = MagicMock()
        repo = SellRepositioner(db=mock_db, ads_manager=mock_ads, profit_tracker=mock_profit)

        # 1. Caso Recarga: Anuncio agotado recibiendo 350 USDT
        dec_replenish = SellDecision(
            cluster_id=1,
            title="G1",
            anchor_method="MP",
            suggested_price=1620.5,
            top1_price=1620.0,
            spread_added=0.5,
            estimated_position="Puesto #2",
            wac_cost=1550.0,
            fiwind_bid=1610.0,
            is_safe=True,
            safety_reason="OK",
            adv_no="ADV_DEPLETED",
            status=1,
            methods=["MP"],
            speed_label="Fast",
            should_update=True,
            new_init_amount=350.0,
            new_min_trans_amount=15000.0,
            new_max_trans_amount=300000.0,
        )

        results = await repo.execute_sell_decisions([dec_replenish])
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0][1])

        # executed = 200 - 1 = 199. total_init = 199 + 350 = 549.0
        mock_ads.update_sell_ad_params.assert_called_once()
        k = mock_ads.update_sell_ad_params.call_args.kwargs
        self.assertEqual(k["init_amount"], 549.0)

        # 2. Caso Rutinario: Anuncio con stock saludable con cambio menor de precio
        mock_ads.update_sell_ad_params.reset_mock()
        dec_routine = SellDecision(
            cluster_id=2,
            title="G2",
            anchor_method="Santander",
            suggested_price=1622.8,
            top1_price=1622.0,
            spread_added=0.8,
            estimated_position="Puesto #2",
            wac_cost=1550.0,
            fiwind_bid=1610.0,
            is_safe=True,
            safety_reason="OK",
            adv_no="ADV_HEALTHY",
            status=1,
            methods=["Santander"],
            speed_label="Med",
            should_update=True,
            new_init_amount=300.0,  # Sin variación de stock
            new_min_trans_amount=15000.0,
            new_max_trans_amount=400000.0,
        )

        results2 = await repo.execute_sell_decisions([dec_routine])
        self.assertEqual(len(results2), 1)
        self.assertTrue(results2[0][1])

        # En cambio rutinario de precio, init_amount debe ser None para no enviar initAmount
        mock_ads.update_sell_ad_params.assert_called_once()
        k2 = mock_ads.update_sell_ad_params.call_args.kwargs
        self.assertIsNone(k2["init_amount"])


if __name__ == "__main__":
    unittest.main()
