"""
Módulo de difusión, notificaciones de eventos y alertas automáticas para TelegramBot.
"""
import asyncio
import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from data.models import DetectedOrder
from telegram_bot.formatters.alert_view import (
    format_altcoin_buy_swap_alert,
    format_opportunity_notification,
    format_rescue_notification,
)

logger = logging.getLogger(__name__)


class BroadcasterMixin:
    """Mixin que contiene la lógica de transmisión de mensajes, alertas y reportes para TelegramBot."""

    def _prune_expired_rescues(self, max_age_seconds: int = 7200):
        """Limpia operaciones pendientes de rescate que hayan superado el tiempo máximo de vida."""
        now_ts = time.time()
        to_del = [k for k, v in self.pending_rescues.items() if now_ts - v.get("created_at", now_ts) > max_age_seconds]
        for k in to_del:
            self.pending_rescues.pop(k, None)

    async def send_message(self, text: str, parse_mode: str = "Markdown", reply_markup=None):
        """Envía un mensaje al chat configurado con tolerancia a fallas de parse_mode."""
        if not self._app or not self._chat_id:
            return None
        if text and len(text) > 4000:
            cut = text.rfind("\n", 0, 4000)
            text = (text[:cut] if cut > 0 else text[:4000]) + "\n..."
        if reply_markup is None:
            reply_markup = self.get_reply_keyboard()
        try:
            return await self._app.bot.send_message(
                chat_id=self._chat_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup,
            )
        except Exception as e:
            if parse_mode and ("can't parse entities" in str(e).lower() or "can't parse" in str(e).lower()):
                try:
                    return await self._app.bot.send_message(
                        chat_id=self._chat_id, text=text, parse_mode=None, reply_markup=reply_markup,
                    )
                except Exception as e2:
                    logger.error("Error enviando mensaje Telegram sin parse_mode: %s", e2)
            logger.error("Error enviando mensaje Telegram: %s", e)
            return None

    async def notify(self, text: str):
        """Alias para send_message."""
        await self.send_message(text)

    async def update_live_dashboard(self, text: str):
        """
        Actualiza el mensaje persistente de monitoreo en vivo en Telegram (edit_message_text).
        Si el mensaje aún no existe o fue eliminado por el usuario, envía uno nuevo y guarda su ID en la BD.
        """
        if not self._app or not self._chat_id:
            return

        if self._dashboard_message_id is None:
            saved_id = self.db.get_config("dashboard_message_id", "")
            if saved_id and str(saved_id).isdigit():
                self._dashboard_message_id = int(saved_id)

        if self._dashboard_message_id:
            try:
                await self._app.bot.edit_message_text(
                    chat_id=self._chat_id,
                    message_id=self._dashboard_message_id,
                    text=text,
                    parse_mode="Markdown",
                )
                return
            except Exception as e:
                err_str = str(e).lower()
                if "not modified" in err_str:
                    return
                if "can't parse entities" in err_str or "can't parse" in err_str:
                    try:
                        await self._app.bot.edit_message_text(
                            chat_id=self._chat_id,
                            message_id=self._dashboard_message_id,
                            text=text,
                            parse_mode=None,
                        )
                        return
                    except Exception as e_plain:
                        if "not modified" in str(e_plain).lower():
                            return
                if not any(msg in err_str for msg in ("message to edit not found", "message can't be edited", "chat not found")):
                    logger.debug("Error transitorio editando dashboard (%s), se conserva message_id=%s", e, self._dashboard_message_id)
                    return
                logger.debug("No se pudo editar mensaje de dashboard (%s), enviando nuevo...", e)
                self._dashboard_message_id = None

        try:
            msg = await self._app.bot.send_message(chat_id=self._chat_id, text=text, parse_mode="Markdown")
            self._dashboard_message_id = msg.message_id
            self.db.set_config("dashboard_message_id", str(msg.message_id))
            logger.info("Nuevo mensaje de Dashboard en vivo creado en Telegram: ID %d", msg.message_id)
        except Exception as e:
            if "can't parse entities" in str(e).lower() or "can't parse" in str(e).lower():
                try:
                    msg = await self._app.bot.send_message(chat_id=self._chat_id, text=text, parse_mode=None)
                    self._dashboard_message_id = msg.message_id
                    self.db.set_config("dashboard_message_id", str(msg.message_id))
                    logger.info("Nuevo mensaje de Dashboard (sin parse_mode) creado en Telegram: ID %d", msg.message_id)
                    return
                except Exception as e_plain:
                    logger.error("Error enviando Dashboard en texto plano: %s", e_plain)
            logger.error("Error enviando Dashboard en vivo a Telegram: %s", e)

    async def notify_rescue_order(
        self,
        order,
        fiwind_bid: float,
        spread: float,
        net_profit: float,
        spot_price: float = 1.0,
    ):
        """Envía notificación de compra de rescate con botones interactivos."""
        if not self._app or not self._chat_id:
            return

        text = format_rescue_notification(order, fiwind_bid, spread, net_profit)
        self._prune_expired_rescues(7200)

        spot_factor = spot_price if spot_price > 0 else 1.0
        amount_usdt = order.amount_crypto if order.asset == "USDT" else (order.amount_crypto * spot_factor)

        self.pending_rescues[order.order_no] = {
            "order_no": order.order_no,
            "adv_no": order.adv_no,
            "asset": order.asset,
            "amount_crypto": order.amount_crypto,
            "amount_usdt": amount_usdt,
            "amount_ars": order.amount_ars,
            "fiwind_bid": fiwind_bid,
            "net_profit": net_profit,
            "created_at": time.time(),
        }

        keyboard = [
            [
                InlineKeyboardButton("✅ Sí, enviado y vendido", callback_data=f"fw_yes_{order.order_no}"),
                InlineKeyboardButton("⏳ Todavía no", callback_data=f"fw_no_{order.order_no}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.send_message(text, parse_mode="Markdown", reply_markup=reply_markup)
        logger.info("Alerta de rescate con botones enviada a Telegram para orden %s", order.order_no)

    async def notify_opportunity_order(
        self,
        order,
        fiwind_bid: float,
        binance_sell_tc: float,
        spread: float,
        net_profit: float,
        spot_price: float = 1.0,
    ):
        """Envía notificación de oportunidad de arbitraje opcional con 2 botones de decisión y timeout de 5 min."""
        if not self._app or not self._chat_id:
            return

        text = format_opportunity_notification(
            order=order,
            fiwind_bid=fiwind_bid,
            binance_sell_tc=binance_sell_tc,
            spread_fiwind=spread,
            net_profit_fiwind=net_profit,
        )
        self._prune_expired_rescues(7200)

        spot_factor = spot_price if spot_price > 0 else 1.0
        amount_usdt = order.amount_crypto if order.asset == "USDT" else (order.amount_crypto * spot_factor)

        self.pending_rescues[order.order_no] = {
            "order_no": order.order_no,
            "adv_no": order.adv_no,
            "asset": order.asset,
            "amount_crypto": order.amount_crypto,
            "amount_usdt": amount_usdt,
            "amount_ars": order.amount_ars,
            "payout_ars": amount_usdt * fiwind_bid,
            "fiwind_bid": fiwind_bid,
            "net_profit": net_profit,
            "created_at": time.time(),
            "is_opportunity": True,
        }

        keyboard = [
            [
                InlineKeyboardButton("🚀 Ir a Fiwind (Rápido)", callback_data=f"fw_opt_go_{order.order_no}"),
                InlineKeyboardButton("🏦 Quedarme en Binance", callback_data=f"fw_opt_stay_{order.order_no}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        sent_msg = await self.send_message(text, parse_mode="Markdown", reply_markup=reply_markup)
        if sent_msg and hasattr(sent_msg, "message_id"):
            self._fiwind_messages[order.order_no] = sent_msg.message_id
        logger.info("Oportunidad de arbitraje enviada a Telegram para orden %s", order.order_no)

        prev_timer = self._fiwind_timers.pop(order.order_no, None)
        if prev_timer and not prev_timer.done():
            prev_timer.cancel()

        self._fiwind_timers[order.order_no] = asyncio.create_task(
            self._fiwind_timeout_worker(order.order_no, timeout_seconds=300)
        )

    async def _fiwind_timeout_worker(self, order_no: str, timeout_seconds: int = 300):
        """Maneja el timeout de 5 minutos para oportunidades de Fiwind."""
        try:
            await asyncio.sleep(timeout_seconds)
        except asyncio.CancelledError:
            return

        info = self.pending_rescues.get(order_no)
        if not info or not info.get("is_opportunity"):
            return

        logger.info("⏰ Timeout de %ds alcanzado para oportunidad Fiwind orden %s. Reactivando ventas.", timeout_seconds, order_no)
        self.pending_rescues.pop(order_no, None)
        self._fiwind_timers.pop(order_no, None)

        has_other_opt = any(v.get("is_opportunity") for v in self.pending_rescues.values())
        if not has_other_opt and self.engine:
            self.engine.is_fiwind_arbitrage_hold = False
            if hasattr(self.engine, "ads_manager") and hasattr(self.engine.ads_manager, "resume_all_sell_ads"):
                await self.engine.ads_manager.resume_all_sell_ads()

        msg_id = self._fiwind_messages.pop(order_no, None)
        timeout_txt = (
            f"⏰ *TIEMPO DE ESPERA AGOTADO (5 MIN)*\n\n"
            f"No se recibió respuesta para la oportunidad en orden `#{order_no[-4:]}`.\n"
            f"▶️ *Tus anuncios de venta en Binance (G1, G2, G3) fueron reactivados automáticamente* para continuar vendiendo en P2P."
        )
        if self._app and self._chat_id and msg_id:
            try:
                await self._app.bot.edit_message_text(
                    chat_id=self._chat_id,
                    message_id=msg_id,
                    text=timeout_txt,
                    parse_mode="Markdown",
                    reply_markup=None,
                )
            except Exception as e_edit:
                logger.debug("No se pudo editar mensaje tras timeout de Fiwind: %s", e_edit)

    async def notify_altcoin_buy_order(
        self,
        order: DetectedOrder,
        spot_price: float,
        usdt_sell_tc: float,
    ):
        """Envía alerta automática de compra de Altcoin con enlaces a Binance Convert y control de anuncios."""
        text = format_altcoin_buy_swap_alert(order, spot_price, usdt_sell_tc)
        convert_url = f"https://www.binance.com/es-LA/convert?from={order.asset}&to=USDT"
        keyboard = [
            [InlineKeyboardButton("🔄 Abrir Binance Convert", url=convert_url)],
            [
                InlineKeyboardButton(f"⏸️ Pausar Anuncio {order.asset}", callback_data=f"alt_pause_{order.asset}_{order.adv_no}"),
                InlineKeyboardButton("✖️ Cerrar Alerta", callback_data=f"alt_close_{order.order_no}_{order.asset}"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.send_message(text, parse_mode="Markdown", reply_markup=reply_markup)
        logger.info("Alerta de compra Altcoin (%s) enviada a Telegram (orden %s)", order.asset, order.order_no)
