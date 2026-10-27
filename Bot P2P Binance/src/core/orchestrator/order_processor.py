"""
Order and Arbitrage Processor for Bot P2P Binance.
Handles fast-path liquidity protection, incoming/completed order notifications,
and Fiwind rescue & opportunity arbitrage detection.
"""
import logging
from typing import Optional, Any, Union, Dict, List, Set, Tuple
from config.settings import (
    FIWIND_RESCUE_MARGIN, FIWIND_OPPORTUNITY_MARGIN,
    STABLECOINS, ASSET_DEFAULTS,
    AD_STATUS_ONLINE, AD_STATUS_OFFLINE,
    FIWIND_ESTIMATED_TRANSFER_FEE_ARS,
    DEFAULT_USDT_BENCHMARK_FALLBACK,
    DEFAULT_BINANCE_SELL_TC_FALLBACK,
)
from telegram_bot.formatters import (
    format_order_notification, format_swap_notification,
    format_open_sell_order_notification,
)

logger = logging.getLogger("orchestrator.orders")


class OrderProcessor:
    """Procesa órdenes de compra/venta, swaps y arbitraje Fiwind."""

    @staticmethod
    async def process_orders_and_arbitrage(engine: Any, spot_prices: dict[str, float], pre_sync_cfg: Any) -> None:
        """Sincroniza órdenes entrantes, completadas y evalúa oportunidades de arbitraje Fiwind."""
        initial_cfg_balance = pre_sync_cfg.balance_ars
        new_orders = await engine.liquidity.sync_orders(spot_prices)
        engine.config.balance_ars = engine.liquidity.balance
        initial_cfg_balance = engine.config.balance_ars
        try:
            engine.db.set_config("balance_ars", str(engine.liquidity.balance))
        except Exception:
            pass

        incoming_orders = (
            engine.liquidity.consume_incoming_orders()
            if hasattr(engine.liquidity, "consume_incoming_orders")
            else []
        )

        # ── Fast-Path: Protección inmediata de liquidez ante órdenes entrantes ──
        incoming_buy_total = sum(o.amount_ars for o in incoming_orders if o.trade_type == "BUY")
        avail_eff = engine.liquidity.available_balance
        if incoming_buy_total > 0 and not engine.config.is_paused:
            logger.info("⚡ Fast-Path Liquidez: Órdenes entrantes por $%.2f ARS (Saldo disponible restante: $%.2f ARS)",
                        incoming_buy_total, avail_eff)
            urgent_pause_ads = []
            for a in engine.my_ads:
                if a.status == AD_STATUS_ONLINE:
                    group_floor = engine.repositioner.get_group_floor_min(a.asset, a.ad_group)
                    defaults = ASSET_DEFAULTS.get(a.asset, {})
                    min_crypto = defaults.get("init_amount", 0.0)
                    spot_p = spot_prices.get(a.asset, 1.0)
                    approx_fiat = spot_p * DEFAULT_USDT_BENCHMARK_FALLBACK if a.asset not in STABLECOINS else DEFAULT_USDT_BENCHMARK_FALLBACK
                    min_crypto_ars = min_crypto * approx_fiat
                    threshold = max(group_floor, min_crypto_ars)
                    if avail_eff < threshold or (a.min_trans_amount > 0 and avail_eff < a.min_trans_amount):
                        urgent_pause_ads.append(a.adv_no)
            if urgent_pause_ads:
                logger.critical("🚨 Fast-Path: Pausando preventivamente en batch %d anuncios descapitalizados: %s",
                                len(urgent_pause_ads), urgent_pause_ads)
                await engine.ads_manager.pause_ads_batch(urgent_pause_ads)
                for a in engine.my_ads:
                    if a.adv_no in urgent_pause_ads:
                        a.status = AD_STATUS_OFFLINE
                        engine.repositioner._paused_by_liquidity.add(a.adv_no)

        # ── Procesar Órdenes ENTRANTES (apenas llegan, pendientes de transferencia) ──
        for inc_order in incoming_orders:
            if inc_order.trade_type == "BUY" and inc_order.asset not in STABLECOINS:
                spot = spot_prices.get(inc_order.asset, 1.0)
                usdt_sell_tc = DEFAULT_BINANCE_SELL_TC_FALLBACK
                if engine.last_benchmarks:
                    bm_vals = [b.avg_top_n_price for b in engine.last_benchmarks.values() if b.avg_top_n_price > 0]
                    if bm_vals:
                        usdt_sell_tc = sum(bm_vals) / len(bm_vals)

                engine._altcoin_notified_orders.add(inc_order.order_no)
                await engine.telegram.notify_altcoin_buy_order(
                    order=inc_order,
                    spot_price=spot,
                    usdt_sell_tc=usdt_sell_tc,
                )
                logger.info("Notificada orden de compra entrante de %s: #%s", inc_order.asset, inc_order.order_no)
            elif inc_order.trade_type == "SELL":
                msg = format_open_sell_order_notification(inc_order)
                await engine.telegram.notify(msg)
                logger.info(
                    "Notificada orden de venta abierta (status=%s): #%s",
                    inc_order.status,
                    inc_order.order_no,
                )

        fiwind_bid = await engine.fiwind.get_usdt_bid()
        for order in new_orders:
            if order.trade_type == "BUY" and fiwind_bid > 0:
                try:
                    engine.db.update_order_fiwind_bid(order.order_no, fiwind_bid)
                except Exception as e_fw:
                    logger.debug("Error guardando fiwind_bid en orden %s: %s", order.order_no, e_fw)

            if order.trade_type != "BUY":
                await engine.telegram.notify(format_order_notification(order))
                continue

            # CASO ALTCOINS: Detección para Swap rápido a USDT
            if order.asset not in STABLECOINS:
                defaults = ASSET_DEFAULTS.get(order.asset, {"min_trans": 10000.0})
                min_trans = defaults["min_trans"]
                had_liquidity = (engine.liquidity.available_balance >= min_trans)
                if not had_liquidity and order.adv_no:
                    await engine.ads_manager.pause_ad(order.adv_no)
                    engine.repositioner._paused_by_liquidity.add(order.adv_no)
                    logger.info("⏸️ Anuncio %s de %s pausado preventivamente tras compra sin saldo", order.adv_no, order.asset)

                if order.order_no in engine._altcoin_notified_orders:
                    # Ya fue notificada en tiempo real apenas llegó. Al liberarse la cripto, confirmamos para el swap.
                    await engine.telegram.notify(
                        f"✅ *¡Compra de {order.asset} liberada en Binance!*\n"
                        f"Orden `#{order.order_no}`: Se acreditaron `{order.amount_crypto:g} {order.asset}` (${order.amount_ars:,.0f} ARS).\n\n"
                        f"👉 _Ya podés realizar el Swap a USDT en Binance Convert._"
                    )
                else:
                    spot = spot_prices.get(order.asset, 1.0)
                    usdt_sell_tc = DEFAULT_BINANCE_SELL_TC_FALLBACK
                    if engine.last_benchmarks:
                        bm_vals = [b.avg_top_n_price for b in engine.last_benchmarks.values() if b.avg_top_n_price > 0]
                        if bm_vals:
                            usdt_sell_tc = sum(bm_vals) / len(bm_vals)

                    engine._altcoin_notified_orders.add(order.order_no)
                    await engine.telegram.notify_altcoin_buy_order(
                        order=order,
                        spot_price=spot,
                        usdt_sell_tc=usdt_sell_tc,
                    )
                continue

            defaults = ASSET_DEFAULTS.get(order.asset, {"min_trans": 10000.0})
            min_trans = defaults["min_trans"]
            had_liquidity = (engine.liquidity.available_balance >= min_trans)

            spot = 1.0 if order.asset == "USDT" else spot_prices.get(order.asset, 1.0)
            spread = (fiwind_bid - order.tc_implicito) if (fiwind_bid > 0 and order.tc_implicito > 0) else 0.0
            gross_profit = (order.amount_crypto * spot) * spread if spread > 0 else 0.0
            net_profit = max(gross_profit - FIWIND_ESTIMATED_TRANSFER_FEE_ARS, 0.0)

            # CASO 1: SIN LIQUIDEZ (Lleno / Recomprado) -> Rescate obligatorio
            if not had_liquidity and fiwind_bid > 0 and order.tc_implicito > 0 and order.tc_implicito <= (fiwind_bid - engine.config.rescue_margin):
                engine.is_fiwind_arbitrage_hold = True
                if hasattr(engine, "ads_manager") and hasattr(engine.ads_manager, "pause_all_sell_ads"):
                    await engine.ads_manager.pause_all_sell_ads()
                if order.adv_no:
                    await engine.ads_manager.pause_ad(order.adv_no)
                    engine.repositioner._paused_by_liquidity.add(order.adv_no)
                    logger.info("⏸️ Anuncio %s pausado preventivamente tras compra de rescate", order.adv_no)

                await engine.telegram.notify_rescue_order(
                    order=order,
                    fiwind_bid=fiwind_bid,
                    spread=spread,
                    net_profit=net_profit,
                    spot_price=spot,
                )

            # CASO 2: CON LIQUIDEZ -> Oportunidad de Arbitraje Opcional ($5 ARS de ganancia)
            elif had_liquidity and fiwind_bid > 0 and order.tc_implicito > 0 and order.tc_implicito <= (fiwind_bid - FIWIND_OPPORTUNITY_MARGIN):
                engine.is_fiwind_arbitrage_hold = True
                if hasattr(engine, "ads_manager") and hasattr(engine.ads_manager, "pause_all_sell_ads"):
                    await engine.ads_manager.pause_all_sell_ads()
                    logger.info("⏸️ Anuncios de venta pausados preventivamente por oportunidad en Fiwind (Orden %s)", order.order_no)

                binance_sell_tc = DEFAULT_BINANCE_SELL_TC_FALLBACK
                if engine.last_benchmarks:
                    bm_vals = [b.avg_top_n_price for b in engine.last_benchmarks.values() if b.avg_top_n_price > 0]
                    if bm_vals:
                        binance_sell_tc = sum(bm_vals) / len(bm_vals)

                await engine.telegram.notify_opportunity_order(
                    order=order,
                    fiwind_bid=fiwind_bid,
                    binance_sell_tc=binance_sell_tc,
                    spread=spread,
                    net_profit=net_profit,
                    spot_price=spot,
                )

            # CASO 3: Compra normal dentro del ciclo
            else:
                await engine.telegram.notify(format_order_notification(order))

        # ── Sync swaps (Spot & Convert - Edge Case 4) ─────────────────
        new_swaps = await engine.liquidity.sync_swaps(engine.assets)
        for swap in new_swaps:
            await engine.telegram.notify(format_swap_notification(swap))

        # Actualizar balance en config recargando la configuración viva para no pisar cambios de Telegram
        fresh_config = engine.db.load_bot_config()
        if abs(fresh_config.balance_ars - initial_cfg_balance) > 0.01:
            engine.liquidity._balance = fresh_config.balance_ars
            if not isinstance(getattr(type(engine.liquidity), "balance", None), property):
                engine.liquidity.balance = fresh_config.balance_ars
            engine.repositioner._last_update_ts.clear()
            logger.info("Sincronizado ajuste externo de balance desde DB/Telegram: $%.2f ARS (cooldowns reseteados)", fresh_config.balance_ars)
        else:
            fresh_config.balance_ars = engine.liquidity.balance
            engine.db.save_bot_config(fresh_config)
        engine.config = fresh_config
