"""
Manejador de callbacks para configuración de márgenes, calibración, reportes y confirmaciones Fiwind.
"""
import logging
import time
from datetime import datetime
from typing import Any

from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update

from telegram_bot.formatters.alert_view import escape_md, format_profit_report
from telegram_bot.formatters.dashboard_view import (
    format_reconciliation_report,
    format_sell_advice_report,
    format_sell_decisions_dashboard,
    format_simulation_report,
)
from telegram_bot.handlers.cb_ads import safe_edit_text

logger = logging.getLogger(__name__)


async def handle_margin_callback(bot: Any, update: Update, query: Any, data: str) -> bool:
    """Maneja callbacks de márgenes, simulaciones, balance, reportes y confirmaciones Fiwind."""
    chat_id = update.effective_chat.id if update.effective_chat else (query.message.chat_id if query.message else None)

    if data.startswith("fw_yes_"):
        order_no = data.replace("fw_yes_", "")
        timer = bot._fiwind_timers.pop(order_no, None)
        if timer and not timer.done():
            timer.cancel()
        bot._fiwind_messages.pop(order_no, None)

        info = bot.pending_rescues.pop(order_no, None)
        if not info:
            await query.answer("Esta operación ya fue confirmada o expiró.", show_alert=True)
            return True
        try:
            await query.answer("Confirmando acreditación...")
        except Exception:
            pass

        amount_usdt = info.get("amount_usdt", info["amount_crypto"])
        payout_ars = amount_usdt * info["fiwind_bid"]
        asset = info["asset"]
        adv_no = info["adv_no"]

        ad_reactivated = False
        if bot.engine:
            new_bal = bot.engine.liquidity.balance + payout_ars
            bot.engine.liquidity.set_balance(new_bal)
            config = bot.db.load_bot_config()
            config.balance_ars = new_bal
            bot.db.save_bot_config(config)
            bot.engine.config = config

            has_other_opt = any(v.get("is_opportunity") for v in bot.pending_rescues.values())
            if not has_other_opt:
                bot.engine.is_fiwind_arbitrage_hold = False

            if adv_no and not config.is_paused and not config.sleep_until and asset not in config.paused_assets and adv_no not in config.paused_ads:
                try:
                    await bot.engine.ads_manager.resume_ad(adv_no)
                    ad_reactivated = True
                    logger.info("Anuncio %s reactivado tras confirmación de venta en Fiwind", adv_no)
                except Exception as e_res:
                    logger.error("Error reactivando %s: %s", adv_no, e_res)

            if hasattr(bot.engine, "repositioner"):
                bot.engine.repositioner._paused_by_liquidity.discard(adv_no)

        status_txt = f"▶️ Anuncio de {asset} reactivado en Binance." if ad_reactivated else "⏸️ El anuncio permanece pausado."
        base = escape_md(query.message.text if query.message else "")
        new_txt = f"{base}\n\n━━━━━━━━━━━━━━━━━━━━━━\n✅ *¡CONFIRMADO POR EL USUARIO!*\n💵 Se acreditaron *${payout_ars:,.0f} ARS* al balance.\n{status_txt}"
        await safe_edit_text(query, new_txt)
        return True

    if data.startswith("fw_no_"):
        await query.answer("Entendido. El anuncio permanece pausado.", show_alert=False)
        return True

    if data.startswith("fw_opt_go_"):
        order_no = data.replace("fw_opt_go_", "")
        timer = bot._fiwind_timers.pop(order_no, None)
        if timer and not timer.done():
            timer.cancel()

        info = bot.pending_rescues.get(order_no)
        if not info:
            await query.answer("Esta operación ya fue procesada o expiró.", show_alert=True)
            return True

        try:
            await query.answer("Elegiste ir a Fiwind. Anuncios de venta pausados preventivamente.")
        except Exception:
            pass

        if bot.engine:
            bot.engine.is_fiwind_arbitrage_hold = True
            if hasattr(bot.engine, "ads_manager") and hasattr(bot.engine.ads_manager, "pause_all_sell_ads"):
                await bot.engine.ads_manager.pause_all_sell_ads()

        keyboard = [[
            InlineKeyboardButton("✅ Ya vendí y cobré en Fiwind", callback_data=f"fw_yes_{order_no}"),
            InlineKeyboardButton("↩️ Volver a Binance P2P", callback_data=f"fw_cancel_{order_no}"),
        ]]
        base = escape_md(query.message.text if query.message else "")
        new_txt = f"{base}\n\n━━━━━━━━━━━━━━━━━━━━━━\n🚀 *ELEGISTE IR A FIWIND*\n⚠️ Tus anuncios de venta en Binance permanecen pausados para proteger tu stock.\n\n👉 *Pasos:*\n1. Retirá tus {info.get('amount_crypto', 0):.4f} {info.get('asset', 'USDT')} a Fiwind.\n2. Vendelos por ARS en Fiwind.\n3. Cuando tengas los pesos acreditados, confirmalo con el botón de abajo:"
        await safe_edit_text(query, new_txt, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if data.startswith("fw_opt_stay_") or data.startswith("fw_cancel_"):
        is_stay = data.startswith("fw_opt_stay_")
        order_no = data.replace("fw_opt_stay_", "") if is_stay else data.replace("fw_cancel_", "")
        timer = bot._fiwind_timers.pop(order_no, None)
        if timer and not timer.done():
            timer.cancel()
        bot._fiwind_messages.pop(order_no, None)
        bot.pending_rescues.pop(order_no, None)

        ans_msg = "¡Perfecto! Te quedás en Binance." if is_stay else "Operación cancelada. Volviendo a Binance P2P..."
        await query.answer(ans_msg, show_alert=False)

        has_other_opt = any(v.get("is_opportunity") for v in bot.pending_rescues.values())
        if not has_other_opt and bot.engine:
            bot.engine.is_fiwind_arbitrage_hold = False
            if hasattr(bot.engine, "ads_manager") and hasattr(bot.engine.ads_manager, "resume_all_sell_ads"):
                await bot.engine.ads_manager.resume_all_sell_ads()

        base = escape_md(query.message.text if query.message else "")
        title = "🏦 *ELEGISTE QUEDARTE EN BINANCE*" if is_stay else "↩️ *OPERACIÓN EN FIWIND CANCELADA*"
        new_txt = f"{base}\n\n━━━━━━━━━━━━━━━━━━━━━━\n{title}\n▶️ Tus anuncios de venta en Binance (G1, G2, G3) fueron reactivados y continuarán operando en P2P."
        await safe_edit_text(query, new_txt, reply_markup=None)
        return True

    if data == "bot_simulate":
        await query.answer("Iniciando simulación y auditoría anti-baneo...")
        await query.edit_message_text(
            "🛡️ *Ejecutando Simulación y Auditoría Anti-Baneo...*\n\n• Escaneando mercado real en vivo (Spot + Benchmarks USDT + Libros P2P)...\n• Evaluando precios óptimos por grupo sin tocar Binance (Dry-Run)...\n• Auditando 6 reglas de Binance P2P con AntiBanValidator...",
            parse_mode="Markdown",
        )
        sim_data = await bot.engine.audit_market_dry_run() if bot.engine else {}
        report = format_simulation_report(sim_data) if sim_data else "Simulación no disponible."
        await query.edit_message_text(report, parse_mode="Markdown", reply_markup=bot.get_inline_panel())
        return True

    if data == "bot_calibrate":
        await query.answer("Calibrando precios y cantidades en Binance...")
        await query.edit_message_text("⏳ *Calibrando precios y cantidades en Binance...*\n\n• Escaneando mercado real en vivo...\n• Calibrando compras y ventas USDT...\n\n⏳ _Ajustando anuncios sin encenderlos (OFFLINE)..._", parse_mode="Markdown")
        count = await bot.engine.calibrate_all_ads() if bot.engine else 0
        sell_count = getattr(bot.engine, "_last_sell_calibrated_count", 0) if bot.engine else 0
        sell_decisions = getattr(bot.engine, "_last_sell_decisions", []) if bot.engine else []
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

        await query.edit_message_text(
            f"🎯 *CALIBRACIÓN COMPLETADA*\n\n📥 *Compras actualizadas:* *{count}* anuncios\n{sell_block}\n\n• Precios y cantidades de cripto 100% alineados al balance y al mercado.\n\nPodés encender el bot cuando quieras con *🟢 Encender Bot*.",
            parse_mode="Markdown",
            reply_markup=bot.get_inline_panel(),
        )
        return True

    if data == "bot_reconcile":
        await query.answer("Reconciliando anuncios con Binance...")
        await query.edit_message_text("🔄 *Reconciliando estructura con Binance...*\n\n• Verificando 42 compras...\n• Verificando 3 ventas USDT...\n• Calibrando precios en frío...\n\n⏳ _Esto puede demorar unos 30-45 segundos..._", parse_mode="Markdown")
        stats = await bot.engine.reconcile_ads(set_online=False) if bot.engine else {}
        report = format_reconciliation_report(stats) if stats else "Reconciliación completada."
        await query.edit_message_text(report, parse_mode="Markdown", reply_markup=bot.get_inline_panel())
        return True

    if data == "bot_status":
        await query.answer()
        text = await bot.engine.get_status_text() if bot.engine else "⚠️ Engine no disponible"
        if text and len(text) > 4000:
            cut = text.rfind("\n", 0, 4000)
            text = (text[:cut] if cut > 0 else text[:4000]) + "\n..."
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=bot.get_reply_keyboard())
        return True

    if data == "bot_balance":
        await query.answer()
        text = bot.engine.liquidity.get_status_text() if bot.engine else "⚠️ Engine no disponible"
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=bot.get_reply_keyboard())
        return True

    if data == "bot_profit":
        await query.answer("Calculando ganancias...")
        if bot.engine and hasattr(bot.engine, "profit_tracker") and bot.engine.profit_tracker:
            try:
                report = await bot.engine.profit_tracker.calculate_profit()
                text = format_profit_report(report)
            except Exception as e_prof:
                logger.error("Error calculando ganancias en callback: %s", e_prof)
                text = f"⚠️ Error calculando ganancias: {escape_md(str(e_prof))}"
        else:
            stats = bot.db.get_daily_stats()
            text = f"📈 *Ganancias del Día*\n\n• Ganancia estimada: *${stats.get('daily_profit_ars', 0.0):,.0f} ARS*\n• Compras: {stats['buy_orders']} (${stats['buy_volume_ars']:,.0f} ARS)\n• Ventas: {stats['sell_orders']} (${stats['sell_volume_ars']:,.0f} ARS)"
        try:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=bot.get_inline_panel())
        except Exception:
            await query.message.reply_text(text, parse_mode="Markdown", reply_markup=bot.get_reply_keyboard())
        return True

    if data in ("bot_set_buy_margin", "bot_set_sell_margin"):
        await query.answer()
        config = bot.db.load_bot_config()
        is_buy = data == "bot_set_buy_margin"
        if chat_id:
            bot._user_state[chat_id], bot._user_state_ts[chat_id] = ("set_margin" if is_buy else "set_sell_margin"), time.time()
        prompt = bot._get_buy_margin_prompt_text(config) if is_buy else bot._get_sell_margin_prompt_text(config)
        if query.message and hasattr(query.message, "reply_text"):
            await query.message.reply_text(prompt, parse_mode="Markdown", reply_markup=ForceReply(selective=True))
        elif chat_id and bot._app:
            await bot._app.bot.send_message(chat_id=chat_id, text=prompt, parse_mode="Markdown", reply_markup=ForceReply(selective=True))
        return True

    if data == "bot_sell_advisor":
        await query.answer("Consultando precios de venta...")
        from core.pricing.sell_repositioner import SellRepositioner
        from core.profit_tracker import ProfitTracker
        from core.fiwind_client import FiwindClient
        try:
            bms = bot.engine.last_benchmarks if bot.engine else None
            fiwind_client = (bot.engine.fiwind if bot.engine else None) or FiwindClient()
            ads_mgr = bot.engine.ads_manager if bot.engine else None
            prof_tracker = (bot.engine.profit_tracker if bot.engine else None) or (ProfitTracker(bot.db) if bot.db else None)
            bot_cfg = bot.engine.config if bot.engine else bot.db.load_bot_config()
            repositioner = SellRepositioner(bot.db, ads_mgr, prof_tracker, fiwind_client)
            decisions = await repositioner.evaluate_sell_clusters(benchmarks=bms, config=bot_cfg)
            wac_cost = prof_tracker.get_effective_wac_cost() if prof_tracker else (decisions[0].wac_cost if decisions else 0.0)
            fiwind_bid = (await fiwind_client.get_usdt_bid()) if fiwind_client else (decisions[0].fiwind_bid if decisions else 0.0)
            margin_val = getattr(bot_cfg, "sell_margin_min", 5.0) or 5.0
            text = format_sell_decisions_dashboard(decisions, datetime.now().strftime("%H:%M:%S"), wac_cost=wac_cost, fiwind_bid=fiwind_bid, margin_min=margin_val)
        except Exception:
            from core.sell_advisor import SellAdvisor
            advisor = SellAdvisor(bot.db)
            advice = advisor.get_sell_advice(benchmarks=(bot.engine.last_benchmarks if bot.engine else None))
            text = format_sell_advice_report(advice, datetime.now().strftime("%H:%M:%S"))

        try:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=bot.get_sell_inline_panel())
        except Exception as e:
            if "not modified" not in str(e).lower():
                raise e
        return True

    if data == "refresh_dash":
        await query.answer()
        config = bot.db.load_bot_config()
        st_icon = "🔴 APAGADO" if config.is_paused else "🟢 ENCENDIDO"
        await query.edit_message_text(
            f"🤖 *Panel de Control P2P*\n\n• Estado: *{st_icon}*\n• Margen compra: *${config.margin_min:.2f} ARS*\n• Margen venta: *+${getattr(config, 'sell_margin_min', 5.0):.2f} ARS*\n• Balance: *${config.balance_ars:,.0f} ARS*",
            parse_mode="Markdown",
            reply_markup=bot.get_inline_panel(),
        )
        return True

    return False
