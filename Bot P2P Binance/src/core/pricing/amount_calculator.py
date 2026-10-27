"""
Calculador de Montos, Remanentes y Límites Dinámicos (Buy Amounts Calculator).

Calcula initAmount escalonado por grupo según Regla 5.1 de Binance (100% G1, 95% G2, 90% G3),
minSingleTransAmount y maxSingleTransAmount garantizando siempre que
initAmount * final_price >= maxSingleTransAmount y evitando actualizaciones fantasma.
"""
import math
import time
from typing import Optional

from config.settings import (
    ASSET_DEFAULTS,
    ASSET_PRECISION,
    GROUP_INIT_MULTIPLIERS,
    GROUP_LIMIT_FACTORS,
    PASSIVE_UPDATE_COOLDOWN_SECONDS,
)
from core.pricing.ticket_filter import (
    calculate_capital_capacity_ars,
    is_stock_capacity_sufficient,
)
from data.models import BotConfig, ExchangeRate, MyAd, RepositionDecision


def recompute_buy_amounts_and_limits(
    ad: MyAd,
    decision: RepositionDecision,
    final_price: float,
    config: BotConfig,
    available_balance: float,
    group_floor_min: float,
    last_update_ts: Optional[dict[str, float]] = None,
    group_floor_min_g3: float = 13000.0,
) -> None:
    """
    Recalcula new_init_amount, new_min_trans_amount y new_max_trans_amount
    garantizando coherencia de capital y detectando cambios relevantes.
    """
    defaults = ASSET_DEFAULTS.get(ad.asset, {"min_trans": 10000.0, "max_trans": 500000.0, "init_amount": 100.0})
    avail = float(available_balance or 0.0)
    min_factor, max_factor = GROUP_LIMIT_FACTORS.get(ad.ad_group, (0.50, 0.75))
    init_mult = GROUP_INIT_MULTIPLIERS.get(ad.ad_group, 1.0)
    prec = ASSET_PRECISION.get(ad.asset, 2)
    min_crypto = defaults.get("init_amount", 0.0)
    ts_map = last_update_ts or {}

    decision.new_init_amount, decision.new_min_trans_amount, decision.new_max_trans_amount = None, None, None

    price_diff = round(abs(final_price - ad.current_price), 2) if final_price > 0 else 0.0
    price_changed = price_diff >= config.price_step
    surplus_crypto = max(float(ad.surplus_amount), 0.0) if getattr(ad, "surplus_amount", None) is not None and ad.init_amount > 0 else ad.init_amount
    executed_crypto = max(ad.init_amount - surplus_crypto, 0.0) if getattr(ad, "surplus_amount", None) is not None and ad.init_amount > 0 else 0.0

    if avail < group_floor_min or final_price <= 0:
        if ad.status == 1 and final_price > 0 and ad.init_amount > 0 and ad.min_trans_amount > 0 and not is_stock_capacity_sufficient(surplus_crypto, final_price, ad.min_trans_amount):
            decision.should_pause = True
            decision.should_update = False
            decision.pause_reason = f"stock_agotado_sin_saldo ({surplus_crypto * final_price:,.0f} < {ad.min_trans_amount:,.0f} ARS)"
            return
        decision.should_update = price_changed and final_price > 0
        decision.new_price = final_price if decision.should_update else ad.current_price
        if not decision.should_update and (not decision.reason or decision.reason.endswith("+anti_collision")):
            decision.reason = "price_unchanged"
        return

    max_aff = avail / final_price
    raw_crypto = (avail * init_mult) / final_price
    step_u = 1.0 if prec == 0 else round(10 ** (-prec), prec)
    min_grp_c = round(min_crypto + (4 - ad.ad_group) * max(step_u, round(min_crypto * 0.015, prec)), prec)
    if prec == 0:
        min_grp_c = float(int(min_grp_c))

    target_amount: Optional[float] = None
    if raw_crypto >= min_grp_c:
        target_amount = round(raw_crypto, prec)
    elif max_aff >= min_grp_c:
        target_amount = min_grp_c
    elif max_aff >= min_crypto:
        target_amount = round(min_crypto if ad.ad_group == 1 else max(min_crypto, raw_crypto), prec)
    if prec == 0 and target_amount is not None:
        target_amount = float(int(target_amount))
    if target_amount is not None:
        target_amount = min(target_amount, round(max_aff, prec))
        if min_crypto > 0 and target_amount < min_crypto:
            target_amount = None

    target_max = round(avail * max_factor, 0)
    eff_crypto = target_amount if target_amount is not None else surplus_crypto
    if eff_crypto > 0:
        target_max = min(target_max, calculate_capital_capacity_ars(eff_crypto, final_price))
    if getattr(ad, "surplus_amount", None) is not None and surplus_crypto > 0 and final_price > 0 and avail < group_floor_min:
        surplus_fiat = calculate_capital_capacity_ars(surplus_crypto, final_price)
        if surplus_fiat < group_floor_min:
            decision.should_pause = True
            decision.should_update = False
            decision.pause_reason = f"stock_agotado_sin_saldo ({surplus_fiat:,.0f} < {group_floor_min:,.0f} ARS)"
            return
        target_max = min(target_max, surplus_fiat)

    if target_max < group_floor_min:
        decision.should_pause = True
        decision.should_update = False
        decision.pause_reason = f"max_menor_a_piso ({target_max:,.0f} < {group_floor_min:,.0f} ARS)"
        return

    target_min_val = min(round(max(group_floor_min, avail * min_factor), 0), target_max)
    if ad.ad_group == 2 and abs(target_min_val - group_floor_min_g3) < 100.0 and target_min_val + 250.0 <= target_max:
        target_min_val = round(target_min_val + 250.0, 0)

    if target_max < target_min_val:
        decision.should_pause = True
        decision.should_update = False
        decision.pause_reason = f"limites_invalidos ({target_max:,.0f} < {target_min_val:,.0f} ARS)"
        return

    integrity_needed = (
        ad.init_amount <= 0 or ad.min_trans_amount <= 0 or ad.max_trans_amount <= 0
        or (ad.init_amount > 0 and ad.max_trans_amount > ad.init_amount * final_price * 1.001)
        or (min_crypto > 0 and 0 < ad.init_amount < min_crypto)
        or (min_crypto > 0 and 0 < surplus_crypto < min_crypto)
        or (ad.init_amount > 0 and surplus_crypto * final_price < group_floor_min)
        or (ad.min_trans_amount > 0 and surplus_crypto * final_price < ad.min_trans_amount)
        or (ad.status != 1 and target_amount is not None and target_amount >= min_crypto)
    )
    sig_amt = target_amount is not None and surplus_crypto > 0 and abs(target_amount - surplus_crypto) / surplus_crypto >= 0.05
    sig_max = ad.max_trans_amount > 0 and abs(target_max - ad.max_trans_amount) / ad.max_trans_amount >= 0.05
    emerg = ad.max_trans_amount > 0 and target_max > 0 and (ad.max_trans_amount > target_max * 1.15 or (avail > 0 and ad.max_trans_amount > avail * 1.05))
    cooldown_ok = ((time.time() - ts_map.get(ad.adv_no, 0.0)) >= PASSIVE_UPDATE_COOLDOWN_SECONDS) or emerg

    if price_changed or integrity_needed or ((sig_amt or sig_max) and cooldown_ok):
        recap = (
            (min_crypto > 0 and 0 < surplus_crypto < min_crypto)
            or (ad.status != 1 and target_amount is not None and target_amount >= min_crypto)
            or (ad.init_amount > 0 and surplus_crypto * final_price < group_floor_min)
            or (ad.min_trans_amount > 0 and surplus_crypto * final_price < ad.min_trans_amount)
        )
        if target_amount is not None and (ad.init_amount <= 0 or abs(target_amount - surplus_crypto) > 0 or recap):
            decision.new_init_amount = round(executed_crypto + target_amount, prec) if executed_crypto > 0 else target_amount
            if prec == 0:
                decision.new_init_amount = float(int(decision.new_init_amount))
        cap = calculate_capital_capacity_ars(eff_crypto, final_price)
        if ad.max_trans_amount <= 0 or abs(target_max - ad.max_trans_amount) >= 100.0 or (ad.max_trans_amount > cap > 0) or recap:
            decision.new_max_trans_amount = target_max
        if ad.min_trans_amount <= 0 or abs(target_min_val - ad.min_trans_amount) >= 100.0 or (ad.min_trans_amount > cap > 0) or recap:
            decision.new_min_trans_amount = target_min_val
        eff_mn = decision.new_min_trans_amount if decision.new_min_trans_amount is not None else ad.min_trans_amount
        eff_mx = decision.new_max_trans_amount if decision.new_max_trans_amount is not None else ad.max_trans_amount
        if eff_mx > 0 and eff_mn > eff_mx:
            decision.new_min_trans_amount = eff_mx

    has_param = (
        (decision.new_init_amount is not None and abs(decision.new_init_amount - ad.init_amount) >= step_u)
        or (decision.new_min_trans_amount is not None and abs(decision.new_min_trans_amount - ad.min_trans_amount) >= 1.0)
        or (decision.new_max_trans_amount is not None and abs(decision.new_max_trans_amount - ad.max_trans_amount) >= 1.0)
    )
    if price_changed:
        decision.should_update = True
        decision.new_price = final_price
    elif has_param:
        decision.should_update = True
        decision.new_price = ad.current_price
        if not decision.reason or decision.reason == "passive_hysteresis_hold":
            decision.reason = "amount_or_limits_sync"
    else:
        decision.should_update = False
        decision.new_price = ad.current_price
        if not decision.reason or decision.reason.endswith("+anti_collision"):
            decision.reason = "price_unchanged"


