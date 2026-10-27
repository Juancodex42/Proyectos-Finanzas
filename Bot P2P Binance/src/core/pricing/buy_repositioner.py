"""
Reposicionador de compras — el cerebro del bot.
Decide cuándo y cómo mover los precios de cada anuncio de compra en Binance P2P.
"""
import asyncio
import logging
import math
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional

from config.settings import (
    AD_API_ERROR_COOLDOWN_SECONDS,
    ALTCOIN_MIN_MARGIN_PCT,
    ASSET_DEFAULTS,
    ASSET_MIN_PRICE_RATIOS,
    ASSET_PRECISION,
    DEFAULT_MIN_PRICE_RATIO,
    GROUP_ANCHOR_METHODS,
    GROUP_LIMIT_FACTORS,
    GROUP_MIN_MULTIPLIERS,
    LIQUID_REFERENCE_METHODS,
    MIN_AD_PRICE_DIFF_RATIO,
    SELL_LESS_ASSETS,
    SELL_LESS_MAX_MARKUP_PCT,
    STABLECOINS,
)
try:
    from core.ads.manager import AdsManager
except ImportError:
    from core.ads.manager import AdsManager
from core.antiban_validator import AntiBanValidator
from core.fiwind_client import FiwindClient
from core.liquidity.liquidity_manager import LiquidityManager
from core.market_scanner import MarketScanner
from core.pricing.amount_calculator import (
    calculate_volatility_discount_target,
    recompute_buy_amounts_and_limits,
)
from core.pricing.collision_guard import CollisionGuard
from core.pricing.ticket_filter import (
    filter_qualified_competitors,
    filter_viable_competitors,
)
from core.war_detector import WarDetector
from data.database import Database
from data.models import Benchmark, BotConfig, ExchangeRate, MyAd, PriceChange, RepositionDecision

logger = logging.getLogger(__name__)


