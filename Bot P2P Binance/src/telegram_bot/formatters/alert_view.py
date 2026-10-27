"""
Vistas y formateadores de alertas, notificaciones de órdenes y swaps para Telegram.
"""
from typing import Any
from data.models import MyAd, RepositionDecision, DetectedOrder, DetectedSwap


def escape_md(text: str) -> str:
    """Escapa caracteres especiales de Markdown v1 de Telegram."""
    if not text:
        return ""
    s = str(text)
    for ch in ("_", "*", "`", "["):
        s = s.replace(ch, f"\\{ch}")
    return s


def _translate_reason(reason: str) -> str:
    """Traduce razón técnica a texto legible."""
    translations = {
        "reposition_first": "Reposicionado para estar 1ro",
        "reposition_second_best": "1ro rompe margen → compitiendo por 2do lugar",
        "reposition_max_margin": "Anclado en precio techo de margen seguro",
        "margin_breach": "Margen insuficiente",
        "margin_breach_lower": "Bajado por margen insuficiente",
        "fiwind_rescue_position": "Posición de rescate Fiwind",
        "no_liquidity_lower": "Sin liquidez → bajado al piso",
        "no_liquidity_stable_lower": "Sin liquidez → stable bajada",
        "no_liquidity_altcoin_keep_first": "Sin liquidez, altcoin mantenida 1ra",
        "no_liquidity_altcoin_lower": "Sin liquidez + margen bajo → bajada",
        "war_detected": "Guerra de precios detectada",
        "sin_competidores": "Sin competidores",
        "sin_benchmark": "Sin benchmark disponible",
        "price_unchanged": "Precio sin cambio significativo",
        "sin_spot_price": "Sin precio spot",
    }
    return translations.get(reason, escape_md(str(reason)))


def format_reposition_notification(
    ad: MyAd, decision: RepositionDecision
) -> str:
    """Formatea notificación de reposicionamiento."""
    direction = "⬆️" if decision.new_price > ad.current_price else "⬇️"
    return (
        f"{direction} *Precio actualizado*\n"
        f"  {ad.asset} Grupo {ad.ad_group}\n"
        f"  ${ad.current_price:,.0f} → ${decision.new_price:,.0f}\n"
        f"  Razón: {_translate_reason(decision.reason)}\n"
        f"  Margen: {decision.margin_worst:.1f} ARS\n"
        f"  Competidor: ${decision.competitor_best_price:,.0f}"
    )


def format_order_notification(order: DetectedOrder) -> str:
    """Formatea notificación de orden detectada."""
    if order.trade_type == "BUY":
        icon = "💰"
        action = "Compra completada"
    else:
        icon = "💸"
        action = "Venta completada"

    return (
        f"{icon} *{action}*\n"
        f"  {order.asset}: {order.amount_crypto:.6f}\n"
        f"  Monto: ${order.amount_ars:,.0f} ARS\n"
        f"  Precio: ${order.price:,.0f}\n"
        f"  TC: {order.tc_implicito:.2f} ARS/USDT\n"
        f"  Método: {escape_md(order.payment_method)}\n"
        f"  Contraparte: {escape_md(order.counterparty)}"
    )


def format_swap_notification(swap: DetectedSwap) -> str:
    """Formatea notificación de conversión / swap detectado."""
    return (
        f"🔄 *Swap Detectado ({escape_md(swap.side)})*\n"
        f"  Par/Operación: {escape_md(swap.symbol)}\n"
        f"  Monto Base: {swap.base_amount:,.6f} {escape_md(swap.base_asset)}\n"
        f"  Monto Quote: ${swap.quote_amount:,.2f} {escape_md(swap.quote_asset)}\n"
        f"  Precio/Ratio: {swap.price:,.4f}"
    )


