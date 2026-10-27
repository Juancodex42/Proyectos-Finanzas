"""
Motor de Reposicionamiento y Anti-Colisión de Ventas P2P (SellRepositioner).
Gestiona la estrategia de 3 anuncios simultáneos de venta USDT (G1 Billeteras, G2 Bancos, G3 Fintechs).
Referencia de diseño: docs/ARQUITECTURA.md
"""
import asyncio
import logging
import math
from datetime import datetime
from typing import Optional

from config import settings
from config.settings import (
    DEFAULT_SELL_MARGIN_MIN,
    SELL_AD_PRICE_DIFF_ARS,
    SELL_AUTO_EXECUTION,
    SELL_CASCADE_MODE,
    SELL_GROUP_FLOORS_ARS,
    SELL_GROUP_LIMIT_FACTORS,
    SELL_MIN_MARGIN_PCT,
    SELL_MIN_PRICE_CHANGE_TRIGGER,
    SELL_MIN_STOCK_CHANGE_TRIGGER,
    SELL_MIN_USDT_THRESHOLD,
)
from core.ads.manager import AdsManager
from core.fiwind_client import FiwindClient
from core.pricing.ticket_filter import calculate_capital_capacity_ars, is_stock_capacity_sufficient
from core.profit_tracker import ProfitTracker
from core.sell_advisor import (
    SELL_CLUSTERS_CONFIG,
    calculate_cluster_cartelera_average,
)
from core.sell_guardrails import SellGuardrails
from data.database import Database
from data.models import Benchmark, BotConfig, SellDecision

logger = logging.getLogger("sell_repositioner")


