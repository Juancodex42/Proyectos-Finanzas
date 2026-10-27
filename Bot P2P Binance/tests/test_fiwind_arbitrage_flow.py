import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core.ads.manager import AdsManager
from config.settings import AD_STATUS_ONLINE, AD_STATUS_OFFLINE
from data.models import MyAd, DetectedOrder
from telegram_bot.bot import TelegramBot


class TestFiwindArbitrageFlow(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = AsyncMock()
        self.mock_db = MagicMock()
        self.mock_engine = MagicMock()
        self.mock_engine.is_fiwind_arbitrage_hold = False
        self.mock_engine.liquidity = MagicMock()
        self.mock_engine.liquidity.balance = 100_000.0
        self.mock_engine.ads_manager = AsyncMock()

    async def test_pause_and_resume_all_sell_ads_in_ads_manager(self):
        """Verifica que pause_all_sell_ads y resume_all_sell_ads actualicen Binance y la base de datos."""
        ad1 = MyAd(adv_no="ad_1", asset="USDT", ad_group=1, current_price=1612.0, payment_methods=["MercadoPagoNew"], status=AD_STATUS_ONLINE, trade_type="SELL")
        ad2 = MyAd(adv_no="ad_2", asset="USDT", ad_group=2, current_price=1617.0, payment_methods=["SantanderArgentina"], status=AD_STATUS_ONLINE, trade_type="SELL")
        ad3 = MyAd(adv_no="ad_3", asset="USDT", ad_group=3, current_price=1616.0, payment_methods=["LemonCash"], status=AD_STATUS_OFFLINE, trade_type="SELL")

        self.mock_db.get_my_sell_ads.return_value = [ad1, ad2, ad3]
        self.mock_client.update_ad_status.return_value = {"code": "000000", "data": True, "success": True}

        mgr = AdsManager(client=self.mock_client, db=self.mock_db)

        # 1. Pausar todos los activos
        paused_count = await mgr.pause_all_sell_ads()
        self.assertEqual(paused_count, 2)
        self.mock_client.update_ad_status.assert_called_with(
            adv_nos=["ad_1", "ad_2"], status=AD_STATUS_OFFLINE
        )
        self.assertEqual(ad1.status, AD_STATUS_OFFLINE)
        self.assertEqual(ad2.status, AD_STATUS_OFFLINE)

        # 2. Reactivar todos
        self.mock_client.update_ad_status.reset_mock()
        self.mock_db.get_my_sell_ads.return_value = [ad1, ad2, ad3]  # Ahora los 3 están offline
        resumed_count = await mgr.resume_all_sell_ads()
        self.assertEqual(resumed_count, 3)
        self.mock_client.update_ad_status.assert_called_with(
            adv_nos=["ad_1", "ad_2", "ad_3"], status=AD_STATUS_ONLINE
        )
        self.assertEqual(ad1.status, AD_STATUS_ONLINE)
        self.assertEqual(ad2.status, AD_STATUS_ONLINE)
        self.assertEqual(ad3.status, AD_STATUS_ONLINE)

    async def test_notify_opportunity_creates_timeout_task(self):
        """Verifica que al notificar oportunidad se cree la tarea de timeout de 5 minutos."""
        bot = TelegramBot(db=self.mock_db, bot_engine=self.mock_engine)
        bot._app = MagicMock()
        mock_msg = MagicMock()
        mock_msg.message_id = 12345
        bot._app.bot.send_message = AsyncMock(return_value=mock_msg)
        bot._chat_id = 999

        order = DetectedOrder(
            order_no="ord_opt_1",
            adv_no="adv_buy_1",
            trade_type="BUY",
            asset="USDT",
            amount_crypto=100.0,
            amount_ars=160_000.0,
            price=1600.0,
            tc_implicito=1600.0,
            payment_method="BANK",
            counterparty="Juan Perez",
            status="COMPLETED",
        )

        with patch.object(bot, "_fiwind_timeout_worker", return_value=None) as mock_worker:
            await bot.notify_opportunity_order(
                order=order,
                fiwind_bid=1610.0,
                binance_sell_tc=1615.0,
                spread=10.0,
                net_profit=1000.0,
            )

            self.assertIn("ord_opt_1", bot.pending_rescues)
            self.assertTrue(bot.pending_rescues["ord_opt_1"]["is_opportunity"])
            self.assertEqual(bot._fiwind_messages.get("ord_opt_1"), 12345)
            self.assertIn("ord_opt_1", bot._fiwind_timers)

            # Limpiar timer
            t = bot._fiwind_timers.pop("ord_opt_1", None)
            if t:
                t.cancel()

    async def test_callback_stay_in_binance_resumes_sales(self):
        """Verifica que el botón 'Quedarme en Binance' cancele el timer y reactive los anuncios de venta."""
        bot = TelegramBot(db=self.mock_db, bot_engine=self.mock_engine)
        bot._admin_ids = {999}
        self.mock_engine.is_fiwind_arbitrage_hold = True

        mock_timer = MagicMock()
        mock_timer.done.return_value = False
        bot._fiwind_timers["ord_stay_1"] = mock_timer
        bot.pending_rescues["ord_stay_1"] = {
            "order_no": "ord_stay_1",
            "is_opportunity": True,
        }

        update = MagicMock()
        update.effective_user.id = 999
        update.effective_chat.id = 999
        update.callback_query.data = "fw_opt_stay_ord_stay_1"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.message.text = "Oportunidad Fiwind"

        await bot._handle_callback(update, MagicMock())

        mock_timer.cancel.assert_called_once()
        self.assertNotIn("ord_stay_1", bot.pending_rescues)
        self.assertFalse(self.mock_engine.is_fiwind_arbitrage_hold)
        self.mock_engine.ads_manager.resume_all_sell_ads.assert_called_once()

    async def test_callback_go_to_fiwind_keeps_hold_active(self):
        """Verifica que el botón 'Ir a Fiwind' mantenga el hold activo y ofrezca confirmación o cancelación."""
        bot = TelegramBot(db=self.mock_db, bot_engine=self.mock_engine)
        bot._admin_ids = {999}
        self.mock_engine.is_fiwind_arbitrage_hold = True

        mock_timer = MagicMock()
        mock_timer.done.return_value = False
        bot._fiwind_timers["ord_go_1"] = mock_timer
        bot.pending_rescues["ord_go_1"] = {
            "order_no": "ord_go_1",
            "asset": "USDT",
            "amount_crypto": 50.0,
            "fiwind_bid": 1612.0,
            "is_opportunity": True,
        }

        update = MagicMock()
        update.effective_user.id = 999
        update.effective_chat.id = 999
        update.callback_query.data = "fw_opt_go_ord_go_1"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.message.text = "Oportunidad Fiwind"

        await bot._handle_callback(update, MagicMock())

        mock_timer.cancel.assert_called_once()
        self.assertTrue(self.mock_engine.is_fiwind_arbitrage_hold)
        self.mock_engine.ads_manager.pause_all_sell_ads.assert_called_once()

        # Verificar que se ofreció el botón fw_cancel_ord_go_1 y fw_yes_ord_go_1
        call_kwargs = update.callback_query.edit_message_text.call_args[1]
        reply_markup = call_kwargs["reply_markup"]
        buttons_data = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
        self.assertIn("fw_yes_ord_go_1", buttons_data)
        self.assertIn("fw_cancel_ord_go_1", buttons_data)

    async def test_callback_cancel_returns_to_binance(self):
        """Verifica que fw_cancel_ cancele Fiwind y reactive ventas en Binance."""
        bot = TelegramBot(db=self.mock_db, bot_engine=self.mock_engine)
        bot._admin_ids = {999}
        self.mock_engine.is_fiwind_arbitrage_hold = True

        bot.pending_rescues["ord_c_1"] = {
            "order_no": "ord_c_1",
            "is_opportunity": True,
        }

        update = MagicMock()
        update.effective_user.id = 999
        update.effective_chat.id = 999
        update.callback_query.data = "fw_cancel_ord_c_1"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        await bot._handle_callback(update, MagicMock())

        self.assertNotIn("ord_c_1", bot.pending_rescues)
        self.assertFalse(self.mock_engine.is_fiwind_arbitrage_hold)
        self.mock_engine.ads_manager.resume_all_sell_ads.assert_called_once()

    async def test_fiwind_timeout_worker_auto_resumes_sales(self):
        """Verifica que el timeout worker de 5 min reactive Binance si el usuario no respondió."""
        bot = TelegramBot(db=self.mock_db, bot_engine=self.mock_engine)
        bot._app = MagicMock()
        bot._app.bot.edit_message_text = AsyncMock()
        bot._chat_id = 999
        self.mock_engine.is_fiwind_arbitrage_hold = True

        bot.pending_rescues["ord_to_1"] = {
            "order_no": "ord_to_1",
            "is_opportunity": True,
        }
        bot._fiwind_messages["ord_to_1"] = 9988

        # Ejecutamos el worker con timeout_seconds=0 para que despierte inmediatamente
        await bot._fiwind_timeout_worker("ord_to_1", timeout_seconds=0)

        self.assertNotIn("ord_to_1", bot.pending_rescues)
        self.assertFalse(self.mock_engine.is_fiwind_arbitrage_hold)
        self.mock_engine.ads_manager.resume_all_sell_ads.assert_called_once()
        bot._app.bot.edit_message_text.assert_called_once()
        args, kwargs = bot._app.bot.edit_message_text.call_args
        self.assertIn("TIEMPO DE ESPERA AGOTADO", kwargs["text"])

    async def test_fiwind_continuous_quotes_and_spread_median(self):
        """Verifica que Database guarde cotizaciones continuas y calcule la mediana de brecha acumulada."""
        import tempfile
        import os
        from data.database import Database
        from data.models import DetectedOrder

        with tempfile.TemporaryDirectory() as tmpdir:
            test_db_path = os.path.join(tmpdir, "test.db")
            db = Database(test_db_path)
            db.init_schema()

            # 1. Guardar cotizaciones continuas de Fiwind
            db.save_fiwind_quote(bid=1610.0, ask=1625.0)
            db.save_fiwind_quote(bid=1612.0, ask=1626.0)

            # 2. Guardar compras con diferentes precios
            # Compra 1: TC=1600.0, Fiwind=1610.0 -> Brecha = 10.0
            o1 = DetectedOrder(
                order_no="ord_1", adv_no="adv_1", asset="USDT", trade_type="BUY",
                amount_crypto=100.0, amount_ars=160000.0, price=1600.0, tc_implicito=1600.0,
                payment_method="MercadoPagoNew", counterparty="user1", status="COMPLETED",
                fiwind_bid=1610.0,
            )
            db.save_detected_order(o1)

            # Compra 2: TC=1602.0, Fiwind=1614.0 -> Brecha = 12.0
            o2 = DetectedOrder(
                order_no="ord_2", adv_no="adv_1", asset="USDT", trade_type="BUY",
                amount_crypto=100.0, amount_ars=160200.0, price=1602.0, tc_implicito=1602.0,
                payment_method="MercadoPagoNew", counterparty="user2", status="COMPLETED",
                fiwind_bid=1614.0,
            )
            db.save_detected_order(o2)

            # Compra 3: TC=1605.0, luego actualizado fiwind_bid=1613.0 -> Brecha = 8.0
            o3 = DetectedOrder(
                order_no="ord_3", adv_no="adv_1", asset="USDT", trade_type="BUY",
                amount_crypto=50.0, amount_ars=80250.0, price=1605.0, tc_implicito=1605.0,
                payment_method="UalaNew", counterparty="user3", status="COMPLETED",
            )
            db.save_detected_order(o3)
            db.update_order_fiwind_bid("ord_3", 1613.0)

            # Brechas: [10.0, 12.0, 8.0] -> Mediana = 10.0, Media = 10.0
            stats = db.get_fiwind_buy_spread_stats(lookback_days=30)
            self.assertEqual(stats["count"], 3)
            self.assertEqual(stats["median"], 10.0)
            self.assertEqual(stats["mean"], 10.0)
            self.assertEqual(stats["min"], 8.0)
            self.assertEqual(stats["max"], 12.0)
            db.close()

    async def test_cmd_set_rescue_shows_cushion_suggestion_without_modifying_rest(self):
        """Verifica que /set_rescue incluya la línea de sugerencia sin alterar el resto del mensaje."""
        mock_db = MagicMock()
        mock_db.load_bot_config.return_value = MagicMock(rescue_margin=10.0)
        mock_db.get_fiwind_buy_spread_stats.return_value = {
            "median": 11.50,
            "mean": 11.30,
            "count": 15,
            "min": 8.0,
            "max": 15.0,
        }

        bot = TelegramBot(db=mock_db, bot_engine=self.mock_engine)
        bot._admin_ids = {999}

        update = MagicMock()
        update.effective_chat.id = 999
        update.effective_user.id = 999
        update.message.reply_text = AsyncMock()
        ctx = MagicMock()
        ctx.args = []

        await bot._cmd_set_rescue(update, ctx)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]

        # Verificar que el mensaje contiene la línea de sugerencia
        self.assertIn("💡 Sugerencia de colchón: *$11.50 ARS* _(mediana acumulada en 15 compras)_", text)
        # Verificar que las líneas originales siguen intactas
        self.assertIn("🛟 *Margen de Rescate Fiwind*", text)
        self.assertIn("Margen de rescate actual: *$10.00 ARS*", text)
        self.assertIn("👉 *¿Cuánto margen de rescate en Fiwind querés?*", text)
        self.assertIn("_(Ingresá el valor en ARS por debajo del bid, ej: `10` u `8.5`, o escribí `cancelar`)_", text)


if __name__ == "__main__":
    unittest.main()