def format_rescue_notification(
    order: DetectedOrder,
    fiwind_bid: float,
    spread: float,
    net_profit: float,
) -> str:
    """Formatea la alerta de compra de rescate con la frase exacta del usuario."""
    return (
        f"🎉 *Felicidades, compra re barata de {order.asset}*\n"
        f"  📦 Cantidad: {order.amount_crypto:.6f} (${order.amount_ars:,.0f} ARS)\n"
        f"  📊 TC Implícito: ${order.tc_implicito:,.2f} ARS/USDT\n\n"
        f"⚠️ *Apaga tu orden en Binance y vende en Fiwind para recompra.*\n\n"
        f"🏦 Fiwind compra ahora a: ${fiwind_bid:,.2f} ARS\n"
        f"💵 Spread de rescate: +${spread:,.2f} ARS/USDT\n"
        f"💰 Ganancia estimada: +${net_profit:,.0f} ARS\n\n"
        f"*(Anuncio en Binance pausado preventivamente para no recibir órdenes sin saldo).*\n\n"
        f"❓ *¿Lo enviaste ya a Fiwind?*"
    )


def format_opportunity_notification(
    order: DetectedOrder,
    fiwind_bid: float,
    binance_sell_tc: float,
    spread_fiwind: float,
    net_profit_fiwind: float,
) -> str:
    """Formatea la alerta de oportunidad de arbitraje opcional cuando se tiene liquidez."""
    spread_binance = (binance_sell_tc - order.tc_implicito) if binance_sell_tc > order.tc_implicito else 0.0
    return (
        f"⚡ *¡OPORTUNIDAD DE ARBITRAJE DETECTADA!*\n"
        f"Compraste {order.asset} muy barato mientras operabas con liquidez:\n"
        f"  📦 Cantidad: {order.amount_crypto:.6f} (${order.amount_ars:,.0f} ARS)\n"
        f"  📊 TC Implícito: ${order.tc_implicito:,.2f} ARS/USDT\n\n"
        f"💡 *Tenés 2 opciones para monetizar esta compra:*\n\n"
        f"1️⃣ *Opción Fiwind (Instantánea, 1 minuto):*\n"
        f"   🏦 Fiwind paga: ${fiwind_bid:,.2f} ARS/USDT\n"
        f"   💵 Spread: +${spread_fiwind:,.2f} ARS/USDT\n"
        f"   💰 Ganancia neta est.: +${net_profit_fiwind:,.0f} ARS\n\n"
        f"2️⃣ *Opción Binance P2P (Mayor ganancia, tiempo de ciclo):*\n"
        f"   📊 Binance P2P venta: ${binance_sell_tc:,.2f} ARS/USDT\n"
        f"   💵 Spread estimado: +${spread_binance:,.2f} ARS/USDT\n\n"
        f"❓ *¿Qué querés hacer con esta orden?*\n\n"
        f"⏱️ *Tiempo límite:* 5 minutos.\n"
        f"_(Tus anuncios de venta en Binance fueron pausados preventivamente. Si no respondés, se reactivarán automáticamente en Binance P2P)._"
    )


def format_daily_report(stats: dict) -> str:
    """Formatea reporte diario."""
    date_str = stats.get("date")
    date_line = f"📅 *Fecha:* `{date_str}`\n\n" if date_str else ""
    profit_val = stats.get("daily_profit_ars", 0.0)
    profit_line = f"\n📈 *Ganancia del día:* ${profit_val:,.0f} ARS"
    return (
        "📊 *Reporte Diario*\n\n"
        f"{date_line}"
        f"🔄 Reposicionamientos: {stats['repositions']}\n"
        f"💰 Compras: {stats['buy_orders']} (${stats['buy_volume_ars']:,.0f} ARS)\n"
        f"💸 Ventas: {stats['sell_orders']} (${stats['sell_volume_ars']:,.0f} ARS)\n"
        f"💵 Balance: ${stats['balance_ars']:,.0f} ARS"
        f"{profit_line}"
    )