class SellRepositioner:
    """Motor de cálculo, anti-colisión y ejecución para ventas P2P en Binance SAPI."""

    def __init__(
        self,
        db: Database,
        ads_manager: AdsManager,
        profit_tracker: ProfitTracker,
        fiwind_client: Optional[FiwindClient] = None,
        cascade_mode: Optional[str] = None,
    ) -> None:
        self.db = db
        self.ads = ads_manager
        self.profit_tracker = profit_tracker
        self.fiwind = fiwind_client or FiwindClient()
        self.cascade_mode = cascade_mode

    async def evaluate_sell_clusters(
        self,
        benchmarks: Optional[dict[str, Benchmark]] = None,
        available_crypto_stock: Optional[float] = None,
        config: Optional[BotConfig] = None,
    ) -> list[SellDecision]:
        """Evalúa los 3 clusters de venta, calcula precios y aplica guardarraíles."""
        db_bms = self.db.get_latest_benchmarks() if self.db else {}
        bms = {**db_bms, **(benchmarks or {})}

        bot_cfg = config or (self.db.load_bot_config() if self.db else None)
        raw_sell_m = getattr(bot_cfg, "sell_margin_min", None)
        sell_margin_ars = float(raw_sell_m) if raw_sell_m is not None else float(DEFAULT_SELL_MARGIN_MIN)

        wac_cost = 0.0
        try:
            wac_cost = self.profit_tracker.get_effective_wac_cost()
        except Exception as e:
            logger.debug("No se pudo obtener WAC cost: %s", e)

        fiwind_bid = 0.0
        try:
            fiwind_bid = await self.fiwind.get_usdt_bid()
        except Exception as e:
            logger.debug("No se pudo obtener Fiwind Bid: %s", e)

        my_sell_ads = self.db.get_my_sell_ads("USDT") if self.db else []
        my_sell_by_group = {a.ad_group: a for a in my_sell_ads}

        if available_crypto_stock is None or available_crypto_stock == 350.0:
            client = getattr(self.ads, "client", None)
            if client and hasattr(client, "get_funding_asset"):
                try:
                    free_funding = await client.get_funding_asset("USDT")
                    if free_funding is not None:
                        available_crypto_stock = max(float(free_funding), 0.0)
                        logger.info("📦 Inventario de Fondos detectado: %.2f USDT libres", available_crypto_stock)
                except Exception as e_stock:
                    logger.debug("No se pudo consultar saldo de Fondos para ventas: %s", e_stock)
            if available_crypto_stock is None:
                available_crypto_stock = 350.0

        raw_decisions: list[SellDecision] = []
        mp_bm = bms.get("MercadoPagoNew")
        base_mp_price = 0.0
        if mp_bm and mp_bm.individual_prices:
            valid_p = [float(p) for p in mp_bm.individual_prices if float(p) > 0]
            if valid_p:
                base_mp_price = valid_p[0]
        if base_mp_price <= 0.0 and mp_bm and mp_bm.avg_top_n_price > 0:
            base_mp_price = float(mp_bm.avg_top_n_price)

        for cfg in SELL_CLUSTERS_CONFIG:
            c_id = cfg["id"]
            title, methods, anchor, speed = cfg["title"], cfg["methods"], cfg["anchor_method"], cfg["speed_label"]
            fallback_ref = fiwind_bid if fiwind_bid > 0 else (base_mp_price if base_mp_price > 0 else 0.0)

            (
                target_price, top1, leader_method, prices_top10, bm_timestamp,
            ) = calculate_cluster_cartelera_average(
                cluster_methods=methods, benchmarks=bms, anchor_method=anchor, fallback_price=fallback_ref,
            )
            if base_mp_price <= 0.0 and top1 > 0:
                base_mp_price = top1

            if c_id == 1:
                target_price = round(top1 - 0.01, 2) if top1 > 0 else round(fallback_ref, 2)
                pos_str = f"Puesto #1 ({leader_method})"
            else:
                if prices_top10:
                    pos = sum(1 for p in prices_top10 if p <= target_price) + 1
                    pos_str = f"Puesto #{pos} ({leader_method})"
                else:
                    pos_str = f"Puesto #2 ({leader_method})"

            is_safe, safety_reason = SellGuardrails.audit_sell_price(
                price=target_price, wac_cost=wac_cost, fiwind_bid=fiwind_bid,
                data_timestamp=bm_timestamp, individual_prices=prices_top10,
                min_margin_pct=SELL_MIN_MARGIN_PCT, min_margin_ars=sell_margin_ars,
            )

            if not is_safe and ("Break-Even" in safety_reason or "inferior al costo WAC" in safety_reason or "piso de seguridad" in safety_reason):
                if wac_cost > 0:
                    pct_floor = wac_cost * (1.0 + SELL_MIN_MARGIN_PCT)
                    ars_floor = wac_cost + sell_margin_ars if sell_margin_ars > 0 else 0.0
                    safe_floor = round(max(pct_floor, ars_floor), 2)
                    if safe_floor > target_price:
                        target_price = safe_floor
                        is_safe, safety_reason = SellGuardrails.audit_sell_price(
                            price=target_price, wac_cost=wac_cost, fiwind_bid=fiwind_bid,
                            data_timestamp=bm_timestamp, individual_prices=prices_top10,
                            min_margin_pct=SELL_MIN_MARGIN_PCT, min_margin_ars=sell_margin_ars,
                        )
                        if is_safe:
                            tag = f"WAC + piso de ganancia (${safe_floor:,.2f})" if sell_margin_ars > 0 else f"WAC + margen (${safe_floor:,.2f})"
                            safety_reason = f"Ajustado a piso de costo {tag}"
                            if prices_top10:
                                if c_id == 1:
                                    pos_str = "Puesto #1 (Piso WAC)"
                                else:
                                    pos = sum(1 for p in prices_top10 if p <= target_price) + 1
                                    pos_str = f"Puesto #{pos}"

            existing_ad = my_sell_by_group.get(c_id)
            adv_no = existing_ad.adv_no if existing_ad else None
            spread_added = round(target_price - top1, 2) if top1 > 0 else 0.0
            should_pause_val = not is_safe
            pause_reason_val = f"guardrail_breach: {safety_reason}" if not is_safe else ""

            dec = SellDecision(
                cluster_id=c_id, title=title, anchor_method=leader_method, suggested_price=target_price,
                top1_price=top1, spread_added=spread_added, estimated_position=pos_str, wac_cost=wac_cost,
                fiwind_bid=fiwind_bid, is_safe=is_safe, safety_reason=safety_reason, adv_no=adv_no,
                status=existing_ad.status if existing_ad else 1, methods=methods, speed_label=speed,
                should_pause=should_pause_val, pause_reason=pause_reason_val, timestamp=datetime.now(),
            )
            raw_decisions.append(dec)

        return self.resolve_sell_collisions(
            raw_decisions, available_crypto_stock=available_crypto_stock,
            cascade_mode=self.cascade_mode or SELL_CASCADE_MODE,
        )

    def resolve_sell_collisions(
        self,
        decisions: list[SellDecision],
        available_crypto_stock: Optional[float] = None,
        cascade_mode: Optional[str] = None,
    ) -> list[SellDecision]:
        """Aplica la Regla 5.1 con separación >= 0.15% (>= $0.35 ARS) e Inventario Compartido."""
        if not decisions:
            return []
        if available_crypto_stock is None:
            available_crypto_stock = 350.0

        safe_decs = [d for d in decisions if d.is_safe]
        sell_step = max(0.35, float(SELL_AD_PRICE_DIFF_ARS))
        d1 = next((d for d in safe_decs if d.cluster_id == 1), None)
        d2 = next((d for d in safe_decs if d.cluster_id == 2), None)
        d3 = next((d for d in safe_decs if d.cluster_id == 3), None)
        valid_map = {d.cluster_id: d for d in [d1, d2, d3] if d and d.suggested_price > 0}

        mode = cascade_mode or getattr(self, "cascade_mode", None)
        if not mode:
            pos_str = str(d1.estimated_position) if d1 else ""
            mode = "SPREAD_FIRST" if ("#1" not in pos_str and ("#2" in pos_str or "#3" in pos_str)) else SELL_CASCADE_MODE

        if valid_map:
            if mode in ("HIGH_ROTATION_LADDER", "OPCION_A", "TIGHT_LADDER"):
                if d1 and d1.suggested_price > 0:
                    base_p = round(d1.suggested_price, 2)
                    d1.suggested_price = base_p
                    if d3:
                        d3.suggested_price = round(base_p + sell_step, 2)
                    if d2:
                        d2.suggested_price = round(base_p + (2 * sell_step if d3 else sell_step), 2)
                elif d3 and d3.suggested_price > 0:
                    base_p = round(d3.suggested_price, 2)
                    d3.suggested_price = base_p
                    if d2:
                        d2.suggested_price = round(base_p + sell_step, 2)
                elif d2 and d2.suggested_price > 0:
                    d2.suggested_price = round(d2.suggested_price, 2)

            elif mode == "MARKET_INDEPENDENT":
                highest_grp = max(valid_map.keys(), key=lambda gid: valid_map[gid].suggested_price)
                base_p = round(valid_map[highest_grp].suggested_price, 2)
                if d1:
                    d1.suggested_price = base_p
                if d2:
                    d2.suggested_price = round(base_p + sell_step, 2)
                if d3:
                    d3.suggested_price = round(base_p + 2 * sell_step, 2)
            else:
                highest_grp = max(valid_map.keys(), key=lambda gid: valid_map[gid].suggested_price)
                base_p = round(valid_map[highest_grp].suggested_price, 2)
                if highest_grp == 2:
                    if d2: d2.suggested_price = base_p
                    if d3: d3.suggested_price = round(base_p + sell_step, 2)
                    if d1: d1.suggested_price = round(base_p + 2 * sell_step, 2)
                elif highest_grp == 3:
                    if d3: d3.suggested_price = base_p
                    if d2: d2.suggested_price = round(base_p + sell_step, 2)
                    if d1: d1.suggested_price = round(base_p + 2 * sell_step, 2)
                else:
                    if d1: d1.suggested_price = base_p
                    if d2: d2.suggested_price = round(base_p + sell_step, 2)
                    if d3: d3.suggested_price = round(base_p + 2 * sell_step, 2)

            for d in [d1, d2, d3]:
                if d and d.top1_price:
                    d.spread_added = round(d.suggested_price - d.top1_price, 2)

        sorted_decs = sorted(decisions, key=lambda d: d.cluster_id)
        existing_ads = self.db.get_my_sell_ads() if self.db else []
        ads_by_group = {a.ad_group: a for a in existing_ads}

        for dec in sorted_decs:
            grp = dec.cluster_id
            dec.new_init_amount = math.floor(float(available_crypto_stock) * 100.0) / 100.0
            capacity_ars = calculate_capital_capacity_ars(dec.new_init_amount, dec.suggested_price)

            if dec.new_init_amount < SELL_MIN_USDT_THRESHOLD or capacity_ars < 15000.0:
                dec.should_pause = True
                dec.pause_reason = f"saldo_menor_a_piso (Capacidad ${capacity_ars:,.0f} < $15k ARS o Stock {dec.new_init_amount:.2f} < {SELL_MIN_USDT_THRESHOLD} USDT)"
                dec.should_update = False
                dec.new_min_trans_amount = 15000.0
                dec.new_max_trans_amount = max(15000.0, float(capacity_ars))
                continue

            if dec.should_pause:
                dec.should_update = False
                continue

            min_f, max_f = SELL_GROUP_LIMIT_FACTORS.get(grp, (0.50, 1.00))
            target_max = float(max(15000.0, math.floor(capacity_ars * max_f)))
            target_min = float(max(15000.0, math.floor(capacity_ars * min_f)))
            if target_min >= target_max:
                target_min = max(15000.0, math.floor(target_max * 0.50))

            dec.new_min_trans_amount = target_min
            dec.new_max_trans_amount = target_max

            ad_for_grp = ads_by_group.get(grp)
            if ad_for_grp and ad_for_grp.status != 1:
                dec.should_update = True
            elif ad_for_grp and ad_for_grp.current_price > 0:
                p_diff = abs(dec.suggested_price - ad_for_grp.current_price)
                stk_ref = ad_for_grp.surplus_amount if (ad_for_grp.surplus_amount is not None and ad_for_grp.surplus_amount > 0) else (ad_for_grp.init_amount or 0.0)
                stk_diff = abs(dec.new_init_amount - stk_ref)
                limits_shift = (
                    ((ad_for_grp.min_trans_amount or 0.0) > 0 and abs(dec.new_min_trans_amount - ad_for_grp.min_trans_amount) / ad_for_grp.min_trans_amount >= 0.05)
                    or ((ad_for_grp.max_trans_amount or 0.0) > 0 and abs(dec.new_max_trans_amount - ad_for_grp.max_trans_amount) / ad_for_grp.max_trans_amount >= 0.05)
                )
                dec.should_update = (p_diff >= SELL_MIN_PRICE_CHANGE_TRIGGER or stk_diff >= SELL_MIN_STOCK_CHANGE_TRIGGER or limits_shift)
            else:
                dec.should_update = True

        return sorted_decs

    async def execute_sell_decisions(
        self,
        decisions: list[SellDecision],
        config: Optional[BotConfig] = None,
        allow_offline: bool = False,
    ) -> list[tuple[SellDecision, bool]]:
        """Ejecuta actualizaciones en Binance en orden seguro anti-187055."""
        results: list[tuple[SellDecision, bool]] = []
        if not decisions:
            return results

        existing_ads = {a.adv_no: a for a in (self.db.get_my_sell_ads() if self.db else [])}

        for dec in decisions:
            if dec.should_pause and dec.adv_no:
                curr_ad = existing_ads.get(dec.adv_no)
                if curr_ad and curr_ad.status == 1:
                    logger.warning("⏸️ Pausando preventivamente venta G%d: %s", dec.cluster_id, dec.pause_reason)
                    try:
                        ok_p = await self.ads.pause_sell_ad(dec.adv_no)
                        results.append((dec, ok_p))
                    except Exception as e_p:
                        logger.error("Error pausando venta %s: %s", dec.adv_no, e_p)
                        results.append((dec, False))

        valid_to_exec = [d for d in decisions if d.is_safe and d.adv_no and d.should_update and not d.should_pause]
        if not valid_to_exec:
            return results

        down_moves, up_moves, other_moves = [], [], []
        for d in valid_to_exec:
            c_ad = existing_ads.get(d.adv_no)
            if c_ad and c_ad.current_price > 0:
                if d.suggested_price < c_ad.current_price - 0.001:
                    down_moves.append(d)
                elif d.suggested_price > c_ad.current_price + 0.001:
                    up_moves.append(d)
                else:
                    other_moves.append(d)
            else:
                up_moves.append(d)

        down_moves.sort(key=lambda d: d.suggested_price)
        up_moves.sort(key=lambda d: d.suggested_price, reverse=True)
        ordered_decs = down_moves + up_moves + other_moves
        active_prices = {a.adv_no: float(a.current_price or 0.0) for a in existing_ads.values() if a.adv_no}

        for dec in ordered_decs:
            try:
                conflict = any(o_no != dec.adv_no and o_p > 0 and abs(dec.suggested_price - o_p) < 0.30 for o_no, o_p in active_prices.items())
                if conflict:
                    logger.warning("🛡️ Anti-187055: Solapamiento < $0.30 ARS en Venta G%d ($%.2f). Omitiendo.", dec.cluster_id, dec.suggested_price)
                    results.append((dec, False))
                    continue

                curr_ad = existing_ads.get(dec.adv_no)
                executed_c = max(float(curr_ad.init_amount) - float(curr_ad.surplus_amount), 0.0) if curr_ad and (curr_ad.init_amount or 0.0) > 0 and curr_ad.surplus_amount is not None else 0.0
                total_init = math.floor(float(executed_c + dec.new_init_amount) * 100.0) / 100.0 if dec.new_init_amount is not None else (curr_ad.init_amount if curr_ad else None)
                c_surplus = float(getattr(curr_ad, "surplus_amount", 0.0) or 0.0) if curr_ad else 0.0

                is_depleted = (c_surplus < 10.0 or not is_stock_capacity_sufficient(c_surplus, dec.suggested_price or 1600.0, dec.new_min_trans_amount or 15000.0)) and (dec.new_init_amount or 0.0) >= 10.0
                needs_downsizing = curr_ad is not None and c_surplus > ((dec.new_init_amount or 0.0) + 2.0) and (dec.new_init_amount or 0.0) >= 10.0
                init_to_send = total_init if (is_depleted or needs_downsizing) else None

                ok = await self.ads.update_sell_ad_params(
                    adv_no=dec.adv_no, price=dec.suggested_price, init_amount=init_to_send,
                    surplus_amount=dec.new_init_amount, min_trans_amount=dec.new_min_trans_amount,
                    max_trans_amount=dec.new_max_trans_amount,
                )
                results.append((dec, ok))
                if ok:
                    active_prices[dec.adv_no] = dec.suggested_price
                    logger.info("✅ Venta G%d (#%s) actualizada: $%.2f ARS (Stock: %.2f USDT)", dec.cluster_id, dec.adv_no[-4:] if dec.adv_no else "----", dec.suggested_price, dec.new_init_amount or 0.0)
                    cfg = config or (self.db.load_bot_config() if self.db else None)
                    is_paused_ad = bool(cfg and dec.adv_no in (getattr(cfg, "paused_ads", None) or []))
                    should_resume = bool(getattr(settings, "SELL_AUTO_EXECUTION", True)) and not allow_offline and not (cfg and getattr(cfg, "is_paused", False)) and curr_ad and curr_ad.status != 1 and not is_paused_ad

                    has_stock_info = (dec.new_init_amount is not None) or (curr_ad and getattr(curr_ad, "surplus_amount", None) is not None)
                    if has_stock_info:
                        eff_surplus = dec.new_init_amount if dec.new_init_amount is not None else float(getattr(curr_ad, "surplus_amount", 0.0) or 0.0)
                        eff_p = dec.suggested_price or float(getattr(curr_ad, "current_price", 1600.0) or 1600.0)
                        eff_min = dec.new_min_trans_amount or float(getattr(curr_ad, "min_trans_amount", 0.0) or 15000.0)
                        can_resume = (eff_surplus >= 10.0) and is_stock_capacity_sufficient(eff_surplus, eff_p, eff_min)
                    else:
                        can_resume = True

                    if should_resume and can_resume:
                        try:
                            if await self.ads.resume_sell_ad(dec.adv_no):
                                logger.info("▶️ Venta G%d reactivada ONLINE en Binance.", dec.cluster_id)
                        except Exception:
                            pass
                await asyncio.sleep(0.7)
            except Exception as e:
                logger.error("Error ejecutando venta G%d: %s", dec.cluster_id, e)
                results.append((dec, False))

        return results

