"""
Vistas del dashboard en vivo, reportes de estado y paneles de decisión para Telegram.
Referencia de diseño: docs/ARQUITECTURA.md
"""
from datetime import datetime
from typing import Any, Optional

from config.settings import STABLECOINS
from data.models import BotConfig, MyAd, RepositionDecision
from telegram_bot.formatters.alert_view import escape_md

METHOD_FRIENDLY_NAMES = {
    "MercadoPagoNew": "Mercado Pago", "LemonCash": "Lemon Cash",
    "NaranjaX": "Naranja X", "UalaNew": "Ualá",
    "BancoBrubankNew": "Brubank", "SantanderArgentina": "Santander",
    "bancogalicia": "Galicia", "BankArgentina": "Transferencia (CBU)",
    "Reba": "Reba", "personalpay": "Personal Pay",
    "Fiwind": "Fiwind", "Prex": "Prex",
    "Beloapp": "Belo", "bnaplus": "BNA+", "BancoDelSol": "Banco del Sol",
}


def format_status(
    ads: list[MyAd],
    config: BotConfig,
    balance: float,
    available: float,
) -> str:
    """Formatea el estado general de todos los anuncios."""
    sell_m = getattr(config, "sell_margin_min", 5.0)
    status_str = "\n🔴 *ESTADO: BOT APAGADO (En Pausa)*" if config.is_paused else "\n🟢 *ESTADO: BOT ENCENDIDO (Operando)*"
    lines = [
        "📊 *Estado del Bot*\n",
        f"💰 Balance: ${balance:,.0f} ARS (disponible: ${available:,.0f})",
        f"📏 Colchón Compra: {config.margin_min} ARS | 🛡️ Piso Venta: +{sell_m} ARS | Step: {config.price_step}",
        f"🔄 Polling: cada {config.poll_interval}s",
        status_str,
    ]
    if config.sleep_until:
        lines.append(f"💤 Sleep hasta: {config.sleep_until.strftime('%H:%M')}")

    by_asset: dict[str, list[MyAd]] = {}
    for ad in ads:
        by_asset.setdefault(ad.asset, []).append(ad)

    for asset, asset_ads in sorted(by_asset.items()):
        paused = asset in config.paused_assets
        status_icon = "⏸️" if paused else "🟢"
        lines.append(f"\n{status_icon} *{asset}* ({len(asset_ads)}/3 anuncios):")
        for ad in sorted(asset_ads, key=lambda a: a.ad_group):
            ad_status = "🔴" if ad.status != 1 else "🟢"
            methods_str = ", ".join(escape_md(m) for m in ad.payment_methods[:3])
            if len(ad.payment_methods) > 3:
                methods_str += f"... ({len(ad.payment_methods)} mét.)"
            lines.append(f"  {ad_status} G{ad.ad_group}: ${ad.current_price:,.0f} ({methods_str})")

    return "\n".join(lines)


def format_benchmark(benchmarks: dict) -> str:
    """Formatea benchmarks de USDT por método."""
    lines = ["📈 *Benchmark USDT SELL (promedio top 10)*\n"]
    for method, bm in sorted(benchmarks.items(), key=lambda x: x[1].avg_top_n_price):
        lines.append(f"  {escape_md(method)}: ${bm.avg_top_n_price:,.2f} ARS/USDT")
    return "\n".join(lines)