class BuyRepositioner:
    """
    Lógica principal de reposicionamiento de precios de compra (Buy Ladder).
    Evalúa competidores, benchmarks, márgenes, liquidez y ejecuta órdenes escalonadas.
    """

    @staticmethod
    def get_group_floor_min(asset: str, ad_group: int) -> float:
        """Calcula el piso mínimo en ARS para un grupo según ASSET_DEFAULTS y GROUP_MIN_MULTIPLIERS."""
        defaults = ASSET_DEFAULTS.get(asset, {})
        floor_min = defaults.get("min_trans", 10000.0)
        return round(floor_min * GROUP_MIN_MULTIPLIERS.get(ad_group, 1.0), 0)

    def __init__(
        self,
        ads_manager: AdsManager,
        scanner: MarketScanner,
        liquidity: LiquidityManager,
        war_detector: WarDetector,
        db: Database,
        fiwind_client: Optional[FiwindClient] = None,
        collision_guard: Optional[CollisionGuard] = None,
    ) -> None:
        self.ads = ads_manager
        self.scanner = scanner
        self.liquidity = liquidity
        self.wars = war_detector
        self.db = db
        self.fiwind = fiwind_client or FiwindClient()
        self.collision_guard = collision_guard or CollisionGuard()
        self._paused_by_liquidity: set[str] = set()
        self._paused_by_market_data: set[str] = set()
        self._paused_by_antiban: set[str] = set()
        self._last_update_ts: dict[str, float] = {}
        self._error_cooldown_until: dict[str, float] = {}
        self._last_failed_price: dict[str, float] = {}

    @property
    def _asset_price_bounds(self) -> dict[str, tuple[float, float]]:
        return self.collision_guard._asset_price_bounds

    async def _resolve_benchmark(self, ad: MyAd, benchmarks: dict[str, Benchmark], decision: RepositionDecision) -> float:
        """Determina el benchmark de salida USDT más conservador y líquido."""
        for m in ad.payment_methods:
            if m in benchmarks:
                decision.benchmark_by_method[m] = benchmarks[m].avg_top_n_price

        liquid_bms = [benchmarks[m].avg_top_n_price for m in LIQUID_REFERENCE_METHODS if m in benchmarks and benchmarks[m].avg_top_n_price > 0]
        min_liquid_bm = min(liquid_bms) if liquid_bms else 0.0
        ad_min_bm = min(decision.benchmark_by_method.values()) if decision.benchmark_by_method else 0.0

        if min_liquid_bm > 0 and ad_min_bm > 0:
            return min(min_liquid_bm, ad_min_bm)
        if min_liquid_bm > 0 or ad_min_bm > 0:
            return max(min_liquid_bm, ad_min_bm)

        valid_bms = [b.avg_top_n_price for b in benchmarks.values() if b and b.avg_top_n_price > 0]
        if valid_bms:
            return min(valid_bms)
        try:
            bid = await self.fiwind.get_usdt_bid()
            return bid if bid > 0 else 0.0
        except Exception:
            return 0.0

    def _cut_to_margin_ceiling(
        self, ad: MyAd, decision: RepositionDecision, max_allowed_p: float, max_allowed_tc: float, req_margin: float, config: BotConfig, reason: str
    ) -> None:
        """Ajusta de emergencia un anuncio al techo seguro de margen."""
        decision.should_update = True
        decision.new_price = max_allowed_p
        decision.reason = reason
        decision.tc_implicito = max_allowed_tc
        decision.margin_worst = req_margin
        self._recompute_ad_amounts_and_limits(ad, decision, max_allowed_p, config)

    async def evaluate_ad(
        self,
        ad: MyAd,
        competitors: dict[tuple[str, str], list[ExchangeRate]],
        benchmarks: dict[str, Benchmark],
        spot_prices: dict[str, float],
        config: BotConfig,
        volatilities: Optional[dict[str, float]] = None,
    ) -> RepositionDecision:
        """Evalúa un anuncio de compra y calcula precio objetivo y límites."""
        decision = RepositionDecision()
        spot = spot_prices.get(ad.asset, 0.0)
        if spot <= 0:
            decision.reason, decision.should_pause, decision.pause_reason = "sin_spot_price", True, f"sin_spot_price ({ad.asset})"
            return decision

        min_benchmark = await self._resolve_benchmark(ad, benchmarks, decision)
        if min_benchmark <= 0:
            decision.reason, decision.should_pause, decision.pause_reason = "sin_benchmark", True, "sin_benchmark_valido"
            return decision

        is_stable = ad.asset in STABLECOINS
        spot_factor = 1.0 if ad.asset == "USDT" else spot
        required_margin = config.margin_min if is_stable else max(config.margin_min, min_benchmark * ALTCOIN_MIN_MARGIN_PCT)
        max_allowed_tc = min_benchmark - required_margin
        max_allowed_price = math.floor(max(0.0, max_allowed_tc * spot_factor) * 100) / 100.0

        if is_stable and ad.asset != "USDT":
            usdt_ceil = math.floor(max(0.0, min_benchmark - config.margin_min) * 100) / 100.0
            if max_allowed_price > usdt_ceil:
                max_allowed_price = usdt_ceil

        if ad.asset in SELL_LESS_ASSETS:
            markup_cap = math.floor(max(0.0, spot * min_benchmark * (1.0 + SELL_LESS_MAX_MARKUP_PCT)) * 100) / 100.0
            if max_allowed_price > markup_cap > 0:
                max_allowed_price = markup_cap

        group_floor_min = self.get_group_floor_min(ad.asset, ad.ad_group)
        avail = self.liquidity.available_balance
        fair_spot_ars = spot * (min_benchmark if min_benchmark > 0 else 1590.0)
        floor_ratio = ASSET_MIN_PRICE_RATIOS.get(ad.asset, DEFAULT_MIN_PRICE_RATIO)
        min_credible_price = round(fair_spot_ars * floor_ratio, 2) if fair_spot_ars > 0 else 0.0
        self.collision_guard.set_bounds(ad.asset, min_credible_price, max_allowed_price)

        if avail < group_floor_min:
            decision.should_pause = True
            decision.pause_reason = f"saldo_menor_a_piso_minimo ({avail:,.0f} < {group_floor_min:,.0f} ARS)"
            return decision

        min_factor, _ = GROUP_LIMIT_FACTORS.get(ad.ad_group, (0.50, 0.75))
        target_min = round(max(group_floor_min, avail * min_factor), 0)
        step = max(round(fair_spot_ars * 0.001, 2), config.price_step) if 0 < fair_spot_ars < 50.0 else config.price_step

        if getattr(self.ads, "is_83714_active", False) is True:
            decision.reason, decision.should_update = "error_83714_cooldown", False
            return decision

        now_ts = time.time()
        if now_ts < self._error_cooldown_until.get(ad.adv_no, 0.0):
            last_failed_p = self._last_failed_price.get(ad.adv_no, -1.0)
            if max_allowed_price > 0 and ad.current_price > max_allowed_price and round(abs(max_allowed_price - last_failed_p), 2) >= config.price_step:
                self._cut_to_margin_ceiling(ad, decision, max_allowed_price, max_allowed_tc, required_margin, config, "cooldown+margin_ceiling_cut")
                return decision
            decision.reason, decision.should_update = "api_error_cooldown", False
            return decision

        competitor_prices: dict[str, float] = {}
        all_visible_rates: list[ExchangeRate] = []
        best_comp_overall: Optional[ExchangeRate] = None

        for m in ad.payment_methods:
            rates = competitors.get((ad.asset, m), [])
            if not rates:
                continue
            all_visible_rates.extend([r for r in rates if r.price_ars >= min_credible_price])
            if self.wars.is_in_war(ad.asset, m):
                if max_allowed_price > 0 and ad.current_price > max_allowed_price:
                    self._cut_to_margin_ceiling(ad, decision, max_allowed_price, max_allowed_tc, required_margin, config, "war_detected+margin_ceiling_cut")
                else:
                    decision.reason, decision.should_update = "war_detected", False
                return decision

            qualified = filter_qualified_competitors(rates, target_min=target_min, min_credible_price=min_credible_price)
            best = self.scanner.get_best_competitor(qualified)
            if best:
                if self.wars.check_escalation(ad.asset, m, best, ad.current_price) is True:
                    if max_allowed_price > 0 and ad.current_price > max_allowed_price:
                        self._cut_to_margin_ceiling(ad, decision, max_allowed_price, max_allowed_tc, required_margin, config, "war_detected+margin_ceiling_cut")
                    else:
                        decision.reason, decision.should_update = "war_detected", False
                    return decision
                competitor_prices[m] = best.price_ars
                if best_comp_overall is None or best.price_ars > best_comp_overall.price_ars:
                    best_comp_overall = best

        if competitor_prices:
            anchor_m = GROUP_ANCHOR_METHODS.get(ad.ad_group)
            anchor_p = competitor_prices.get(anchor_m) if anchor_m else None
            if anchor_p and anchor_p > 0:
                usable = [p for p in competitor_prices.values() if p <= anchor_p * 1.01]
                base_comp_p = max(usable) if usable else anchor_p
            else:
                sp = sorted(competitor_prices.values())
                med = sp[len(sp) // 2]
                usable = [p for p in sp if p <= med * 1.015]
                base_comp_p = max(usable) if usable else med

            target_price = round(base_comp_p + step, 2)
            decision.competitor_best_price = base_comp_p
            if best_comp_overall:
                decision.competitor_no = best_comp_overall.advertiser_no
            tc_target = target_price / spot_factor
            decision.tc_implicito = tc_target
            decision.margin_worst = min_benchmark - tc_target

            if decision.margin_worst >= required_margin and min_credible_price <= target_price <= max_allowed_price:
                decision.should_update, decision.new_price = True, target_price
                decision.reason = "reposition_first" if ad.asset not in SELL_LESS_ASSETS else "reposition_sell_less_gap"
            else:
                viable: list[ExchangeRate] = []
                for m in ad.payment_methods:
                    cand = filter_viable_competitors(competitors.get((ad.asset, m), []), target_min, min_credible_price, max_allowed_price)
                    if cand:
                        b_cand = self.scanner.get_best_competitor(cand)
                        if b_cand and min_credible_price <= b_cand.price_ars < max_allowed_price:
                            viable.append(b_cand)
                if viable:
                    best_v = max(viable, key=lambda r: r.price_ars)
                    cand_p = min(round(best_v.price_ars + step, 2), max_allowed_price)
                    decision.should_update, decision.new_price = True, cand_p
                    decision.reason = "reposition_second_best" if cand_p < max_allowed_price else "reposition_max_margin"
                    decision.competitor_best_price = best_v.price_ars
                    decision.competitor_no = best_v.advertiser_no
                    decision.tc_implicito = cand_p / spot_factor
                    decision.margin_worst = min_benchmark - decision.tc_implicito
                elif max_allowed_price >= min_credible_price and max_allowed_price > 0:
                    decision.should_update, decision.new_price = True, max_allowed_price
                    decision.reason = "reposition_max_margin"
                    decision.tc_implicito = max_allowed_tc
                    decision.margin_worst = required_margin
                else:
                    decision.reason = "margin_breach"
        else:
            fb_target, l_price, reason_code = calculate_volatility_discount_target(
                asset=ad.asset, fair_spot_ars=fair_spot_ars, min_credible_price=min_credible_price,
                max_allowed_price=max_allowed_price, step=step, is_stable=is_stable,
                all_visible_rates=all_visible_rates, competitors=competitors, volatilities=volatilities,
            )
            if fb_target >= min_credible_price and fb_target > 0:
                decision.should_update, decision.new_price, decision.reason = True, fb_target, reason_code
                decision.competitor_best_price = l_price
                decision.tc_implicito = fb_target / spot_factor
                decision.margin_worst = min_benchmark - decision.tc_implicito
            else:
                decision.reason, decision.should_update = "sin_precio_valido", False
                return decision

        if decision.reason in ("margin_breach", "sin_spot_price", "sin_benchmark", "sin_precio_valido", "war_detected", "api_error_cooldown"):
            decision.should_update = False
            return decision

        target_p = decision.new_price if (decision.should_update and decision.new_price > 0) else ad.current_price
        self._recompute_ad_amounts_and_limits(ad, decision, target_p, config)
        return decision

    def _recompute_ad_amounts_and_limits(self, ad: MyAd, decision: RepositionDecision, final_price: float, config: BotConfig) -> None:
        """Calcula initAmount escalonado y límites dinámicos exactos para el precio final."""
        group_floor_min = self.get_group_floor_min(ad.asset, ad.ad_group)
        group_floor_g3 = self.get_group_floor_min(ad.asset, 3)
        recompute_buy_amounts_and_limits(
            ad=ad, decision=decision, final_price=final_price, config=config,
            available_balance=self.liquidity.available_balance, group_floor_min=group_floor_min,
            last_update_ts=self._last_update_ts, group_floor_min_g3=group_floor_g3,
        )

    async def execute_repositioning(self, ad: MyAd, decision: RepositionDecision, config: BotConfig, allow_offline: bool = False) -> bool:
        """Ejecuta un reposicionamiento en Binance y persiste los cambios."""
        if not decision.should_update:
            return False
        old_price = ad.current_price
        target_p = decision.new_price if decision.new_price > 0 else old_price
        prec = ASSET_PRECISION.get(ad.asset, 2)
        step_u = 1.0 if prec == 0 else round(10 ** (-prec), prec)
        price_changed = round(abs(target_p - old_price), 2) >= config.price_step
        has_param = (
            (decision.new_init_amount is not None and abs(decision.new_init_amount - ad.init_amount) >= step_u)
            or (decision.new_min_trans_amount is not None and abs(decision.new_min_trans_amount - ad.min_trans_amount) >= 1.0)
            or (decision.new_max_trans_amount is not None and abs(decision.new_max_trans_amount - ad.max_trans_amount) >= 1.0)
        )
        if not price_changed and not has_param:
            decision.should_update = False
            decision.reason = "noop_filtered"
            return True

        executed = max(ad.init_amount - float(ad.surplus_amount), 0.0) if getattr(ad, "surplus_amount", None) is not None and ad.init_amount > 0 else 0.0
        new_surplus = max(round(decision.new_init_amount - executed, prec), 0.0) if decision.new_init_amount is not None else None

        success = await self.ads.update_ad_params(
            adv_no=ad.adv_no, price=target_p if price_changed else None, init_amount=decision.new_init_amount,
            min_trans_amount=decision.new_min_trans_amount, max_trans_amount=decision.new_max_trans_amount, surplus_amount=new_surplus,
        )
        if success:
            now_t = time.time()
            self._last_update_ts[ad.adv_no] = now_t
            self._error_cooldown_until.pop(ad.adv_no, None)
            self._last_failed_price.pop(ad.adv_no, None)
            if price_changed:
                self.db.save_price_change(PriceChange(
                    adv_no=ad.adv_no, asset=ad.asset, ad_group=ad.ad_group, old_price=old_price, new_price=target_p,
                    reason=decision.reason, competitor_best_price=decision.competitor_best_price, competitor_no=decision.competitor_no,
                    tc_implicito=decision.tc_implicito, benchmark_by_method=decision.benchmark_by_method, margin_worst=decision.margin_worst,
                    liquidity_ars=self.liquidity.balance,
                ))
            ad.current_price, ad.last_repositioned = target_p, datetime.now()
            if decision.new_init_amount is not None:
                ad.init_amount = decision.new_init_amount
                if new_surplus is not None:
                    ad.surplus_amount = new_surplus
            if decision.new_min_trans_amount is not None:
                ad.min_trans_amount = decision.new_min_trans_amount
            if decision.new_max_trans_amount is not None:
                ad.max_trans_amount = decision.new_max_trans_amount
            self.db.save_my_ad(ad)
            logger.info("✅ %s G%d actualizado en Binance: $%.2f | (%s)", ad.asset, ad.ad_group, target_p, decision.reason)
        else:
            self._error_cooldown_until[ad.adv_no] = time.time() + AD_API_ERROR_COOLDOWN_SECONDS
            self._last_failed_price[ad.adv_no] = target_p
            logger.warning("🛡️ Circuit-breaker activado para %s G%d tras rechazo de API", ad.asset, ad.ad_group)
        return success

    def resolve_asset_price_collisions(
        self, asset: str, evaluated: list[tuple[MyAd, RepositionDecision]], config: BotConfig,
        all_asset_ads: Optional[list[MyAd]] = None, allow_offline: bool = False,
    ) -> list[tuple[MyAd, RepositionDecision]]:
        """Delega la resolución de colisiones a CollisionGuard."""
        return self.collision_guard.resolve_asset_price_collisions(
            asset=asset, evaluated=evaluated, config=config, all_asset_ads=all_asset_ads,
            allow_offline=allow_offline, last_update_ts=self._last_update_ts,
            available_balance=self.liquidity.available_balance, recompute_fn=self._recompute_ad_amounts_and_limits,
        )

    async def run_cycle(
        self, ads: list[MyAd], competitors: dict[tuple[str, str], list[ExchangeRate]], benchmarks: dict[str, Benchmark],
        spot_prices: dict[str, float], config: BotConfig, allow_offline: bool = False, volatilities: Optional[dict[str, float]] = None,
    ) -> list[tuple[MyAd, RepositionDecision]]:
        """Ejecuta un ciclo completo de evaluación, anti-colisión y ejecución para todos los anuncios de compra."""
        results: list[tuple[MyAd, RepositionDecision]] = []
        evaluated_by_asset: dict[str, list[tuple[MyAd, RepositionDecision]]] = defaultdict(list)
        all_ads_by_asset: dict[str, list[MyAd]] = defaultdict(list)
        resume_cand: set[str] = set()
        initial_pauses: list[tuple[MyAd, RepositionDecision]] = []

        for a in ads:
            all_ads_by_asset[a.asset].append(a)

        for ad in ads:
            if ad.adv_no in config.paused_ads or ad.asset in config.paused_assets:
                continue
            is_paused = (ad.adv_no in self._paused_by_liquidity or ad.adv_no in self._paused_by_market_data or ad.adv_no in self._paused_by_antiban)
            is_resume_cand = False
            if is_paused and ad.status != 1 and ad.adv_no not in config.paused_ads and ad.asset not in config.paused_assets:
                floor_m = self.get_group_floor_min(ad.asset, ad.ad_group)
                min_c = ASSET_DEFAULTS.get(ad.asset, {}).get("init_amount", 0.0)
                spot_v = spot_prices.get(ad.asset, 0.0)
                ref_bm = sum(b.avg_top_n_price for b in benchmarks.values() if b and b.avg_top_n_price > 0) / max(1, len(benchmarks)) if benchmarks else 1600.0
                req_cap = round(min_c * spot_v * ref_bm, 0) if min_c > 0 and spot_v > 0 else floor_m
                if self.liquidity.available_balance >= max(floor_m, req_cap):
                    is_resume_cand = True
                    resume_cand.add(ad.adv_no)

            if not allow_offline and ad.status != 1 and not is_resume_cand:
                continue

            decision = await self.evaluate_ad(ad, competitors, benchmarks, spot_prices, config, volatilities=volatilities)
            if decision.should_pause:
                if ad.status == 1:
                    initial_pauses.append((ad, decision))
                else:
                    self._paused_by_liquidity.add(ad.adv_no)
                if not allow_offline:
                    continue
            evaluated_by_asset[ad.asset].append((ad, decision))

        if initial_pauses:
            online_nos = [a.adv_no for a, _ in initial_pauses if a.status == 1]
            if online_nos:
                await self.ads.pause_ads_batch(online_nos)
                for a, d in initial_pauses:
                    a.status = 3
                    self._paused_by_liquidity.add(a.adv_no)
                    logger.warning("⏸️ %s G%d pausado en batch por falta de saldo: %s", a.asset, a.ad_group, d.pause_reason)

        for asset, asset_pairs in evaluated_by_asset.items():
            to_exec = self.resolve_asset_price_collisions(asset, asset_pairs, config, all_asset_ads=all_ads_by_asset.get(asset, []), allow_offline=allow_offline)
            viols = AntiBanValidator.audit_asset_decisions(asset=asset, ad_decision_pairs=to_exec, spot_price=spot_prices.get(asset, 1.0), price_step=config.price_step)
            if any(v.severity == "CRITICAL" for v in viols):
                logger.error("🚨 Violación crítica Anti-Ban en %s: abortando ejecución de este activo.", asset)
                continue

            aborted, to_resume, deferred = False, [], []
            async def _exec_pair(pair: tuple[MyAd, RepositionDecision]) -> bool:
                a_item, d_item = pair
                if await self.execute_repositioning(a_item, d_item, config, allow_offline=allow_offline):
                    results.append((a_item, d_item))
                    if not allow_offline and not config.is_paused and a_item.status != 1 and a_item.adv_no not in config.paused_ads and a_item.asset not in config.paused_assets:
                        to_resume.append(a_item)
                    await asyncio.sleep(0.65)
                    return True
                return False

            for ad, decision in to_exec:
                target_p = decision.new_price if decision.new_price > 0 else ad.current_price
                t_buf = max(0.16, round(target_p * MIN_AD_PRICE_DIFF_RATIO, 2))
                if any(o.adv_no != ad.adv_no and o.status == 1 and o.current_price > 0 and abs(target_p - o.current_price) < t_buf for o in all_ads_by_asset.get(asset, [])):
                    deferred.append((ad, decision))
                    continue
                if not await _exec_pair((ad, decision)):
                    aborted = True
                    break

            if deferred and not aborted:
                for item in deferred:
                    if not await _exec_pair(item):
                        aborted = True
                        break

            if not aborted:
                for ad in to_resume:
                    try:
                        if await self.ads.resume_ad(ad.adv_no):
                            ad.status = 1
                            self._paused_by_liquidity.discard(ad.adv_no)
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass

            online_pauses = [ad.adv_no for ad, decision in asset_pairs if decision.should_pause and ad.status == 1]
            if online_pauses:
                await self.ads.pause_ads_batch(online_pauses)
            for ad, decision in asset_pairs:
                if decision.should_pause:
                    ad.status = 3
                    self._paused_by_liquidity.add(ad.adv_no)
                elif not decision.should_update and not allow_offline and not config.is_paused and not aborted and ad.adv_no in resume_cand and ad.status != 1:
                    try:
                        if await self.ads.resume_ad(ad.adv_no):
                            ad.status = 1
                            self._paused_by_liquidity.discard(ad.adv_no)
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass

        return results


# Alias canónico
Repositioner = BuyRepositioner