def format_profit_report(report: Any) -> str:
    """Formatea el reporte detallado de ganancias para Telegram."""
    date_str = getattr(report, "date", "")
    total_profit = getattr(report, "total_profit_ars", 0.0)
    realized_profit = getattr(report, "realized_profit_ars", 0.0)
    projected_profit = getattr(report, "projected_profit_ars", 0.0)

    buy_orders = getattr(report, "buy_orders_count", 0)
    buy_ars = getattr(report, "total_buy_ars", 0.0)
    buy_usdt = getattr(report, "total_buy_usdt", 0.0)
    avg_buy_tc = getattr(report, "avg_buy_tc", 0.0)

    sell_orders = getattr(report, "sell_orders_count", 0)
    sell_ars = getattr(report, "total_sell_ars", 0.0)
    sell_usdt = getattr(report, "total_sell_usdt", 0.0)
    avg_sell_tc = getattr(report, "avg_sell_tc", 0.0)

    stock_usdt = getattr(report, "remaining_stock_usdt", 0.0)
    proj_price = getattr(report, "projected_sell_price", 0.0)
    proj_source = getattr(report, "projection_source", "")

    lines = [
        f"📈 *REPORTE DE GANANCIAS EN VIVO* ({date_str})\n",
        f"💵 *Ganancia Total del Día:* `+${total_profit:,.0f} ARS`",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"✅ *Ganancia Realizada (Cerrada):* `+${realized_profit:,.0f} ARS`",
        f"   • USDT Vendidos: `{sell_usdt:,.2f} USDT` @ `${avg_sell_tc:,.2f}`",
        f"   • Costo Medio Compra: `${avg_buy_tc:,.2f}`",
    ]
    if sell_usdt > 0 and avg_buy_tc > 0:
        spread_real = avg_sell_tc - avg_buy_tc
        lines.append(f"   • Spread Realizado: `+${spread_real:,.2f}/USDT`")

    lines.append("")
    if stock_usdt >= 0.01:
        lines.append(f"⏳ *Ganancia Proyectada (En Stock):* `+${projected_profit:,.0f} ARS`")
        lines.append(f"   • Stock Pendiente: `{stock_usdt:,.2f} USDT` equiv.")
        lines.append(f"   • Valuación según: *{escape_md(proj_source)}*")
        if proj_price > avg_buy_tc and avg_buy_tc > 0:
            lines.append(f"   • Spread Proyectado: `+${proj_price - avg_buy_tc:,.2f}/USDT`")
    else:
        lines.append("⏳ *Ganancia Proyectada:* `$0 ARS` (Todo el stock del día fue vendido)")

    lines.append("\n📊 *Actividad del Día:*")
    lines.append(f"   • Compras: *{buy_orders}* (`${buy_ars:,.0f} ARS` / `{buy_usdt:,.2f} USDT`)")
    lines.append(f"   • Ventas: *{sell_orders}* (`${sell_ars:,.0f} ARS` / `{sell_usdt:,.2f} USDT`)")

    return "\n".join(lines)


