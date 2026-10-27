"""
Módulo de Guardia Anti-Colisión y Separación de Anuncios P2P.

Garantiza que ningún par de anuncios del mismo activo colisione en Binance
(Error 187055 / 83714) ni perfore el collar legal de precios (Error 187031).
"""
import logging
import math
import time
from typing import Callable, Optional

from config.settings import (
    ASSET_PRECISION,
    MIN_AD_PRICE_DIFF_RATIO,
    PASSIVE_PRICE_HYSTERESIS_PCT,
    PASSIVE_UPDATE_COOLDOWN_SECONDS,
)
from data.models import BotConfig, MyAd, RepositionDecision

logger = logging.getLogger(__name__)


class CollisionGuard:
    """
    Guardia de colisiones, espaciado delta y cotas de seguridad por activo.
    """

    def __init__(self) -> None:
        self._asset_price_bounds: dict[str, tuple[float, float]] = {}

    def set_bounds(self, asset: str, min_credible: float, max_allowed: float) -> None:
        """Registra las cotas de precio (mínimo legal creíble, techo de margen) para un activo."""
        self._asset_price_bounds[asset] = (min_credible, max_allowed)

    def get_bounds(self, asset: str) -> tuple[float, float]:
        """Obtiene las cotas de precio registradas para un activo."""
        return self._asset_price_bounds.get(asset, (0.0, 0.0))

    def should_apply_passive_hold(
        self,
        ad: MyAd,
        decision: RepositionDecision,
        final_price: float,
        config: BotConfig,
        last_update_ts: dict[str, float],
        allow_offline: bool = False,
    ) -> bool:
        """
        Determina si una actualización de precio es meramente pasiva para evitar spam (Error 83714).
        NUNCA frena si un competidor P2P nos superó o si estamos fuera del margen o collar legal.
        """
        if ad.current_price <= 0:
            return False
        if not (ad.status == 1 or (allow_offline and ad.status == 3)):
            return False

        min_credible, max_allowed = self.get_bounds(ad.asset)

        # 1. Urgencia por margen o collar oficial de Binance
        if max_allowed > 0 and ad.current_price > max_allowed:
            return False
        if min_credible > 0 and ad.current_price < min_credible:
            return False

        # 2. Urgencia competitiva: competidor P2P nos superó o empató
        full_reason = decision.reason or ""
        base_reason = full_reason.split("+")[0]
        was_staggered = "+anti_collision" in full_reason
        is_competitive = base_reason in ("reposition_first", "reposition_second_best", "reposition_sell_less_gap")

        if is_competitive and decision.competitor_best_price > 0:
            if ad.current_price <= decision.competitor_best_price and (
                not was_staggered or final_price > decision.competitor_best_price
            ):
                return False
            overpay_gap = ad.current_price - final_price
            if not was_staggered and overpay_gap >= max(0.30, round(ad.current_price * 0.0003, 2)):
                return False

        # 3. Movimiento pasivo (ticks de spot / escalonamiento pasivo G2/G3)
        pct_change = abs(final_price - ad.current_price) / ad.current_price
        now_ts = time.time()
        elapsed = now_ts - last_update_ts.get(ad.adv_no, 0.0)

        if pct_change >= PASSIVE_PRICE_HYSTERESIS_PCT * 2.5:
            return False

        return pct_change < PASSIVE_PRICE_HYSTERESIS_PCT or elapsed < PASSIVE_UPDATE_COOLDOWN_SECONDS

    def resolve_asset_price_collisions(
        self,
        asset: str,
        evaluated: list[tuple[MyAd, RepositionDecision]],
        config: BotConfig,
        all_asset_ads: Optional[list[MyAd]] = None,
        allow_offline: bool = False,
        last_update_ts: Optional[dict[str, float]] = None,
        available_balance: float = 0.0,
        recompute_fn: Optional[Callable] = None,
    ) -> list[tuple[MyAd, RepositionDecision]]:
        """
        Garantiza que ningún par de anuncios del mismo activo colisione en Binance ni caiga
        por debajo del piso legal:
        1. Usa MIN_AD_PRICE_DIFF_RATIO (0.15% en ARS).
        2. Respeta anuncios fijos como anclas inamovibles.
        3. Escalonamiento estricto G1 > G2 > G3.
        4. Protección Anti-187031 con rebote seguro sobre min_credible_price.
        5. Separación contra anclas fijas.
        6. Deduplicación de initAmount (Regla 5.1.1) y límites.
        7. Doble cola de ejecución ascendente/descendente (Anti-187055).
        """
        if not evaluated:
            return []

        ts_map = last_update_ts or {}
        min_credible, max_allowed = self.get_bounds(asset)
        evaluated_adv_nos = {a.adv_no for a, _ in evaluated}
        fixed_anchor_prices: list[float] = []

        if all_asset_ads:
            for other_ad in all_asset_ads:
                if other_ad.adv_no not in evaluated_adv_nos and other_ad.current_price > 0:
                    fixed_anchor_prices.append(other_ad.current_price)

        non_movable_reasons = (
            "war_detected", "api_error_cooldown", "error_83714_cooldown",
            "margin_breach", "sin_spot_price", "sin_benchmark", "sin_precio_valido",
        )
        movable_pairs: list[tuple[MyAd, RepositionDecision]] = []
        for ad, decision in evaluated:
            is_above_ceiling = (max_allowed > 0 and ad.current_price > max_allowed)
            if (decision.reason in non_movable_reasons and not is_above_ceiling) or ad.adv_no in config.paused_ads:
                decision.should_update = False
                if ad.current_price > 0:
                    fixed_anchor_prices.append(ad.current_price)
            else:
                if is_above_ceiling and decision.reason in non_movable_reasons:
                    decision.new_price = max_allowed
                    decision.should_update = True
                    decision.reason = f"{decision.reason}+margin_ceiling_cut"
                movable_pairs.append((ad, decision))

        if not movable_pairs:
            return []

        sample_prices = [
            p for a, d in movable_pairs for p in (d.new_price, a.current_price) if p and p > 0
        ] + fixed_anchor_prices
        valid_prices = [p for p in sample_prices if p > 0]
        if not valid_prices:
            return []

        max_ref_price = max(valid_prices)
        min_buffer = max(config.price_step, round(max_ref_price * MIN_AD_PRICE_DIFF_RATIO, 2))

        highest_desired = max(
            (item[1].new_price if item[1].new_price > 0 else item[0].current_price)
            for item in movable_pairs
        )
        sorted_pairs = sorted(movable_pairs, key=lambda item: item[0].ad_group)

        desired_prices: list[float] = []
        last_price: Optional[float] = None
        for idx_g, (ad, decision) in enumerate(sorted_pairs):
            p = decision.new_price if decision.new_price > 0 else ad.current_price
            if idx_g == 0 and highest_desired > p:
                p = highest_desired
            if max_allowed > 0:
                p = min(p, max_allowed)
            if min_credible > 0:
                p = max(p, min_credible)

            if last_price is not None and round(last_price - p, 2) < min_buffer:
                p = round(last_price - min_buffer, 2)
            last_price = p
            desired_prices.append(p)

        if min_credible > 0 and desired_prices and desired_prices[-1] < min_credible:
            n = len(desired_prices)
            desired_prices[-1] = min_credible
            for i in range(n - 2, -1, -1):
                if round(desired_prices[i] - desired_prices[i + 1], 2) < min_buffer:
                    cand = round(desired_prices[i + 1] + min_buffer, 2)
                    if max_allowed > 0:
                        cand = min(cand, max_allowed)
                    desired_prices[i] = cand

        unfit_indices: set[int] = set()
        for idx in range(len(desired_prices)):
            p = desired_prices[idx]
            if idx > 0 and round(desired_prices[idx - 1] - p, 2) < min_buffer:
                p = round(desired_prices[idx - 1] - min_buffer, 2)
            for anchor_p in fixed_anchor_prices:
                if round(abs(p - anchor_p), 2) < min_buffer:
                    down_cand = round(anchor_p - min_buffer, 2)
                    up_cand = round(anchor_p + min_buffer, 2)
                    prev_ok_up = (idx == 0) or (round(desired_prices[idx - 1] - up_cand, 2) >= min_buffer)
                    if min_credible <= 0 or down_cand >= min_credible:
                        p = down_cand
                    elif (max_allowed <= 0 or up_cand <= max_allowed) and prev_ok_up:
                        p = up_cand
                    else:
                        unfit_indices.add(idx)

            if min_credible > 0 and p < min_credible:
                unfit_indices.add(idx)

            desired_prices[idx] = sorted_pairs[idx][0].current_price if idx in unfit_indices else max(config.price_step, p)

        precision = ASSET_PRECISION.get(asset, 2)
        step_u = 1.0 if precision == 0 else round(10 ** (-precision), precision)
        used_init_amounts: set[float] = {
            round(other_ad.init_amount, precision)
            for other_ad in (all_asset_ads or [])
            if other_ad.adv_no not in {a.adv_no for a, _ in sorted_pairs} and other_ad.init_amount > 0
        }

        for idx, (ad, decision) in enumerate(sorted_pairs):
            if idx in unfit_indices:
                continue
            final_p = desired_prices[idx]
            orig_p = decision.new_price if decision.new_price > 0 else ad.current_price
            if round(abs(final_p - orig_p), 2) >= config.price_step:
                base_reason = (decision.reason or "stagger").split("+")[0]
                decision.reason = f"{base_reason}+anti_collision"
                if decision.tc_implicito > 0 and orig_p > 0:
                    spot_ratio = decision.tc_implicito / orig_p
                    decision.tc_implicito = round(final_p * spot_ratio, 2)
                    if decision.benchmark_by_method:
                        min_bm = min(decision.benchmark_by_method.values())
                        decision.margin_worst = round(min_bm - decision.tc_implicito, 2)
                logger.info("🛡️ Anti-colisión %s G%d: $%.2f -> $%.2f (buffer: $%.2f)", ad.asset, ad.ad_group, orig_p, final_p, min_buffer)

        n_pairs = len(sorted_pairs)
        passive_hold_indices: set[int] = {
            j for j, (a_j, d_j) in enumerate(sorted_pairs)
            if j not in unfit_indices
            and round(abs(desired_prices[j] - a_j.current_price), 2) >= config.price_step
            and self.should_apply_passive_hold(a_j, d_j, desired_prices[j], config, ts_map, allow_offline=allow_offline)
        }

        for idx, (ad, decision) in enumerate(sorted_pairs):
            if idx in unfit_indices:
                decision.should_update = False
                decision.new_price = ad.current_price
                decision.reason = "band_too_narrow_anti_collision"
                other_active = [desired_prices[j] for j in range(n_pairs) if j != idx and j not in unfit_indices and desired_prices[j] > 0] + fixed_anchor_prices
                out_of_band = (max_allowed > 0 and ad.current_price > max_allowed) or (min_credible > 0 and ad.current_price < min_credible)
                if out_of_band or any(round(abs(ad.current_price - op), 2) < min_buffer for op in other_active):
                    decision.should_pause = True
                    decision.reason = "collision_floor_breach_pause"
                    decision.pause_reason = "colision_con_anuncio_fijo_sin_rango_seguro"
                if ad.init_amount > 0:
                    used_init_amounts.add(round(ad.init_amount, precision))
                continue

            final_p = desired_prices[idx]
            if idx in passive_hold_indices:
                other_finals = [
                    (sorted_pairs[j][0].current_price if j in passive_hold_indices else desired_prices[j])
                    for j in range(n_pairs) if j != idx and j not in unfit_indices
                ] + fixed_anchor_prices
                if all(round(abs(ad.current_price - op), 2) >= min_buffer for op in other_finals):
                    final_p = ad.current_price
                    desired_prices[idx] = final_p
                    decision.reason = "passive_hysteresis_hold"
                else:
                    passive_hold_indices.discard(idx)

            if recompute_fn:
                recompute_fn(ad, decision, final_p, config)

            eff_init = decision.new_init_amount if decision.new_init_amount is not None else ad.init_amount
            if eff_init > 0:
                eff_rounded = round(eff_init, precision)
                avail_bal = float(available_balance)
                max_aff = round((avail_bal / final_p), precision) if (final_p > 0 and avail_bal > 0) else eff_rounded
                while eff_rounded in used_init_amounts:
                    up_cand = round(eff_rounded + step_u, precision)
                    if (avail_bal <= 0 or up_cand <= max_aff) and up_cand not in used_init_amounts:
                        eff_rounded = up_cand
                    elif avail_bal <= 0:
                        eff_rounded = up_cand
                    else:
                        down_cand = round(eff_rounded - step_u, precision)
                        eff_rounded = down_cand if down_cand >= step_u else up_cand
                    if precision == 0:
                        eff_rounded = float(int(eff_rounded))
                    decision.new_init_amount = eff_rounded
                    decision.should_update = True
                    raw_surplus = getattr(ad, "surplus_amount", None)
                    executed = max(ad.init_amount - float(raw_surplus), 0.0) if (raw_surplus is not None and ad.init_amount > 0) else 0.0
                    eff_tradable = max(eff_rounded - executed, 0.0)
                    new_cap = math.floor(eff_tradable * final_p) if (eff_tradable > 0 and final_p > 0) else 0
                    current_max = decision.new_max_trans_amount if decision.new_max_trans_amount is not None else ad.max_trans_amount
                    if current_max and new_cap > 0 and current_max > new_cap:
                        decision.new_max_trans_amount = float(new_cap)
                    elif decision.new_max_trans_amount is None and ad.max_trans_amount:
                        decision.new_max_trans_amount = min(ad.max_trans_amount, float(new_cap) if new_cap > 0 else ad.max_trans_amount)
                    if decision.new_min_trans_amount and decision.new_max_trans_amount and decision.new_min_trans_amount > decision.new_max_trans_amount:
                        decision.new_min_trans_amount = decision.new_max_trans_amount
                used_init_amounts.add(eff_rounded)

        down_moves, up_moves, other_moves = [], [], []
        for ad, decision in sorted_pairs:
            if not decision.should_update:
                continue
            new_p = decision.new_price if decision.new_price > 0 else ad.current_price
            if new_p < ad.current_price - 0.001:
                down_moves.append((ad, decision, new_p))
            elif new_p > ad.current_price + 0.001:
                up_moves.append((ad, decision, new_p))
            else:
                other_moves.append((ad, decision))

        down_moves.sort(key=lambda x: x[2])
        up_moves.sort(key=lambda x: -x[2])
        return [(a, d) for a, d, _ in down_moves] + [(a, d) for a, d, _ in up_moves] + other_moves
