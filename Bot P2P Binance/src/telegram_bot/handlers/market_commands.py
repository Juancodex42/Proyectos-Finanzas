"""
Manejadores de comandos de mercado, balances, márgenes, calibración y fijación de precios.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import logging
import time
from datetime import datetime

from telegram import ForceReply, Update
from telegram.ext import ContextTypes

from telegram_bot.formatters.dashboard_view import (
    format_benchmark,
    format_sell_advice_report,
    format_sell_decisions_dashboard,
)
from telegram_bot.handlers.input_parser import parse_numeric_input

logger = logging.getLogger(__name__)


class MarketCommandsMixin:
    """Mixin que contiene comandos financieros, de mercado, márgenes y fijación de precios."""

    def _apply_balance_update(self, amount: float):
        """Aplica y persiste la actualización de balance ARS."""
        config = self.db.load_bot_config()
        config.balance_ars = amount
        self.db.save_bot_config(config)
        if self.engine:
            self.engine.liquidity.set_balance(amount)
            self.engine.config.balance_ars = amount
        else:
            self.db.save_liquidity_event("manual_adjust", amount, amount, "Ajuste manual Telegram")

    def _apply_margin_update(self, val: float, field: str):
        """Aplica y persiste la actualización de un margen en DB y engine."""
        config = self.db.load_bot_config()
        setattr(config, field, val)
        self.db.save_bot_config(config)
        if self.engine:
            setattr(self.engine.config, field, val)

    async def _cmd_calibrate(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Calibra precios y límites en Binance sin encender los anuncios (modo OFFLINE)."""
        status_msg = await update.message.reply_text(
            "⏳ *Calibrando precios y cantidades en Binance...*\n\n"
            "• Escaneando mercado real en vivo (Spot + USDT Benchmarks)...\n"
            "• Calibrando compras (14 activos x 3 grupos)...\n"
            "• Calibrando ventas USDT (G1, G2, G3)...\n\n"
            "⏳ _Ajustando anuncios sin encenderlos (OFFLINE). Espera un momento..._",
            parse_mode="Markdown",
        )
        count = await self.engine.calibrate_all_ads() if self.engine else 0
        sell_count = getattr(self.engine, "_last_sell_calibrated_count", 0) if self.engine else 0
        sell_decisions = getattr(self.engine, "_last_sell_decisions", []) if self.engine else []
        sell_lines = []
        if sell_decisions:
            sell_lines.append("\n📤 *VENTAS USDT (3 Clusters):*")
            for d in sorted(sell_decisions, key=lambda x: x.cluster_id):
                pos = f" • {d.estimated_position}" if getattr(d, "estimated_position", "") else ""
                short_no = f" `#{d.adv_no[-4:]}`" if getattr(d, "adv_no", None) else ""
                title = d.title.split("(")[0].strip() if getattr(d, "title", None) else f"G{d.cluster_id}"
                sell_lines.append(f"• *G{d.cluster_id}* ({title}): `${d.suggested_price:,.2f} ARS`{pos}{short_no}")
            sell_lines.append(f"• Anuncios de venta actualizados: *{sell_count}*")
        elif sell_count > 0:
            sell_lines.append(f"\n📤 *Ventas actualizadas:* *{sell_count}* anuncios")

        sell_block = "\n".join(sell_lines) if sell_lines else ""
        calib_msg = (
            f"🎯 *CALIBRACIÓN COMPLETADA*\n\n📥 *Compras actualizadas:* *{count}* anuncios\n{sell_block}\n\n"
            "• Precios y cantidades de cripto 100% alineados al balance y al mercado.\n\n"
            "Podés encender el bot cuando quieras con /encender."
        )
        try:
            await status_msg.edit_text(calib_msg, parse_mode="Markdown", reply_markup=self.get_reply_keyboard())
        except Exception:
            await update.message.reply_text(calib_msg, parse_mode="Markdown", reply_markup=self.get_reply_keyboard())

    async def _cmd_balance(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra el saldo y estado de liquidez del bot."""
        text = self.engine.liquidity.get_status_text() if self.engine else "⚠️ Engine no disponible"
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=self.get_reply_keyboard())

    async def _cmd_set_balance(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Configura el saldo de capital ARS disponible."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        if not ctx.args:
            config = self.db.load_bot_config()
            if chat_id:
                self._user_state[chat_id], self._user_state_ts[chat_id] = "set_balance", time.time()
            await update.message.reply_text(
                f"💵 *Configurar Saldo ARS*\n\nSaldo actual registrado: *${config.balance_ars:,.0f} ARS*\n\n"
                f"👉 *¿Qué saldo tenés ahora?*\n_(Ingresá el monto en pesos, ej: `500000` o escribí `cancelar`)_",
                parse_mode="Markdown",
                reply_markup=ForceReply(selective=True),
            )
            return

        if chat_id:
            self._user_state.pop(chat_id, None)
            self._user_state_ts.pop(chat_id, None)
        amount = parse_numeric_input(ctx.args[0])
        if amount is None or amount < 0:
            await update.message.reply_text("❌ Monto inválido. Ejemplo: `/set_balance 500000`", parse_mode="Markdown")
            return

        self._apply_balance_update(amount)
        await update.message.reply_text(f"✅ *Saldo ARS actualizado a:* `${amount:,.0f} ARS`", parse_mode="Markdown")

    async def _cmd_benchmark(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra los precios promedio de venta USDT por método de pago."""
        text = format_benchmark(self.engine.last_benchmarks) if (self.engine and self.engine.last_benchmarks) else "⚠️ Sin datos de benchmark"
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=self.get_reply_keyboard())

    async def _cmd_sell_advisor(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Genera el reporte de asesor de ventas P2P y panel de decisiones."""
        from core.pricing.sell_repositioner import SellRepositioner
        from core.profit_tracker import ProfitTracker
        from core.fiwind_client import FiwindClient
        try:
            bms = self.engine.last_benchmarks if self.engine else None
            fiwind_client = (self.engine.fiwind if self.engine else None) or FiwindClient()
            ads_mgr = self.engine.ads_manager if self.engine else None
            prof_tracker = (self.engine.profit_tracker if self.engine else None) or (ProfitTracker(self.db) if self.db else None)
            bot_cfg = self.engine.config if self.engine else self.db.load_bot_config()
            repositioner = SellRepositioner(self.db, ads_mgr, prof_tracker, fiwind_client)
            decisions = await repositioner.evaluate_sell_clusters(benchmarks=bms, config=bot_cfg)
            wac_cost = prof_tracker.get_effective_wac_cost() if prof_tracker else (decisions[0].wac_cost if decisions else 0.0)
            fiwind_bid = (await fiwind_client.get_usdt_bid()) if fiwind_client else (decisions[0].fiwind_bid if decisions else 0.0)
            now_str = datetime.now().strftime("%H:%M:%S")
            margin_val = getattr(bot_cfg, "sell_margin_min", 5.0) or 5.0
            text = format_sell_decisions_dashboard(decisions, now_str, wac_cost=wac_cost, fiwind_bid=fiwind_bid, margin_min=margin_val)
        except Exception:
            from core.sell_advisor import SellAdvisor
            advisor = SellAdvisor(self.db)
            advice = advisor.get_sell_advice(benchmarks=(self.engine.last_benchmarks if self.engine else None))
            text = format_sell_advice_report(advice, datetime.now().strftime("%H:%M:%S"))

        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=self.get_sell_inline_panel())

    async def _cmd_margin(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra los márgenes de compra y pisos de venta configurados."""
        config = self.db.load_bot_config()
        sell_m = getattr(config, "sell_margin_min", 5.0)
        target_msg = update.message or update.effective_message
        if target_msg:
            usdt_bm, wac_cost = self._get_usdt_benchmark_ref(), self._get_effective_wac_ref()
            buy_detail = f"\n• Techo máx compra USDT: `${usdt_bm - config.margin_min:,.2f} ARS`" if usdt_bm > 0 else ""
            sell_detail = f"\n• Piso mín seguro venta: `${wac_cost + sell_m:,.2f} ARS` (WAC: ${wac_cost:,.2f})" if wac_cost > 0 else ""
            await target_msg.reply_text(
                f"📏 *MÁRGENES Y COLCHONES ACTIVOS*\n\n"
                f"📥 *Colchón de Compra:* `+{config.margin_min:.2f} ARS`{buy_detail}\n_(Techo de compra = Benchmark Venta - Colchón)_\n\n"
                f"📤 *Piso Ganancia Venta:* `+{sell_m:.2f} ARS`{sell_detail}\n_(Piso seguro de venta = Costo WAC + Piso)_\n\n"
                f"💡 _Para cambiar compra: `/set_margin 10`_\n💡 _Para cambiar venta: `/set_sell_margin 5`_",
                parse_mode="Markdown",
            )

    async def _cmd_set_margin(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Configura el colchón mínimo de compra en ARS."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        target_msg = update.message or update.effective_message
        if not ctx.args:
            config = self.db.load_bot_config()
            if chat_id:
                self._user_state[chat_id], self._user_state_ts[chat_id] = "set_margin", time.time()
            if target_msg:
                await target_msg.reply_text(self._get_buy_margin_prompt_text(config), parse_mode="Markdown", reply_markup=ForceReply(selective=True))
            return

        if chat_id:
            self._user_state.pop(chat_id, None)
            self._user_state_ts.pop(chat_id, None)
        margin = parse_numeric_input(ctx.args[0])
        if margin is None or margin < 0:
            if target_msg:
                await target_msg.reply_text("❌ Colchón de compra inválido. Ejemplo: `/set_margin 10`", parse_mode="Markdown")
            return

        self._apply_margin_update(margin, "margin_min")
        if target_msg:
            lines = [f"✅ *Colchón de compra actualizado a:* `{margin} ARS`"]
            usdt_bm = self._get_usdt_benchmark_ref()
            if usdt_bm > 0:
                lines.append(f"🎯 *Nuevo techo de compra USDT:* `${usdt_bm - margin:,.2f} ARS`")
            await target_msg.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_set_sell_margin(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Configura el piso mínimo de ganancia en venta sobre costo WAC."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        target_msg = update.message or update.effective_message
        if not ctx.args:
            config = self.db.load_bot_config()
            if chat_id:
                self._user_state[chat_id], self._user_state_ts[chat_id] = "set_sell_margin", time.time()
            if target_msg:
                await target_msg.reply_text(self._get_sell_margin_prompt_text(config), parse_mode="Markdown", reply_markup=ForceReply(selective=True))
            return

        if chat_id:
            self._user_state.pop(chat_id, None)
            self._user_state_ts.pop(chat_id, None)
        margin = parse_numeric_input(ctx.args[0])
        if margin is None or margin < 0:
            if target_msg:
                await target_msg.reply_text("❌ Piso de ganancia en venta inválido. Ejemplo: `/set_sell_margin 5`", parse_mode="Markdown")
            return

        self._apply_margin_update(margin, "sell_margin_min")
        if target_msg:
            lines = [f"✅ *Piso de ganancia en venta actualizado a:* `+{margin:.2f} ARS` sobre costo WAC"]
            wac_cost = self._get_effective_wac_ref()
            if wac_cost > 0:
                lines.append(f"🛡️ *Nuevo piso seguro de venta:* `${wac_cost + margin:,.2f} ARS`")
            await target_msg.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_set_rescue(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Configura el margen de rescate con Fiwind."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        if not ctx.args:
            config = self.db.load_bot_config()
            if chat_id:
                self._user_state[chat_id], self._user_state_ts[chat_id] = "set_rescue", time.time()
            sug_line = ""
            try:
                stats_fn = getattr(self.db, "get_fiwind_buy_spread_stats", None)
                if stats_fn:
                    stats = stats_fn()
                    if isinstance(stats, dict) and stats.get("count", 0) > 0 and stats.get("median") is not None:
                        sug_line = f"💡 Sugerencia de colchón: *${stats['median']:,.2f} ARS* _(mediana acumulada en {stats['count']} compras)_\n\n"
                    else:
                        sug_line = "💡 Sugerencia de colchón: _(acumulando datos de compras y Fiwind...)_\n\n"
            except Exception as e:
                logger.debug("Error obteniendo sugerencia de colchón Fiwind: %s", e)

            await update.message.reply_text(
                f"🛟 *Margen de Rescate Fiwind*\n\nMargen de rescate actual: *${config.rescue_margin:.2f} ARS*\n\n{sug_line}"
                f"👉 *¿Cuánto margen de rescate en Fiwind querés?*\n_(Ingresá el valor en ARS por debajo del bid, ej: `10` u `8.5`, o escribí `cancelar`)_",
                parse_mode="Markdown",
                reply_markup=ForceReply(selective=True),
            )
            return

        if chat_id:
            self._user_state.pop(chat_id, None)
            self._user_state_ts.pop(chat_id, None)
        margin = parse_numeric_input(ctx.args[0])
        if margin is None or margin <= 0:
            await update.message.reply_text("❌ Margen de rescate inválido. Debe ser mayor a 0 ARS. Ejemplo: `/set_rescue 10`", parse_mode="Markdown")
            return

        self._apply_margin_update(margin, "rescue_margin")
        await update.message.reply_text(f"✅ *Margen de rescate Fiwind actualizado a:* `${margin:,.2f} ARS`", parse_mode="Markdown")

    async def _cmd_set_volume(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Configura el volumen de referencia ARS."""
        if not ctx.args:
            await update.message.reply_text("Uso: /set_volume 500000")
            return
        amount = parse_numeric_input(ctx.args[0])
        if amount is None or amount <= 0:
            await update.message.reply_text("❌ Monto inválido. Ejemplo: `/set_volume 500000`", parse_mode="Markdown")
            return
        self._apply_margin_update(amount, "volume_ref")
        await update.message.reply_text(f"✅ Volumen de referencia: ${amount:,.0f} ARS")

    async def _cmd_set_step(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Configura el incremento de precio entre pasos."""
        if not ctx.args:
            await update.message.reply_text("Uso: /set_step 0.01")
            return
        step = parse_numeric_input(ctx.args[0])
        if step is None or not (0.01 <= step <= 100.0):
            await update.message.reply_text("❌ Paso inválido. Debe estar entre 0.01 y 100.0 ARS. Ejemplo: `/set_step 0.01`", parse_mode="Markdown")
            return
        self._apply_margin_update(step, "price_step")
        await update.message.reply_text(f"✅ Paso de precio: {step} ARS")

    async def _handle_market_text_input(self, update: Update, text: str, state: str, chat_id: int) -> bool:
        """Procesa entradas interactivas de fijación de balance, márgenes o rescate."""
        val = parse_numeric_input(text)
        if state in ("set_balance", "set_margin", "set_sell_margin") and (val is None or val < 0):
            lbl = "Monto" if state == "set_balance" else ("Colchón de compra" if state == "set_margin" else "Piso de ganancia en venta")
            await update.message.reply_text(f"❌ *{lbl} inválido.*\nPor favor ingresá un número positivo o escribí `cancelar`:", parse_mode="Markdown", reply_markup=ForceReply(selective=True))
            return True
        if state == "set_rescue" and (val is None or val <= 0):
            await update.message.reply_text("❌ *Margen de rescate inválido.*\nDebe ser un número mayor a 0 ARS o escribí `cancelar`:", parse_mode="Markdown", reply_markup=ForceReply(selective=True))
            return True

        self._user_state.pop(chat_id, None)
        self._user_state_ts.pop(chat_id, None)

        if state == "set_balance":
            self._apply_balance_update(val)
            await update.message.reply_text(f"✅ *Saldo ARS actualizado a:* `${val:,.0f} ARS`", parse_mode="Markdown")
        elif state == "set_margin":
            self._apply_margin_update(val, "margin_min")
            lines = [f"✅ *Colchón de compra actualizado a:* `{val} ARS`"]
            usdt_bm = self._get_usdt_benchmark_ref()
            if usdt_bm > 0:
                lines.append(f"🎯 *Nuevo techo de compra USDT:* `${usdt_bm - val:,.2f} ARS`")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        elif state == "set_sell_margin":
            self._apply_margin_update(val, "sell_margin_min")
            lines = [f"✅ *Piso de ganancia en venta actualizado a:* `+{val:.2f} ARS` sobre costo WAC"]
            wac_cost = self._get_effective_wac_ref()
            if wac_cost > 0:
                lines.append(f"🛡️ *Nuevo piso seguro de venta:* `${wac_cost + val:,.2f} ARS`")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        elif state == "set_rescue":
            self._apply_margin_update(val, "rescue_margin")
            await update.message.reply_text(f"✅ *Margen de rescate Fiwind actualizado a:* `${val:,.2f} ARS`", parse_mode="Markdown")

        return True