def format_altcoin_buy_swap_alert(
    order: DetectedOrder,
    spot_price: float,
    usdt_sell_tc: float,
) -> str:
    """
    Formatea la alerta de orden de compra entrante de Altcoin para Telegram.
    Calcula TC implícito en vivo antes de transferir y proyección de Swap a USDT.
    """
    amount_crypto = order.amount_crypto
    amount_ars = order.amount_ars
    price_ars = order.price

    tc_implicito = order.tc_implicito if order.tc_implicito > 0 else (price_ars / spot_price if spot_price > 0 else 0.0)
    usdt_estimated = amount_crypto * spot_price if spot_price > 0 else 0.0
    spread = (usdt_sell_tc - tc_implicito) if (usdt_sell_tc > 0 and tc_implicito > 0) else 0.0
    gross_ars = usdt_estimated * usdt_sell_tc if usdt_sell_tc > 0 else 0.0
    net_profit_ars = max(gross_ars - amount_ars, 0.0) if spread > 0 else 0.0

    lines = [
        f"🔔 *¡NUEVA ORDEN DE COMPRA DE {order.asset}!* ⚡",
        "⚠️ *PENDIENTE DE TRANSFERENCIA (Revisá antes de transferir)*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🆔 *Orden:* `#{order.order_no}`",
    ]
    if order.counterparty:
        lines.append(f"👤 *Vendedor:* {escape_md(order.counterparty)}")
    if order.payment_method:
        lines.append(f"💳 *Método de pago:* {escape_md(order.payment_method)}")

    lines.extend([
        f"💸 *Monto a transferir:* `${amount_ars:,.0f} ARS`",
        f"📥 *Cantidad a recibir:* `{amount_crypto:g} {order.asset}`",
        f"🏷️ *Precio pactado:* `${price_ars:,.2f} ARS/{order.asset}`",
        "",
        "📊 *TIPO DE CAMBIO IMPLÍCITO (EN VIVO)* ⚡",
        f"• 📈 *Spot en Binance:* `${spot_price:,.2f} USDT`",
        f"• 💱 *TC Implícito:* `${tc_implicito:,.2f} ARS/USDT`",
        f"• 🏦 *P2P USDT Venta:* `${usdt_sell_tc:,.2f} ARS`",
        "",
        "💡 *SWAP RECOMENDADO A USDT:*",
        f"🔄 *Al convertir recibirías:* `~{usdt_estimated:,.2f} USDT`",
        f"💰 *Spread proyectado:* `+${spread:,.2f}/USDT` *(+${net_profit_ars:,.0f} ARS)* 🟢" if spread > 0 else f"⚠️ *Spread neutro/ajustado:* `${spread:,.2f}/USDT`",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"ℹ️ _Revisá el TC implícito antes de transferir. Al recibir los {order.asset}, abrí Convert para cambiar a USDT._",
    ])
    return "\n".join(lines)


def format_open_sell_order_notification(order: DetectedOrder) -> str:
    """
    Formatea la alerta de orden de venta P2P abierta (status 1: en proceso, status 2: comprador marcó pagado).
    """
    is_paid = str(order.status) in ("2", "BUYER_PAYED")
    if is_paid:
        header = "🚨 *¡COMPRADOR MARCÓ PAGADO EN VENTA P2P!* 🚨"
        sub = "⚠️ *VERIFICÁ TU BANCO/BILLETERA ANTES DE LIBERAR*"
    else:
        header = "📥 *NUEVA ORDEN DE VENTA EN CURSO* ⏳"
        sub = "ℹ️ _Esperando transferencia del comprador..._"

    lines = [
        header,
        sub,
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🆔 *Orden:* `#{order.order_no}`",
    ]
    if order.counterparty:
        lines.append(f"👤 *Comprador:* {escape_md(order.counterparty)}")
    if order.payment_method:
        lines.append(f"💳 *Método de pago:* {escape_md(order.payment_method)}")

    lines.extend([
        f"💰 *Monto a recibir:* `${order.amount_ars:,.0f} ARS`",
        f"📤 *Cripto a liberar:* `{order.amount_crypto:g} {order.asset}`",
        f"🏷️ *Precio pactado:* `${order.price:,.2f} ARS/{order.asset}`",
    ])

    if is_paid:
        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "🛡️ *PROTOCOLO DE SEGURIDAD ESTRICTO:*",
            "1. 🏦 *Ingresá a tu App bancaria/billetera* y confirmá que el dinero ESTÉ ACREDITADO en saldo disponible (no retenciones ni transferencias 'en revisión').",
            f"2. 🔍 *Verificá el titular*: El remitente del dinero DEBE coincidir con el nombre de Binance (*{escape_md(order.counterparty)}*). ¡Rechazá pagos de terceros!",
            "3. 🚫 *NUNCA liberes por capturas de pantalla o chat*: Los comprobantes se falsifican en segundos. Solo tu app bancaria dice la verdad.",
        ])
    else:
        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "⏳ *El comprador tiene tiempo límite para pagar.* Te avisaremos en cuanto marque el pago.",
        ])

    return "\n".join(lines)