def format_reconciliation_report(stats: dict) -> str:
    """Formatea el informe de escaneo y reconciliación completa de anuncios (Compras y Ventas)."""
    calib_str = f"🎯 *Anuncios de compra calibrados:* {stats.get('calibrated', 0)}\n" if "calibrated" in stats else ""
    sell_lines = []
    sell_decisions = stats.get("sell_decisions", [])
    sell_verified, sell_created = stats.get("sell_verified", 0), stats.get("sell_created", 0)
    sell_stock, sell_min_req = stats.get("sell_available_stock", 0.0), stats.get("sell_min_required", 100.0)
    sell_low_balance = stats.get("sell_low_balance", False)

    has_real_sell_ads = sell_verified > 0 or sell_created > 0 or any(getattr(d, "adv_no", None) for d in sell_decisions)

    if has_real_sell_ads and sell_decisions:
        sell_lines.append("\n📤 *VENTAS USDT (3 Clusters Calibrados en Frío):*")
        for d in sorted(sell_decisions, key=lambda x: x.cluster_id):
            tag = " _(OFFLINE)_" if not stats.get("total_active") else " _(ONLINE)_"
            pos_info = f" • {d.estimated_position}" if getattr(d, "estimated_position", "") else ""
            status_ico = "🟢" if getattr(d, "is_safe", True) else "⚠️"
            short_no = f" `#{d.adv_no[-4:]}`" if getattr(d, "adv_no", None) else " _(sin anuncio)_"
            title_clean = d.title.split("(")[0].strip() if getattr(d, "title", None) else f"G{d.cluster_id}"
            sell_lines.append(f"{status_ico} *G{d.cluster_id}* ({title_clean}): `${d.suggested_price:,.2f} ARS`{pos_info}{short_no}{tag}")
        if stats.get("sell_calibrated", 0) > 0:
            sell_lines.append(f"🎯 *Anuncios de venta actualizados en Binance:* {stats.get('sell_calibrated', 0)}")
    elif has_real_sell_ads:
        sell_lines.append(f"\n📤 *VENTAS USDT:* {sell_verified} anuncios de venta sincronizados.")
    else:
        if sell_low_balance or sell_stock < sell_min_req:
            sell_lines.append(
                f"\n⚠️ *VENTAS USDT (No creados):*\n"
                f"• Saldo libre en Fondos: `{sell_stock:.2f} USDT`\n"
                f"• Mínimo requerido por Binance para crear anuncios: `{sell_min_req:.0f} USDT`\n"
                f"💡 _No se crearon los anuncios de venta porque Binance exige al menos {sell_min_req:.0f} USDT de saldo disponible. Al depositar o acumular saldo, tocá 'Reconciliar' para crearlos automáticamente._"
            )
        else:
            sell_lines.append("\n📤 *VENTAS USDT:* 0 anuncios de venta presentes.")

    sell_block = "\n".join(sell_lines) if sell_lines else ""
    return (
        "🔄 *Escaneo y Reconciliación de Anuncios Completo*\n\n"
        "📥 *COMPRAS (14 Criptomonedas):*\n"
        f"• Activos verificados: {stats.get('total_assets', 14)} de 14\n"
        f"• Anuncios correctos (3x activo): {stats.get('verified', 0)}\n"
        f"• Anuncios actualizados (5 métodos): {stats.get('updated', 0)}\n"
        f"• Anuncios nuevos creados: {stats.get('created', 0)}\n"
        f"• Anuncios duplicados/excedentes cerrados: {stats.get('closed_duplicates', 0)}\n"
        f"{calib_str}"
        f"• Anuncios ONLINE operando: {stats.get('total_active', 0)}\n"
        f"{sell_block}\n\n"
        "✨ *Catálogo garantizado:* Compras y Ventas sincronizadas y calibradas con el mercado actual."
    )


