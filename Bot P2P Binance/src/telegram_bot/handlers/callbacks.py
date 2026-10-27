"""
Despachador central de callback queries para TelegramBot.
"""
import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.handlers.cb_ads import handle_ad_callback
from telegram_bot.handlers.cb_margins import handle_margin_callback

logger = logging.getLogger(__name__)


async def handle_callback(bot: Any, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Despacha las respuestas a los botones inline al manejador correspondiente."""
    query = update.callback_query
    if not query or not query.data:
        return

    if not bot._is_authorized(update):
        await query.answer("⛔ No estás autorizado.", show_alert=True)
        return

    try:
        data = query.data

        # 1. Intentar delegar a callbacks de anuncios (pausa, reanudación, borrado, aplicación venta)
        if await handle_ad_callback(bot, update, query, data):
            return

        # 2. Intentar delegar a callbacks de márgenes, calibración y rescate Fiwind
        if await handle_margin_callback(bot, update, query, data):
            return

        logger.warning("Callback no manejado recibido: %s", data)
    except Exception as e:
        logger.error("Error manejando callback query '%s': %s", getattr(query, "data", ""), e, exc_info=True)
        try:
            await query.answer("⚠️ Error procesando la acción.", show_alert=True)
        except Exception:
            pass
