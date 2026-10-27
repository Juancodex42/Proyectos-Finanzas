import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core.ads.manager import AdsManager
from core.network.binance_api import BinanceClientError
from data.models import MyAd


class TestSellReconcileCooldown(unittest.IsolatedAsyncioTestCase):

    async def test_create_sell_ad_retries_on_187000(self):
        """Verifica que create_sell_ad reintente cuando Binance responde con error 187000."""
        mock_client = MagicMock()
        mock_db = MagicMock()

        # Primer intento lanza 187000, segundo intento tiene éxito
        mock_client.create_ad = AsyncMock(side_effect=[
            BinanceClientError(400, "-9000", "187000"),
            {"code": "000000", "data": "1234567890", "success": True},
        ])

        mgr = AdsManager(client=mock_client, db=mock_db)

        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            adv_no = await mgr.create_sell_ad(
                price=1620.0,
                init_amount=200.0,
                min_trans_amount=15000.0,
                max_trans_amount=300000.0,
                trade_methods=[{"identifier": "MercadoPagoNew", "payId": 1}],
                online_now=False,
            )

            self.assertEqual(adv_no, "1234567890")
            self.assertEqual(mock_client.create_ad.call_count, 2)
            mock_sleep.assert_called_once()

    async def test_reconcile_sell_ads_creates_all_clusters_with_cooldown(self):
        """Verifica que reconcile_sell_ads cree los 3 clusters respetando cooldown."""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_db.get_my_sell_ads.return_value = []
        mock_db.get_latest_benchmarks.return_value = {}

        created_advs = ["ADV_G1", "ADV_G2", "ADV_G3"]
        mock_client.create_ad = AsyncMock(side_effect=[
            {"code": "000000", "data": adv, "success": True} for adv in created_advs
        ])
        mock_client.list_my_ads = AsyncMock(return_value={"data": []})

        mgr = AdsManager(client=mock_client, db=mock_db)

        pay_id_map = {
            "MercadoPagoNew": 1,
            "LemonCash": 2,
            "SantanderArgentina": 3,
            "bancogalicia": 4,
            "personalpay": 5,
            "Fiwind": 6,
        }

        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            stats = await mgr.reconcile_sell_ads(
                pay_id_map=pay_id_map,
                available_crypto_stock=250.0,
                set_online=False,
            )

            self.assertEqual(stats["created"], 3)
            self.assertEqual(stats["errors"], 0)
            self.assertEqual(len(stats["clusters"]), 3)
            # Debe haber dormido al menos 3 veces por cada cluster intentado
            self.assertEqual(mock_sleep.call_count, 3)
