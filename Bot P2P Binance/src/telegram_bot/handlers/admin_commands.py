"""
Manejadores de comandos administrativos y de control de ciclo para TelegramBot.
"""
import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from telegram_bot.formatters.dashboard_view import format_reconciliation_report

logger = logging.getLogger(__name__)


class AdminCommandsMixin:
    """Mixin que contiene comandos administrativos: encendido, apagado, pausa y reconciliación."""

    async def _cmd_cancel(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Cancela cualquier operación interactiva en curso."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id and self._user_state.pop(chat_id, None):
            self._user_state_ts.pop(chat_id, None)
            await update.message.reply_text("❌ *Operación cancelada.*", parse_mode="Markdown")
        else:
            await update.message.reply_text("No hay ninguna operación pendiente para cancelar.")

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra bienvenida y orientación de comandos."""
        await update.message.reply_text(
            "🤖 *Bot P2P Binance ARS*\n\n"
            "Bot de reposicionamiento de precios de compra multiactivo (14 criptos x 3 anuncios con 5 métodos c/u).\n\n"
            "Usá el menú de comandos (hamburguesa) para controlar el bot o ver su estado.",
            parse_mode="Markdown",
            reply_markup=self.get_reply_keyboard(),
        )

    async def _cmd_power_off(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Apaga el bot pausando todos los anuncios de compra en Binance."""
        await update.message.reply_text("⏳ *Apagando bot...*\nPausando todos los anuncios en Binance y frenando ciclo.", parse_mode="Markdown")
        if self.engine:
            await self.engine.turn_off()
        else:
            config = self.db.load_bot_config()
            config.is_paused = True
            self.db.save_bot_config(config)

        await update.message.reply_text(
            "🔴 *BOT APAGADO*\n\n"
            "• Todos los anuncios BUY en Binance han sido pausados.\n"
            "• El ciclo de reposicionamiento está detenido.\n\n"
            "Podés volver a encenderlo en cualquier momento desde el menú de comandos o con /encender.",
            parse_mode="Markdown",
            reply_markup=self.get_reply_keyboard(),
        )

    async def _cmd_power_on(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Enciende el bot verificando estructura y reactivando anuncios."""
        await update.message.reply_text("⏳ *Encendiendo bot...*\nVerificando y reconciliando anuncios para los 14 activos (42 anuncios, 5 métodos c/u)...", parse_mode="Markdown")
        stats = {}
        if self.engine:
            stats = await self.engine.turn_on()
        else:
            config = self.db.load_bot_config()
            config.is_paused = False
            config.sleep_until = None
            self.db.save_bot_config(config)

        report = format_reconciliation_report(stats) if stats else ""
        msg = (
            "🟢 *BOT ENCENDIDO Y OPERANDO*\n\n"
            "• Todos los anuncios fueron verificados y puestos online en Binance.\n"
            "• El ciclo de reposicionamiento está activo.\n\n"
        )
        if report:
            msg += f"{report}\n\n"
        msg += "Podés apagarlo cuando quieras desde el menú de comandos o con /apagar."

        await update.message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=self.get_reply_keyboard(),
        )

    async def _cmd_reconcile(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Reconcilia anuncios de compra y venta en Binance."""
        status_msg = await update.message.reply_text(
            "🔄 *Reconciliando estructura con Binance...*\n\n"
            "• Verificando 42 anuncios de compra (14 criptos x 3 grupos)...\n"
            "• Verificando 3 anuncios de venta USDT (G1, G2, G3)...\n"
            "• Escaneando mercado y calibrando precios en frío...\n\n"
            "⏳ _Esto puede demorar unos 30-45 segundos. Por favor espera..._",
            parse_mode="Markdown",
        )
        stats = {}
        if self.engine:
            stats = await self.engine.reconcile_ads(set_online=False)
        report = format_reconciliation_report(stats) if stats else "Reconciliación completada."
        try:
            await status_msg.edit_text(report, parse_mode="Markdown", reply_markup=self.get_reply_keyboard())
        except Exception:
            await update.message.reply_text(report, parse_mode="Markdown", reply_markup=self.get_reply_keyboard())

    async def _cmd_pause_all(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Pausa todos los anuncios de Binance."""
        if self.engine:
            count = await self.engine.ads_manager.pause_all()
            config = self.db.load_bot_config()
            config.is_paused = True
            self.db.save_bot_config(config)
            self.engine.config = config
            self.engine._notify_state_change()
            await update.message.reply_text(f"⏸️ {count} anuncios pausados")
        else:
            await update.message.reply_text("⚠️ Engine no disponible")

    async def _cmd_resume_all(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Reactiva todos los anuncios tras calibración en frío."""
        await update.message.reply_text("⏳ *Reactivando todos los anuncios con calibración previa en frío...*", parse_mode="Markdown")
        stats = {}
        if self.engine:
            stats = await self.engine.turn_on()
        else:
            config = self.db.load_bot_config()
            config.is_paused = False
            config.sleep_until = None
            self.db.save_bot_config(config)

        calib = stats.get("calibrated", 0) if stats else 0
        resumed = stats.get("total_active", stats.get("resumed", 0)) if stats else 0
        await update.message.reply_text(
            f"▶️ *Todos los anuncios reactivados*\n\n"
            f"• Anuncios calibrados en frío: *{calib}*\n"
            f"• Anuncios online: *{resumed}*",
            parse_mode="Markdown",
            reply_markup=self.get_reply_keyboard(),
        )

    async def _cmd_pause(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Pausa un activo específico o un anuncio individual."""
        if not ctx.args:
            await update.message.reply_text("Uso: /pause BTC [grupo]")
            return
        asset = ctx.args[0].upper()
        if not self.engine:
            await update.message.reply_text("⚠️ Engine no disponible")
            return

        if len(ctx.args) >= 2:
            raw_g = ctx.args[1].upper().replace("G", "").strip()
            try:
                group = int(raw_g)
            except ValueError:
                await update.message.reply_text("❌ Grupo inválido. Usa 1, 2 o 3 (o G1, G2, G3)")
                return
            ads = self.db.get_my_ads(asset=asset)
            config = self.db.load_bot_config()
            paused_count = 0
            for ad in ads:
                if ad.ad_group == group:
                    await self.engine.ads_manager.pause_ad(ad.adv_no)
                    config.paused_ads.add(ad.adv_no)
                    paused_count += 1
            self.db.save_bot_config(config)
            self.engine.config = config
            self.engine._notify_state_change()
            await update.message.reply_text(f"⏸️ {asset} grupo {group} pausado ({paused_count} anuncios)")
        else:
            count = await self.engine.ads_manager.pause_by_asset(asset)
            config = self.db.load_bot_config()
            config.paused_assets.add(asset)
            self.db.save_bot_config(config)
            self.engine.config = config
            self.engine._notify_state_change()
            await update.message.reply_text(f"⏸️ {asset}: {count} anuncios pausados")

    async def _cmd_resume(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Reactiva un activo específico o un anuncio individual."""
        if not ctx.args:
            await update.message.reply_text("Uso: /resume BTC [grupo]")
            return
        asset = ctx.args[0].upper()
        if not self.engine:
            await update.message.reply_text("⚠️ Engine no disponible")
            return

        if len(ctx.args) >= 2:
            raw_g = ctx.args[1].upper().replace("G", "").strip()
            try:
                group = int(raw_g)
            except ValueError:
                await update.message.reply_text("❌ Grupo inválido. Usa 1, 2 o 3 (o G1, G2, G3)")
                return
            ads = self.db.get_my_ads(asset=asset)
            config = self.db.load_bot_config()
            resumed_count = 0
            can_go_online = not config.is_paused and not config.sleep_until
            for ad in ads:
                if ad.ad_group == group:
                    config.paused_ads.discard(ad.adv_no)
                    if can_go_online:
                        await self.engine.ads_manager.resume_ad(ad.adv_no)
                        resumed_count += 1
            self.db.save_bot_config(config)
            self.engine.config = config
            self.engine._notify_state_change()
            if can_go_online:
                await update.message.reply_text(f"▶️ {asset} grupo {group} reactivado ({resumed_count} anuncios)")
            else:
                await update.message.reply_text(f"✅ {asset} grupo {group} quitado de pausa manual (se pondrá online al encender el bot)")
        else:
            config = self.db.load_bot_config()
            config.paused_assets.discard(asset)
            self.db.save_bot_config(config)
            self.engine.config = config
            self.engine._notify_state_change()
            if not config.is_paused and not config.sleep_until:
                count = await self.engine.ads_manager.resume_by_asset(asset)
                await update.message.reply_text(f"▶️ {asset}: {count} anuncios reactivados")
            else:
                await update.message.reply_text(f"✅ {asset} habilitado en configuración (se pondrá online al encender el bot)")

    async def _cmd_sleep(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Pone en pausa temporal el bot durante N minutos."""
        if not ctx.args:
            await update.message.reply_text("Uso: /sleep 30 (minutos)")
            return
        try:
            minutes = int(ctx.args[0])
            if minutes <= 0 or minutes > 1440:
                await update.message.reply_text("❌ *Minutos inválidos.* Debe ser entre 1 y 1440 min (máx 24h).", parse_mode="Markdown")
                return
            config = self.db.load_bot_config()
            config.sleep_until = datetime.now() + timedelta(minutes=minutes)
            config.is_paused = True
            self.db.save_bot_config(config)
            if self.engine:
                self.engine.config = config
                await self.engine.ads_manager.pause_all()
                self.engine._notify_state_change()
            await update.message.reply_text(f"💤 Bot en sleep por {minutes} minutos (hasta {config.sleep_until.strftime('%H:%M')})")
        except ValueError:
            await update.message.reply_text("❌ Valor inválido. Debe ser un número entero. Ejemplo: `/sleep 30`", parse_mode="Markdown")

    async def _cmd_delete_buy_ads(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Pide confirmación antes de eliminar permanentemente todos los anuncios de COMPRA."""
        keyboard = [[
            InlineKeyboardButton("⚠️ Sí, eliminar COMPRAS", callback_data="confirm_delete_buy_ads"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_delete_buy_ads"),
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = (
            "⚠️ *CONFIRMACIÓN DE SEGURIDAD*\n\n"
            "¿Estás seguro de que deseas *ELIMINAR DEFINITIVAMENTE* todos tus anuncios de *COMPRA* en Binance?\n\n"
            "🛡️ *Tus anuncios de VENTA no serán tocados ni modificados.*\n"
            "⏸️ El bot se pondrá en pausa preventiva tras eliminarlos."
        )
        msg_target = update.message or (update.callback_query.message if update.callback_query else None)
        if msg_target:
            await msg_target.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

    async def _cmd_delete_sell_ads(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Pide confirmación antes de eliminar permanentemente todos los anuncios de VENTA."""
        keyboard = [[
            InlineKeyboardButton("⚠️ Sí, eliminar VENTAS", callback_data="confirm_delete_sell_ads"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_delete_sell_ads"),
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = (
            "⚠️ *CONFIRMACIÓN DE SEGURIDAD*\n\n"
            "¿Estás seguro de que deseas *ELIMINAR DEFINITIVAMENTE* todos tus anuncios de *VENTA* en Binance?\n\n"
            "🛡️ *Tus anuncios de COMPRA no serán tocados ni modificados.*\n"
            "⏸️ El bot se pondrá en pausa preventiva tras eliminarlos."
        )
        msg_target = update.message or (update.callback_query.message if update.callback_query else None)
        if msg_target:
            await msg_target.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

    async def _cmd_set_interval(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Configura el intervalo de polling del ciclo de reposicionamiento."""
        if not ctx.args:
            await update.message.reply_text("Uso: /set_interval 30")
            return
        try:
            interval = int(ctx.args[0])
            if not (15 <= interval <= 300):
                await update.message.reply_text("❌ Intervalo inválido. Debe estar entre 15 y 300 segundos por seguridad de Binance.")
                return
            config = self.db.load_bot_config()
            config.poll_interval = interval
            self.db.save_bot_config(config)
            if self.engine:
                self.engine.config.poll_interval = interval
            await update.message.reply_text(f"✅ Intervalo de polling: {interval}s")
        except ValueError:
            await update.message.reply_text("❌ Valor inválido")

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra lista detallada de comandos de control, configuración e información."""
        await update.message.reply_text(
            "📋 *Comandos disponibles*\n\n"
            "*Control General:*\n"
            "/apagar — 🔴 Apagar bot y pausar anuncios en Binance\n"
            "/encender — 🟢 Encender bot y reactivar anuncios\n"
            "/reconcile — 🔄 Reconciliar los 42 anuncios con Binance\n"
            "/calibrar — 🎯 Calibrar precios/cantidades en Binance (anuncios OFFLINE)\n"
            "/simular — 🛡️ Simular precios en vivo y auditar reglas anti-baneo (Dry-Run)\n"
            "/test\\_estres — 🚀 Batería sintética de estrés anti-baneo (6 escenarios hostiles)\n"
            "/borrar\\_compras — 🗑️ Eliminar todos los anuncios de COMPRA\n"
            "/borrar\\_ventas — 🗑️ Eliminar todos los anuncios de VENTA\n"
            "/pause\\_all — Pausar todos los anuncios\n"
            "/resume\\_all — Reactivar todos los anuncios\n"
            "/pause `asset` — Pausar activo\n"
            "/pause `asset` `grupo` — Pausar anuncio\n"
            "/resume `asset` — Reactivar activo\n"
            "/sleep `min` — Pausar X minutos\n\n"
            "*Configuración:*\n"
            "/set\\_balance `ARS` — Saldo actual\n"
            "/set\\_volume `ARS` — Volumen benchmark\n"
            "/set\\_margin `ARS` — Margen mínimo\n"
            "/set\\_rescue `ARS` — Margen rescate Fiwind\n"
            "/set\\_step `val` — Paso de precio\n"
            "/set\\_interval `seg` — Polling\n\n"
            "*Info:*\n"
            "/status — Estado general\n"
            "/balance — Saldo y liquidez\n"
            "/stats — Estadísticas\n"
            "/benchmark — USDT sell avg\n"
            "/sugerencia\\_venta — 💡 Sugerencias y precios venta USDT\n"
            "/margin — Márgenes\n"
            "/orders — Últimas órdenes\n"
            "/methods — Métodos de pago\n"
            "/groups — Agrupamiento\n"
            "/wars — Guerras activas\n"
            "/assets — Activos\n"
            "/daily — Reporte diario",
            parse_mode="Markdown",
            reply_markup=self.get_reply_keyboard(),
        )