def format_live_dashboard(
    ads: list[MyAd],
    decisions: dict[str, RepositionDecision],
    spot_prices: dict[str, float],
    config: BotConfig,
    balance: float,
    available: float,
    cycle_num: int = 0,
) -> str:
    """
    Formatea un panel de control en vivo consolidado para Telegram.
    Muestra el estado de cada moneda y los TC implícitos de sus 3 anuncios (G1, G2, G3).
    """
    now_str = datetime.now().strftime("%H:%M:%S")
    lines = [
        "📊 *MONITOR EN VIVO P2P BINANCE ARS* ⚡",
        f"🕒 `{now_str} hs` | 🔄 *Ciclo:* #{cycle_num} (cada {config.poll_interval}s)",
        f"💰 *Saldo:* ${balance:,.0f} ARS (Disp: ${available:,.0f}) | 📏 *Colchón:* {config.margin_min} ARS | 🛡️ *Piso Vta:* +{getattr(config, 'sell_margin_min', 5.0)} ARS",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    by_asset: dict[str, list[MyAd]] = {}
    for ad in ads:
        by_asset.setdefault(ad.asset, []).append(ad)

    asset_order = [
        "USDT", "USDC", "FDUSD", "BTC", "ETH",
        "SOL", "BNB", "XRP", "ADA", "DOGE",
    ]

    lines.append("💵 *ESTABLES*")
    stables_done = False

    for asset in asset_order:
        if asset not in by_asset:
            continue

        if not stables_done and asset not in STABLECOINS:
            lines.append("\n🪙 *ALTCOINS*")
            stables_done = True

        asset_ads = sorted(by_asset[asset], key=lambda a: a.ad_group)
        spot = spot_prices.get(asset, 1.0)
        asset_decisions = [decisions.get(a.adv_no) for a in asset_ads if decisions.get(a.adv_no)]
        reasons = [d.reason for d in asset_decisions]

        if any("war" in r for r in reasons):
            pos_badge = "⚔️ Guerra"
        elif any("first" in r or "gap" in r for r in reasons):
            pos_badge = "🥇 1º Puesto"
        elif any("second" in r for r in reasons):
            pos_badge = "🥈 2º Puesto"
        else:
            pos_badge = "🟢 Activo"

        spot_label = f" (${spot:,.0f})" if spot > 100 else (f" (${spot:.2f})" if spot > 1 else "")
        if asset in STABLECOINS:
            spot_label = ""

        lines.append(f"• *{asset}*{spot_label} — {pos_badge}")

        group_parts = []
        for a in asset_ads:
            d = decisions.get(a.adv_no)
            if d and d.tc_implicito and d.tc_implicito > 0:
                tc, reason = d.tc_implicito, d.reason
            else:
                if a.asset not in STABLECOINS and spot <= 0:
                    tc = 0.0
                else:
                    tc = (a.current_price / spot) if (spot > 0 and asset != "USDT") else a.current_price
                reason = ""

            g_icon = "🥇" if "first" in reason or "gap" in reason else ("🥈" if "second" in reason else "▫️")
            group_parts.append(f"G{a.ad_group}: `{tc:,.2f}` {g_icon}")

        lines.append(f"   {' | '.join(group_parts)}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    status_bot = "🛡️ Modo Centinela (Vigilancia Activa — Anuncios Apagados)" if config.is_paused else "🟢 Bot Operando en Vivo"
    lines.append(f"{status_bot} | 🎯 Auto-actualización continua")
    timeout_mins = max(3, int(round((config.poll_interval * 2) / 60)))
    lines.append(
        f"🕒 *Última actualización:* `{now_str} hs` "
        f"_(Si no se actualizó en {timeout_mins} minutos es porque la conexión se perdió. Revisá)_"
    )
    return "\n".join(lines)


def format_simulation_report(sim_data: dict) -> str:
    """Formatea el reporte de simulación y auditoría anti-baneo para Telegram."""
    if "error" in sim_data:
        return f"⚠️ *Error en simulación:* {escape_md(str(sim_data['error']))}"

    passed = sim_data.get("passed", False)
    total_ads, audited_assets = sim_data.get("total_ads", 0), sim_data.get("audited_assets", 0)
    violations, summaries = sim_data.get("violations", []), sim_data.get("asset_summaries", [])

    lines = []
    if passed:
        lines.append("🛡️ *AUDITORÍA Y SIMULACIÓN ANTI-BANEO (DRY-RUN)*\n\n🟢 *VEREDICTO: 100% BLINDADO Y SEGURO*\n✅ Todas las reglas de Binance P2P fueron validadas sin fallas.")
    else:
        lines.append(f"🛡️ *AUDITORÍA Y SIMULACIÓN ANTI-BANEO (DRY-RUN)*\n\n🔴 *VEREDICTO: SE DETECTARON {len(violations)} VIOLACIONES*\n⚠️ *No encender anuncios hasta corregir las alertas.*")

    lines.append(f"\n📊 *Resumen:*\n• Anuncios auditados: *{total_ads}* ({audited_assets} activos)\n• Llamadas API emitidas: *0* (Simulación en frío)\n• Violaciones a normas Binance: *{len(violations)}*")

    if violations:
        lines.append("\n❌ *Detalle de violaciones detectadas:*")
        for v in violations[:6]:
            lines.append(f"  • *{v.asset} G{v.group}* ({escape_md(v.rule_id)}): {escape_md(v.message)}")
        if len(violations) > 6:
            lines.append(f"  _...y {len(violations) - 6} violaciones más._")

    lines.append("\n📋 *Muestra de precios simulados (Top Activos):*")
    key_assets = ["USDT", "BTC", "ETH", "FDUSD", "USDC"]
    for s in summaries:
        if s["asset"] in key_assets:
            asset = s["asset"]
            lines.append(f"\n🪙 *{asset}*:")
            for g in s["groups"]:
                p_sim, p_cur = g["simulated_price"], g["current_price"]
                init_a, min_l, max_l = g["init_amount"], g["min_limit"], g["max_limit"]
                if g["should_pause"]:
                    lines.append(f"  ⏸️ *G{g['group']}*: Pausado ({escape_md(str(g['pause_reason']))})")
                else:
                    diff_sym = "🔺" if p_sim > p_cur else ("🔻" if p_sim < p_cur else "▫️")
                    lines.append(f"  {diff_sym} *G{g['group']}*: `${p_sim:,.2f}` | Stock: `{init_a:g} {asset}` | Lim: `[${min_l:,.0f} - ${max_l:,.0f}]`")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 *Opciones disponibles:*\n• Para probar en Binance con anuncios apagados: tocá *🎯 Calibrar Precios* (o /calibrar).\n• Para operar en vivo: tocá *🟢 Encender Bot* (o /encender).")
    return "\n".join(lines)


def format_sell_advice_report(clusters: list, now_str: str, ticket_ref: float = 350.0) -> str:
    """Formatea el informe de sugerencias y precios óptimos de venta manual para Telegram."""
    latest_ts = None
    for c in clusters:
        ts = getattr(c, "data_timestamp", None)
        if ts and (latest_ts is None or ts > latest_ts):
            latest_ts = ts

    if latest_ts:
        age_min = max(int((datetime.now() - latest_ts).total_seconds() / 60), 0)
        if age_min > 30:
            sub = f"⚠️ *DATOS HISTÓRICOS* (`{latest_ts.strftime('%H:%M')} hs` — hace {age_min} min)\n⚠️ _El bot estuvo inactivo o sin escanear. Verificá los precios en Binance antes de publicar._"
        else:
            age_label = "hace 1 min" if age_min <= 1 else f"hace {age_min} min"
            sub = f"🕒 `{now_str} hs` | 📊 *Base de datos en vivo ({age_label})*\nℹ️ _Recomendación para organizar tus anuncios manuales en Binance:_"
    else:
        is_any_valid = any(c.is_valid_data for c in clusters)
        sub_title = f"🕒 `{now_str} hs` | 📊 *Base de datos (Solo Lectura)*" if is_any_valid else f"🕒 `{now_str} hs` | ⚠️ *Valores teóricos (Sin datos en DB)*"
        sub = f"{sub_title}\nℹ️ _Recomendación para organizar tus anuncios manuales en Binance:_"

    lines = ["💡 *ASESOR DE VENTAS P2P USDT* ⚡", sub, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]

    for c in clusters:
        methods_str = ", ".join([METHOD_FRIENDLY_NAMES.get(m, m) for m in c.methods])
        icon = "📦" if c.cluster_id == 1 else ("🏦" if c.cluster_id == 2 else "🪙")
        lines.append(f"\n{icon} *ANUNCIO {c.cluster_id}: {c.title.upper()}*")
        if not c.is_valid_data:
            lines.append("   ⚠️ _Datos estimados sobre referencia general (sin cotización directa en este grupo)_")
        lines.append(f"• *Métodos juntos:* `{methods_str}`")
        anchor_name = METHOD_FRIENDLY_NAMES.get(c.anchor_method, c.anchor_method)
        lines.append(f"• *Puesto #1 ancla:* `${c.top1_price:,.2f}` ({anchor_name})")
        lines.append(f"🎯 *PRECIO SUGERIDO:* `${c.suggested_price:,.2f} ARS` (+${c.spread_added:.2f})")
        lines.append(f"🏆 *Posición estimada:* {c.estimated_position}")
        if c.extra_profit_per_usdt > 0:
            lines.append(f"💰 *Ganancia extra vs MP:* `+${c.extra_profit_per_usdt:,.2f}/USDT` (+${c.estimated_extra_ticket_ars:,.0f} en {ticket_ref:g} USDT)")
        lines.append(f"⚡ *Velocidad:* {c.speed_label}")
        if c.notes:
            lines.append(f"💡 _{c.notes}_")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🛡️ *Seguridad:* Este informe es 100% de solo lectura. No emite ninguna orden a Binance.")
    return "\n".join(lines)


def format_sell_decisions_dashboard(
    decisions: list,
    now_str: str,
    wac_cost: float = 0.0,
    fiwind_bid: float = 0.0,
    margin_min: float = 0.0,
) -> str:
    """Formatea el panel interactivo de evaluación y ejecución segura de ventas P2P."""
    lines = [
        "💡 *PANEL DE CONTROL DE VENTA P2P USDT* ⚡",
        f"🕒 `{now_str} hs` | 🛡️ *Guardarraíles Cero Pérdida Activos*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if wac_cost > 0:
        lines.append(f"📥 *Costo Compra (WAC 48h):* `${wac_cost:,.2f} ARS`")
        if margin_min > 0:
            safe_floor = round(max(wac_cost * 1.002, wac_cost + margin_min), 2)
            lines.append(f"🛡️ *Piso Ganancia Venta:* `+${margin_min:,.2f} ARS` _(Piso Seguro: ${safe_floor:,.2f})_")
        else:
            lines.append("🛡️ *Piso de Break-Even:* `+0.2%` sobre WAC")
    if fiwind_bid > 0:
        lines.append(f"🌐 *Oráculo Fiwind Bid:* `${fiwind_bid:,.2f} ARS` _(Referencia externa)_")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for d in decisions:
        c_id, title = getattr(d, "cluster_id", 1), getattr(d, "title", "Grupo")
        icon = "📦" if c_id == 1 else ("🏦" if c_id == 2 else "🪙")
        price, spread = getattr(d, "suggested_price", 0.0), getattr(d, "spread_added", 0.0)
        pos, adv_no = getattr(d, "estimated_position", "Podio"), getattr(d, "adv_no", None)
        ad_str = f"`#{adv_no[-4:]}`" if adv_no else "_(Sin publicar)_"
        is_safe, safety_reason = getattr(d, "is_safe", True), getattr(d, "safety_reason", "")
        min_ars, max_ars = getattr(d, "new_min_trans_amount", 0.0) or 0.0, getattr(d, "new_max_trans_amount", 0.0) or 0.0
        init_u = getattr(d, "new_init_amount", 0.0) or 0.0

        lines.append(f"\n{icon} *ANUNCIO {c_id}: {title.upper()}* | {ad_str}")
        lines.append(f"🎯 *Precio Sugerido:* `${price:,.2f} ARS` (+${spread:.2f})")
        lines.append(f"🏆 *Posición:* {pos}")
        if init_u > 0:
            lines.append(f"📊 *Lote:* `{init_u:.2f} USDT` | Límites: `${min_ars:,.0f}` a `${max_ars:,.0f}` ARS")

        if is_safe:
            lines.append("🛡️ *Seguridad:* ✅ _Protección Break-Even y Oráculo superada_")
        else:
            lines.append(f"🛡️ *Seguridad:* ⚠️ *ALERTA*: {safety_reason}")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nℹ️ _Seleccioná una acción abajo para aplicar cambios con anti-colisión en Binance:_")
    return "\n".join(lines)
