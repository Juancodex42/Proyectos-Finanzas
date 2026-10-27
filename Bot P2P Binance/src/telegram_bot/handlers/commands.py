"""
Manejador principal de comandos y registro de rutas para TelegramBot.
"""
import logging
import time
from typing import Any

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from telegram_bot.handlers.admin_commands import AdminCommandsMixin
from telegram_bot.handlers.diagnostic_commands import DiagnosticCommandsMixin
from telegram_bot.handlers.market_commands import MarketCommandsMixin

logger = logging.getLogger(__name__)


class CommandHandlerMixin(AdminCommandsMixin, MarketCommandsMixin, DiagnosticCommandsMixin):
    """Mixin unificado que combina comandos de administración, mercado y diagnóstico."""

    async def _handle_text_button(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Maneja respuestas interactivas a preguntas del bot y botones de texto."""
        if not update.message or not update.message.text:
            return
        if not self._is_authorized(update):
            return
        text = update.message.text.strip()
        chat_id = update.effective_chat.id if update.effective_chat else None

        # Expiración de sesión interactiva (5 min)
        if chat_id and chat_id in self._user_state:
            if chat_id in self._user_state_ts and (time.time() - self._user_state_ts[chat_id]) > 300.0:
                self._user_state.pop(chat_id, None)
                self._user_state_ts.pop(chat_id, None)
                menu_keywords = ("Apagar", "Encender", "Estado", "Balance", "Reconciliar", "Ayuda")
                if not any(k in text for k in menu_keywords):
                    await update.message.reply_text("⏱️ Sesión de entrada expirada (5 min). Operación cancelada.")
                    return

        if chat_id and chat_id in self._user_state:
            state = self._user_state[chat_id]
            if text.lower() in ("cancelar", "cancel", "salir", "/cancel", "/cancelar"):
                self._user_state.pop(chat_id, None)
                self._user_state_ts.pop(chat_id, None)
                await update.message.reply_text("❌ *Operación cancelada.*", parse_mode="Markdown")
                return

            if await self._handle_market_text_input(update, text, state, chat_id):
                return

        # Botones de texto del menú clásico
        actions = {
            ("🔴 Apagar Bot", "Apagar Bot"): self._cmd_power_off,
            ("🟢 Encender Bot", "Encender Bot"): self._cmd_power_on,
            ("📊 Estado", "Estado"): self._cmd_status,
            ("💰 Balance", "Balance", "💰 Liquidez", "Liquidez", "💵 Cambiar Capital", "Cambiar Capital"): self._cmd_balance,
            ("🔄 Reconciliar", "Reconciliar", "🔄 Reconciliar Anuncios", "Reconciliar Anuncios"): self._cmd_reconcile,
            ("📈 Benchmark", "Benchmark", "🔍 Mercado", "Mercado"): self._cmd_benchmark,
            ("🗑️ Borrar Compras", "Borrar Compras", "🗑️ Borrar Anuncios", "Borrar Anuncios"): self._cmd_delete_buy_ads,
            ("🗑️ Borrar Ventas", "Borrar Ventas"): self._cmd_delete_sell_ads,
            ("💡 Sugerencia Venta", "Sugerencia Venta", "💡 Sugerencias Venta", "Sugerencias Venta", "💡 Consejos Venta", "Consejos Venta"): self._cmd_sell_advisor,
            ("❓ Ayuda", "Ayuda"): self._cmd_help,
        }
        for aliases, fn in actions.items():
            if text in aliases:
                await fn(update, ctx)
                return


def register_commands(app: Application, bot: Any):
    """Registra todos los comandos, callbacks y mensajes en la aplicación de Telegram."""
    handlers = [
        ("start", bot._cmd_start),
        ("cancel", bot._cmd_cancel),
        ("cancelar", bot._cmd_cancel),
        ("apagar", bot._cmd_power_off),
        ("stop", bot._cmd_power_off),
        ("parar", bot._cmd_power_off),
        ("encender", bot._cmd_power_on),
        ("reconcile", bot._cmd_reconcile),
        ("calibrar", bot._cmd_calibrate),
        ("calibrate", bot._cmd_calibrate),
        ("simular", bot._cmd_simulate),
        ("simulate", bot._cmd_simulate),
        ("test_estres", bot._cmd_stress_test),
        ("stress_test", bot._cmd_stress_test),
        ("borrar_compras", bot._cmd_delete_buy_ads),
        ("delete_buy_ads", bot._cmd_delete_buy_ads),
        ("borrar_ventas", bot._cmd_delete_sell_ads),
        ("delete_sell_ads", bot._cmd_delete_sell_ads),
        ("sugerencia_venta", bot._cmd_sell_advisor),
        ("sugerencias_venta", bot._cmd_sell_advisor),
        ("venta_tips", bot._cmd_sell_advisor),
        ("status", bot._cmd_status),
        ("balance", bot._cmd_balance),
        ("set_balance", bot._cmd_set_balance),
        ("stats", bot._cmd_stats),
        ("benchmark", bot._cmd_benchmark),
        ("margin", bot._cmd_margin),
        ("pause_all", bot._cmd_pause_all),
        ("resume_all", bot._cmd_resume_all),
        ("pause", bot._cmd_pause),
        ("resume", bot._cmd_resume),
        ("sleep", bot._cmd_sleep),
        ("set_volume", bot._cmd_set_volume),
        ("set_margin", bot._cmd_set_margin),
        ("set_sell_margin", bot._cmd_set_sell_margin),
        ("piso_venta", bot._cmd_set_sell_margin),
        ("set_piso_venta", bot._cmd_set_sell_margin),
        ("set_rescue", bot._cmd_set_rescue),
        ("set_step", bot._cmd_set_step),
        ("set_interval", bot._cmd_set_interval),
        ("assets", bot._cmd_assets),
        ("orders", bot._cmd_orders),
        ("methods", bot._cmd_methods),
        ("groups", bot._cmd_groups),
        ("wars", bot._cmd_wars),
        ("daily", bot._cmd_daily),
        ("ganancias", bot._cmd_profit),
        ("profit", bot._cmd_profit),
        ("help", bot._cmd_help),
    ]

    def _make_handler(h):
        async def _wrapped(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            if not bot._is_authorized(update):
                if update.effective_message:
                    await update.effective_message.reply_text("⛔ No estás autorizado para controlar este bot.")
                return
            chat_id = update.effective_chat.id if update.effective_chat else None
            interactive_cmds = (bot._cmd_set_balance, bot._cmd_set_margin, bot._cmd_set_sell_margin, bot._cmd_set_rescue, bot._cmd_cancel)
            if chat_id and h not in interactive_cmds:
                bot._user_state.pop(chat_id, None)
                bot._user_state_ts.pop(chat_id, None)
            return await h(update, ctx)
        return _wrapped

    for cmd, handler in handlers:
        app.add_handler(CommandHandler(cmd, _make_handler(handler)))

    app.add_handler(CallbackQueryHandler(bot._handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot._handle_text_button))