def calculate_volatility_discount_target(
    asset: str,
    fair_spot_ars: float,
    min_credible_price: float,
    max_allowed_price: float,
    step: float,
    is_stable: bool,
    all_visible_rates: list[ExchangeRate],
    competitors: dict[tuple[str, str], list[ExchangeRate]],
    volatilities: Optional[dict[str, float]] = None,
) -> tuple[float, float, str]:
    """
    Calcula el precio objetivo con descuento por volatilidad ante ausencia de competidores calificados.
    Returns: (fallback_target, lowest_comp_price, reason_code)
    """
    disc = 0.001 if is_stable else min(0.04, max(0.005, (volatilities.get(asset, 0.04) if volatilities else 0.04) * 0.25))
    vp = [r.price_ars for r in all_visible_rates if r.price_ars >= min_credible_price]
    all_rates = [r.price_ars for (ast, _), r_l in competitors.items() if ast == asset for r in r_l if r.price_ars >= min_credible_price]
    if vp:
        l_price = min(vp)
        fb_target = round(l_price - max(step, round(l_price * disc, 2)), 2)
        reason_code = "reposition_last_volatility_discount"
    elif all_rates:
        l_price = min(fair_spot_ars, max(all_rates))
        fb_target = round(l_price - max(step, round(l_price * disc, 2)), 2)
        reason_code = "reposition_market_ref_volatility_discount"
    elif fair_spot_ars > 0:
        l_price = fair_spot_ars
        fb_target = round(l_price - max(step, round(l_price * disc, 2)), 2)
        reason_code = "reposition_fair_spot_volatility_discount"
    else:
        l_price, fb_target, reason_code = 0.0, 0.0, "sin_competidores"

    if min_credible_price > 0:
        fb_target = max(fb_target, min_credible_price)
    fb_target = max(step, min(fb_target, max_allowed_price))
    return fb_target, l_price, reason_code
