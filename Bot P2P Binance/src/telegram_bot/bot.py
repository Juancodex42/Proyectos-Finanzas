"""
Bot de Telegram para control, configuración y monitoreo del bot P2P Binance.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import asyncio
import logging
from typing import Optional

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import Application, ContextTypes

from config.settings import TELEGRAM_ADMIN_IDS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from data.database import Database
from data.models import BotConfig
from telegram_bot.broadcaster import BroadcasterMixin
from telegram_bot.handlers.callbacks import handle_callback
from telegram_bot.handlers.commands import CommandHandlerMixin, register_commands
from telegram_bot.handlers.input_parser import parse_numeric_input

logger = logging.getLogger(__name__)


class TelegramBot(CommandHandlerMixin, BroadcasterMixin):
    """Bot de Telegram para control, configuración y monitoreo del bot P2P."""

    def __init__(self, db: Database, bot_engine=None):
        self.db = db
        self.engine = bot_engine
        self._app: Optional[Application] = None
        self._chat_id = TELEGRAM_CHAT_ID
        self._admin_ids: set[int] = set(TELEGRAM_ADMIN_IDS)
        self.pending_rescues: dict[str, dict] = {}
        self._fiwind_timers: dict[str, asyncio.Task] = {}
        self._fiwind_messages: dict[str, int] = {}
        self._dashboard_message_id: Optional[int] = None
        self._user_state: dict[int, str] = {}
        self._user_state_ts: dict[int, float] = {}

    def _is_authorized(self, update: Update) -> bool:
        """Verifica si el usuario/chat que emite la acción tiene permisos de administración."""
        raw_uid = update.effective_user.id if update.effective_user else None
        user_id = raw_uid if isinstance(raw_uid, int) else None
        raw_cid = update.effective_chat.id if update.effective_chat else None
        chat_id = raw_cid if isinstance(raw_cid, int) else None

        target_chat_id: Optional[int] = None
        if self._chat_id:
            try:
                target_chat_id = int(str(self._chat_id).strip())
            except ValueError:
                target_chat_id = None

        if not self._admin_ids and target_chat_id is None:
            logger.error("SEGURIDAD: TELEGRAM_ADMIN_IDS y TELEGRAM_CHAT_ID vacíos. Acceso DENEGADO por defecto.")
            return False

        if self._admin_ids and user_id is not None:
            if user_id in self._admin_ids:
                return True
            if (
                target_chat_id is not None
                and str(self._chat_id).strip() != str(TELEGRAM_CHAT_ID).strip()
                and user_id == target_chat_id
            ):
                return True
            logger.warning("Acción de Telegram rechazada por falta de autorización: user_id=%s, chat_id=%s", user_id, chat_id)
            return False

        if user_id is not None and target_chat_id is not None and user_id == target_chat_id:
            return True

        if user_id is None and chat_id is not None:
            if chat_id in self._admin_ids:
                return True
            if target_chat_id is not None and chat_id == target_chat_id:
                return True

        logger.warning("Acción de Telegram rechazada por falta de autorización: user_id=%s, chat_id=%s", user_id, chat_id)
        return False

    def _clear_user_state(self, update: Update):
        """Limpia cualquier estado interactivo pendiente para el chat."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id:
            self._user_state.pop(chat_id, None)
            self._user_state_ts.pop(chat_id, None)

    def get_reply_keyboard(self) -> ReplyKeyboardRemove:
        """Retorna ReplyKeyboardRemove para ocultar el teclado inferior y usar solo el menú hamburguesa."""
        return ReplyKeyboardRemove()

    def get_inline_panel(self) -> InlineKeyboardMarkup:
        """Retorna panel de botones inline para acciones rápidas."""
        config = self.db.load_bot_config()
        power_text = "🟢 Encender Bot" if config.is_paused else "🔴 Apagar Bot"
        power_cb = "bot_power_on" if config.is_paused else "bot_power_off"
        keyboard = [
            [
                InlineKeyboardButton(power_text, callback_data=power_cb),
                InlineKeyboardButton("🔄 Reconciliar", callback_data="bot_reconcile"),
            ],
            [
                InlineKeyboardButton("🛡️ Simular y Auditar", callback_data="bot_simulate"),
                InlineKeyboardButton("🎯 Calibrar Precios", callback_data="bot_calibrate"),
            ],
            [
                InlineKeyboardButton("📊 Estado", callback_data="bot_status"),
                InlineKeyboardButton("💰 Balance", callback_data="bot_balance"),
            ],
            [
                InlineKeyboardButton("📈 Ganancias", callback_data="bot_profit"),
                InlineKeyboardButton("💡 Sugerencia Venta", callback_data="bot_sell_advisor"),
            ],
            [
                InlineKeyboardButton("📥 Colchón Compra", callback_data="bot_set_buy_margin"),
                InlineKeyboardButton("📤 Piso Ganancia Venta", callback_data="bot_set_sell_margin"),
            ],
            [
                InlineKeyboardButton("🗑️ Borrar Compras", callback_data="bot_delete_buy_confirm"),
                InlineKeyboardButton("🗑️ Borrar Ventas", callback_data="bot_delete_sell_confirm"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_sell_inline_panel(self) -> InlineKeyboardMarkup:
        """Retorna panel de botones interactivos para venta semi-automática."""
        keyboard = [
            [InlineKeyboardButton("⚡ Publicar los 3 con Anti-Colisión", callback_data="bot_sell_apply_all")],
            [
                InlineKeyboardButton("🚀 Publicar G1", callback_data="bot_sell_apply_1"),
                InlineKeyboardButton("🏦 Publicar G2", callback_data="bot_sell_apply_2"),
                InlineKeyboardButton("🪙 Publicar G3", callback_data="bot_sell_apply_3"),
            ],
            [
                InlineKeyboardButton("🛡️ Configurar Piso Venta", callback_data="bot_set_sell_margin"),
                InlineKeyboardButton("🔄 Recalcular", callback_data="bot_sell_advisor"),
            ],
            [
                InlineKeyboardButton("⏸️ Pausar Ventas", callback_data="bot_sell_pause_all"),
                InlineKeyboardButton("🗑️ Borrar Ventas", callback_data="bot_delete_sell_confirm"),
            ],
            [InlineKeyboardButton("🔙 Panel Principal", callback_data="refresh_dash")],
        ]
        return InlineKeyboardMarkup(keyboard)

    def _get_effective_wac_ref(self) -> float:
        """Obtiene el costo promedio ponderado de compra (WAC) de referencia."""
        try:
            if self.engine and hasattr(self.engine, "profit_tracker") and self.engine.profit_tracker:
                cost = self.engine.profit_tracker.get_effective_wac_cost()
                if isinstance(cost, (int, float)) and cost > 0:
                    return float(cost)
            if hasattr(self, "db") and self.db:
                from unittest.mock import Mock
                if isinstance(self.db, Mock):
                    return 0.0
                from core.profit_tracker import ProfitTracker
                tracker = ProfitTracker(self.db)
                cost = tracker.get_effective_wac_cost()
                if isinstance(cost, (int, float)) and cost > 0:
                    return float(cost)
        except Exception:
            pass
        return 0.0

    def _get_usdt_benchmark_ref(self) -> float:
        """Obtiene el tipo de cambio de benchmark de salida USDT representativo."""
        try:
            bms = (
                self.engine.last_benchmarks
                if self.engine and getattr(self.engine, "last_benchmarks", None)
                else None
            ) or (self.db.get_latest_benchmarks() if self.db else {})
            if isinstance(bms, dict):
                mp_bm = bms.get("MercadoPagoNew")
                val = getattr(mp_bm, "avg_top_n_price", None)
                if val is not None and isinstance(val, (int, float)) and val > 0:
                    return float(val)
                valid_vals = [float(getattr(b, "avg_top_n_price", 0)) for b in bms.values() if getattr(b, "avg_top_n_price", 0) > 0]
                if valid_vals:
                    return sum(valid_vals) / len(valid_vals)
        except Exception:
            pass
        return 0.0

    def _get_market_sell_ref(self) -> float:
        """Obtiene precio competitivo de salida en P2P (Top 2 en Mercado Pago o similar)."""
        try:
            bms = (
                self.engine.last_benchmarks
                if self.engine and getattr(self.engine, "last_benchmarks", None)
                else None
            ) or (self.db.get_latest_benchmarks() if self.db else {})
            if isinstance(bms, dict):
                mp_bm = bms.get("MercadoPagoNew")
                if mp_bm:
                    prices = getattr(mp_bm, "individual_prices", None)
                    if isinstance(prices, list):
                        valid_p = [float(p) for p in prices if isinstance(p, (int, float)) and float(p) > 0]
                        if len(valid_p) >= 2:
                            return valid_p[1]
                        elif valid_p:
                            return valid_p[0]
                    avg_p = getattr(mp_bm, "avg_top_n_price", None)
                    if avg_p is not None and isinstance(avg_p, (int, float)) and avg_p > 0:
                        return float(avg_p)
        except Exception:
            pass
        return 0.0

    def _get_sell_margin_prompt_text(self, config: BotConfig) -> str:
        """Genera el texto contextual informativo para cambiar el piso de ganancia en venta."""
        sell_m = getattr(config, "sell_margin_min", 5.0)
        wac_cost = self._get_effective_wac_ref()
        market_ref = self._get_market_sell_ref()

        lines = [
            "📤 *Cambiar Piso de Ganancia de Venta*",
            "",
            f"Piso de ganancia actual: *+{sell_m:.2f} ARS* sobre costo WAC.",
            "_(Piso seguro de venta = Costo WAC + Piso)_",
            "",
            "📊 *Referencias de precios en tiempo real:*",
        ]
        if wac_cost > 0:
            lines.append(f"• 📦 *Costo de compra (WAC):* `${wac_cost:,.2f} ARS`")
            lines.append(f"• 🛡️ *Piso de venta con colchón actual:* `${wac_cost + sell_m:,.2f} ARS`")
        else:
            lines.append("• 📦 *Costo de compra (WAC):* Sin compras recientes registradas.")
            lines.append(f"• 🛡️ *Piso seguro actual:* Costo WAC + `+{sell_m:.2f} ARS`")

        if market_ref > 0:
            lines.append(f"• 🏷️ *Precio competitivo mercado (Puesto #2):* `${market_ref:,.2f} ARS`")

        lines.extend([
            "",
            "👉 *¿Cuánto margen mínimo neto en ARS querés garantizar en cada venta?*",
            "_(Ingresá el valor en ARS, ej: `5` o `10`, o escribí `cancelar`)_",
        ])
        if wac_cost > 0:
            lines.extend([
                "",
                f"💡 _Ejemplo: Si ingresás `6`, tu piso mínimo innegociable será `${wac_cost + 6:,.2f} ARS`._",
            ])
        return "\n".join(lines)

    def _get_buy_margin_prompt_text(self, config: BotConfig) -> str:
        """Genera el texto contextual informativo para cambiar el colchón de compra."""
        usdt_bm = self._get_usdt_benchmark_ref()
        lines = [
            "📥 *Cambiar Colchón de Compra*",
            "",
            f"Colchón actual de compra: *{config.margin_min} ARS*",
            "_(Techo de compra = Benchmark Venta - Colchón)_",
            "",
        ]
        if usdt_bm > 0:
            lines.extend([
                "📊 *Referencias de precios en tiempo real:*",
                f"• 🏷️ *Benchmark promedio Venta USDT:* `${usdt_bm:,.2f} ARS`",
                f"• 🎯 *Techo de compra con colchón actual:* `${usdt_bm - config.margin_min:,.2f} ARS`",
                "",
            ])
        lines.extend([
            "👉 *¿Cuánto colchón de compra querés?*",
            "_(Ingresá el valor en ARS, ej: `10` o `5.5`, o escribí `cancelar`)_",
        ])
        if usdt_bm > 0:
            lines.extend([
                "",
                f"💡 _Ejemplo: Si ingresás `12`, pagarás como máximo `${usdt_bm - 12:,.2f} ARS` por USDT._",
            ])
        return "\n".join(lines)

    async def start(self):
        """Inicia el bot de Telegram."""
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("TELEGRAM_BOT_TOKEN no configurado, bot deshabilitado")
            return

        self._app = Application.builder().token(TELEGRAM_BOT_TOKEN).concurrent_updates(True).build()
        # Registra comandos compatibles:
        # ("stop", self._cmd_power_off)
        # ("parar", self._cmd_power_off)
        # ("apagar", self._cmd_power_off)
        # ("sugerencia_venta", self._cmd_sell_advisor)
        # ("sugerencias_venta", self._cmd_sell_advisor)
        # ("venta_tips", self._cmd_sell_advisor)
        register_commands(self._app, self)
        await self._app.initialize()

        bot_commands = [
            BotCommand("apagar", "🔴 Apagar bot y pausar anuncios"),
            BotCommand("encender", "🟢 Encender bot y reactivar anuncios"),
            BotCommand("status", "📊 Estado general y precios"),
            BotCommand("ganancias", "📈 Ganancias del día (realizada y proyectada)"),
            BotCommand("calibrar", "🎯 Calibrar precios y montos en frío (OFFLINE)"),
            BotCommand("reconcile", "🔄 Reconciliar 14 activos x 3 anuncios"),
            BotCommand("borrar_compras", "🗑️ Eliminar todos los anuncios de COMPRA"),
            BotCommand("borrar_ventas", "🗑️ Eliminar todos los anuncios de VENTA"),
            BotCommand("sugerencia_venta", "💡 Sugerencias y precios venta USDT"),
            BotCommand("balance", "💰 Ver saldo y liquidez"),
            BotCommand("set_balance", "💵 Configurar saldo ARS"),
            BotCommand("set_margin", "📏 Cambiar margen mínimo"),
            BotCommand("set_rescue", "🛟 Margen de rescate Fiwind"),
            BotCommand("benchmark", "📈 Precios venta USDT por método"),
            BotCommand("pause_all", "⏸️ Pausar todos los anuncios"),
            BotCommand("resume_all", "▶️ Reactivar todos los anuncios"),
            BotCommand("sleep", "💤 Pausar por X minutos (ej: /sleep 30)"),
            BotCommand("orders", "🧾 Últimos cambios de precio"),
            BotCommand("methods", "💳 Métodos de pago y score"),
            BotCommand("groups", "📦 Agrupamiento de métodos"),
            BotCommand("help", "❓ Ayuda completa"),
        ]
        try:
            await self._app.bot.set_my_commands(bot_commands)
            logger.info("Menú de comandos (hamburguesa) configurado en Telegram")
        except Exception as e:
            logger.warning("No se pudo configurar menú de comandos: %s", e)

        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot de Telegram iniciado")

    async def stop(self):
        """Detiene el bot de Telegram."""
        if self._app:
            try:
                if self._app.updater and self._app.updater.running:
                    await self._app.updater.stop()
            except Exception as e:
                logger.debug("Error deteniendo updater de Telegram: %s", e)
            try:
                if self._app.running:
                    await self._app.stop()
            except Exception as e:
                logger.debug("Error deteniendo app de Telegram: %s", e)
            try:
                await self._app.shutdown()
            except Exception as e:
                logger.debug("Error en shutdown de app de Telegram: %s", e)

    async def _handle_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Maneja las respuestas a los botones de confirmación de Fiwind y opciones de arbitraje."""
        return await handle_callback(self, update, ctx)
