"""
Manejador de callbacks para pausa, reanudación, aplicación y eliminación de anuncios.
"""
import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from telegram_bot.formatters.alert_view import escape_md
from telegram_bot.formatters.dashboard_view import format_reconciliation_report

logger = logging.getLogger(__name__)


async def safe_edit_text(query: Any, text: str, reply_markup=None):
    """Edita el texto del mensaje de callback de forma segura tolerando errores de Markdown."""
    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception:
        try:
            await query.edit_message_text(text.replace("*", ""), reply_markup=reply_markup)
        except Exception as e:
            logger.debug("Error editando mensaje en callback: %s", e)


async def handle_ad_callback(bot: Any, update: Update, query: Any, data: str) -> bool:
    """Maneja callbacks relacionados con anuncios de compra, venta y estado del bot."""
    if data == "bot_power_off":
        await query.answer("Apagando bot...")
        if bot.engine:
            await bot.engine.turn_off()
        else:
            config = bot.db.load_bot_config()
            config.is_paused = True
            bot.db.save_bot_config(config)
        await query.edit_message_text(
            "🔴 *BOT APAGADO*\n\n• Todos los anuncios BUY en Binance han sido pausados.\n• El ciclo de reposicionamiento está detenido.\n\nPodés volver a encenderlo con el botón de abajo o con /encender.",
            parse_mode="Markdown",
            reply_markup=bot.get_inline_panel(),
        )
        return True

    if data == "bot_power_on":
        await query.answer("Iniciando encendido seguro...")
        await query.edit_message_text(
            "⏳ *Encendiendo bot de forma segura (Pre-flight Calibration)...*\n\n1️⃣ Verificando estructura de 42 anuncios...\n2️⃣ Calibrando precios y cantidades en frío (OFFLINE)...\n3️⃣ Poniendo anuncios ONLINE en Binance...\n\nPor favor espera unos segundos.",
            parse_mode="Markdown",
        )
        stats = {}
        if bot.engine:
            stats = await bot.engine.turn_on()
        else:
            config = bot.db.load_bot_config()
            config.is_paused, config.sleep_until = False, None
            bot.db.save_bot_config(config)

        report = format_reconciliation_report(stats) if stats else ""
        calib_txt = f"\n• Anuncios calibrados en frío: *{stats.get('calibrated', 0)}*" if stats.get("calibrated") is not None else ""
        msg = f"🟢 *BOT ENCENDIDO Y OPERANDO DE FORMA SEGURA*\n\n• Anuncios puestos ONLINE con precios y montos óptimos.{calib_txt}\n• Cero exposición a precios viejos.\n• Ciclo de reposicionamiento continuo activo.\n\n"
        if report:
            msg += f"{report}\n\n"
        msg += "Podés apagarlo cuando quieras con el botón de abajo o con /apagar."
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=bot.get_inline_panel())
        return True

    if data.startswith("alt_pause_"):
        parts = data.split("_")
        asset, adv_no = (parts[2] if len(parts) > 2 else ""), (parts[3] if len(parts) > 3 else "")
        paused_ok = False
        if adv_no and bot.engine:
            try:
                paused_ok = await bot.engine.ads_manager.pause_ad(adv_no)
                if paused_ok:
                    config = bot.db.load_bot_config()
                    config.paused_ads.add(adv_no)
                    bot.db.save_bot_config(config)
                    bot.engine.config = config
                    bot.engine._notify_state_change()
            except Exception as e:
                logger.error("Error pausando anuncio %s: %s", adv_no, e)
        elif asset and bot.engine:
            try:
                await bot.engine.ads_manager.pause_by_asset(asset)
                config = bot.db.load_bot_config()
                config.paused_assets.add(asset)
                bot.db.save_bot_config(config)
                bot.engine.config = config
                bot.engine._notify_state_change()
                paused_ok = True
            except Exception as e:
                logger.error("Error pausando anuncios de %s: %s", asset, e)

        ans_text = f"⏸️ Anuncio de {asset} pausado en Binance." if paused_ok else f"⚠️ No se pudo pausar el anuncio de {asset}."
        await query.answer(ans_text)
        base = escape_md(query.message.text if query.message else "")
        new_txt = f"{base}\n\n━━━━━━━━━━━━━━━━━━━━━━\n⏸️ *ANUNCIO DE {asset} PAUSADO EN BINANCE*\nNo entrarán más compras de {asset} mientras realizás el swap y la venta de USDT."
        await safe_edit_text(query, new_txt, reply_markup=None)
        return True

    if data.startswith("alt_done_"):
        parts = data.split("_")
        asset = parts[3] if len(parts) > 3 else ""
        await query.answer("✅ Swap a USDT confirmado por el usuario.", show_alert=False)
        base = escape_md(query.message.text if query.message else "")
        new_txt = f"{base}\n\n━━━━━━━━━━━━━━━━━━━━━━\n✅ *¡SWAP A USDT CONFIRMADO POR EL USUARIO!*\nOperación de {asset} marcada como completada con éxito."
        await safe_edit_text(query, new_txt, reply_markup=None)
        return True

    if data.startswith("alt_close_"):
        parts = data.split("_")
        order_no, asset = (parts[2] if len(parts) > 2 else ""), (parts[3] if len(parts) > 3 else "")
        await query.answer("Alerta cerrada. El bot continúa operando normalmente.", show_alert=False)
        base = escape_md(query.message.text if query.message else "")
        new_txt = f"{base}\n\n━━━━━━━━━━━━━━━━━━━━━━\n👁️ *ALERTA CERRADA*\nOrden #{order_no} ({asset}) revisada por el usuario. El bot continúa operando normalmente."
        await safe_edit_text(query, new_txt, reply_markup=None)
        return True

    if data == "bot_delete_buy_confirm":
        await query.answer()
        keyboard = [[
            InlineKeyboardButton("⚠️ Sí, eliminar COMPRAS", callback_data="confirm_delete_buy_ads"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_delete_buy_ads"),
        ]]
        await query.message.reply_text(
            "⚠️ *CONFIRMACIÓN DE SEGURIDAD*\n\n¿Estás seguro de que deseas *ELIMINAR DEFINITIVAMENTE* todos tus anuncios de *COMPRA* en Binance?\n\n🛡️ *Tus anuncios de VENTA no serán tocados ni modificados.*\n⏸️ El bot se pondrá en pausa preventiva tras eliminarlos.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return True

    if data == "confirm_delete_buy_ads":
        await query.answer("Eliminando anuncios de compra...")
        await query.edit_message_text("⏳ *Eliminando todos los anuncios de COMPRA en Binance...*\nPor favor espera unos momentos.", parse_mode="Markdown")
        if bot.engine:
            stats = await bot.engine.delete_all_buy_ads()
            res_text = (
                f"🗑️ *ANUNCIOS DE COMPRA ELIMINADOS*\n\n• Anuncios encontrados: *{stats.get('total_found', 0)}*\n"
                f"• Eliminados en Binance: *{stats.get('deleted', 0)}*\n• Errores: *{stats.get('errors', 0)}*\n\n"
                f"🛡️ *Tus anuncios de VENTA permanecen intactos.*\n⏸️ El bot quedó *pausado*.\n\n"
                f"Podés volver a crearlos cuando quieras con *🔄 Reconciliar Anuncios* o *🟢 Encender Bot*."
            )
        else:
            res_text = "⚠️ Bot Engine no disponible."
        await query.edit_message_text(res_text, parse_mode="Markdown", reply_markup=bot.get_inline_panel())
        return True

    if data == "cancel_delete_buy_ads":
        await query.answer("Operación cancelada")
        await query.edit_message_text("❌ *Operación cancelada*\nNo se eliminó ningún anuncio.", parse_mode="Markdown", reply_markup=bot.get_inline_panel())
        return True

    if data == "bot_delete_sell_confirm":
        await query.answer()
        keyboard = [[
            InlineKeyboardButton("⚠️ Sí, eliminar VENTAS", callback_data="confirm_delete_sell_ads"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_delete_sell_ads"),
        ]]
        await query.message.reply_text(
            "⚠️ *CONFIRMACIÓN DE SEGURIDAD*\n\n¿Estás seguro de que deseas *ELIMINAR DEFINITIVAMENTE* todos tus anuncios de *VENTA* en Binance?\n\n🛡️ *Tus anuncios de COMPRA no serán tocados ni modificados.*\n⏸️ El bot se pondrá en pausa preventiva tras eliminarlos.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return True

    if data == "confirm_delete_sell_ads":
        await query.answer("Eliminando anuncios de venta...")
        await query.edit_message_text("⏳ *Eliminando todos los anuncios de VENTA en Binance...*\nPor favor espera unos momentos.", parse_mode="Markdown")
        if bot.engine:
            stats = await bot.engine.delete_all_sell_ads()
            res_text = (
                f"🗑️ *ANUNCIOS DE VENTA ELIMINADOS*\n\n• Anuncios encontrados: *{stats.get('total_found', 0)}*\n"
                f"• Eliminados en Binance: *{stats.get('deleted', 0)}*\n• Errores: *{stats.get('errors', 0)}*\n\n"
                f"🛡️ *Tus anuncios de COMPRA permanecen intactos.*\n⏸️ El bot quedó *pausado*.\n\n"
                f"Podés volver a crearlos cuando quieras desde *💡 Sugerencia Venta*."
            )
        else:
            res_text = "⚠️ Bot Engine no disponible."
        await query.edit_message_text(res_text, parse_mode="Markdown", reply_markup=bot.get_inline_panel())
        return True

    if data == "cancel_delete_sell_ads":
        await query.answer("Operación cancelada")
        await query.edit_message_text("❌ *Operación cancelada*\nNo se eliminó ningún anuncio de venta.", parse_mode="Markdown", reply_markup=bot.get_inline_panel())
        return True

    if data == "bot_sell_pause_all":
        await query.answer("Pausando anuncios de venta...")
        ads_mgr = bot.engine.ads_manager if bot.engine else None
        if not ads_mgr:
            await query.edit_message_text("⚠️ Engine no disponible.", reply_markup=bot.get_sell_inline_panel())
            return True
        paused_count = await ads_mgr.pause_all_sell_ads()
        await query.edit_message_text(f"⏸️ Se pausaron {paused_count} anuncios de venta en Binance.", reply_markup=bot.get_sell_inline_panel())
        return True

    if data.startswith("bot_sell_apply_"):
        target = data.replace("bot_sell_apply_", "")
        await query.answer("Auditando y aplicando precios de venta...")
        from core.pricing.sell_repositioner import SellRepositioner
        bms = bot.engine.last_benchmarks if bot.engine else None
        fiwind_client = bot.engine.fiwind if bot.engine else None
        ads_mgr = bot.engine.ads_manager if bot.engine else None
        prof_tracker = bot.engine.profit_tracker if bot.engine else None
        if not ads_mgr or not prof_tracker:
            await query.edit_message_text("⚠️ Engine no disponible para ejecutar ventas.", reply_markup=bot.get_sell_inline_panel())
            return True

        try:
            await ads_mgr.sync_my_sell_ads()
        except Exception as e_sync:
            logger.warning("Error sincronizando anuncios de venta antes de aplicar: %s", e_sync)

        repositioner = SellRepositioner(bot.db, ads_mgr, prof_tracker, fiwind_client)
        bot_cfg = bot.engine.config if bot.engine else bot.db.load_bot_config()
        decisions = await repositioner.evaluate_sell_clusters(benchmarks=bms, config=bot_cfg)

        if target == "all":
            to_exec = decisions
        else:
            try:
                grp_target = int(target)
                target_dec = next((d for d in decisions if d.cluster_id == grp_target), None)
                if target_dec:
                    all_sell_ads = bot.db.get_my_sell_ads("USDT")
                    has_collision, collision_msg = False, ""
                    sell_step_min, rank_map = 0.30, {1: 1, 3: 2, 2: 3}
                    target_rank = rank_map.get(target_dec.cluster_id, target_dec.cluster_id)
                    for ad in all_sell_ads:
                        if ad.adv_no != target_dec.adv_no and ad.status == 1 and ad.current_price > 0:
                            price_diff = abs(target_dec.suggested_price - ad.current_price)
                            if round(price_diff, 2) < sell_step_min:
                                has_collision, collision_msg = True, f"colisionaría (<$0.30 ARS Error 187055) con G{ad.ad_group} (${ad.current_price:,.2f})"
                                break
                            ad_rank = rank_map.get(ad.ad_group, ad.ad_group)
                            if (target_rank < ad_rank and target_dec.suggested_price >= ad.current_price) or (target_rank > ad_rank and target_dec.suggested_price <= ad.current_price):
                                has_collision, collision_msg = True, f"rompería la jerarquía Opción A con G{ad.ad_group} (${ad.current_price:,.2f})"
                                break
                    if has_collision:
                        await query.edit_message_text(
                            f"⚠️ *No se puede actualizar únicamente G{grp_target}*:\nEl precio propuesto (${target_dec.suggested_price:,.2f}) {collision_msg} en Binance.\n\n"
                            f"👉 *Recomendación:* Usá el botón *'🚀 Publicar Todos los Precios'* para actualizar los 3 armónicamente con anti-colisión.",
                            parse_mode="Markdown",
                            reply_markup=bot.get_sell_inline_panel(),
                        )
                        return True
                    to_exec = [target_dec]
                else:
                    to_exec = []
            except Exception:
                to_exec = []

        results = await repositioner.execute_sell_decisions(to_exec)
        resp_lines = ["⚡ *RESULTADO DE PUBLICACIÓN DE VENTAS P2P* ⚡\n"]
        for dec, success in results:
            st = "✅ Actualizado en Binance" if success else "❌ Error al actualizar"
            adv_label = f"`#{dec.adv_no[-4:]}`" if dec.adv_no else ""
            resp_lines.append(f"• *G{dec.cluster_id} ({dec.title}):* ${dec.suggested_price:,.2f} ARS {adv_label}\n  ↳ Estado: {st}")
        if not results:
            resp_lines.append("⚠️ No se ejecutó ningún anuncio.\nVerificá que tus anuncios de VENTA estén creados en Binance o revisá las alertas de margen.")
        resp_lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        await query.edit_message_text("\n".join(resp_lines), parse_mode="Markdown", reply_markup=bot.get_sell_inline_panel())
        return True

    return False
