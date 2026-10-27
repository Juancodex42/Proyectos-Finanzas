"""
Calibration and Market Audit Module for Bot P2P Binance.
Handles offline calibration of ads and dry-run anti-ban market simulation audits.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, Any, Union, Dict, List, Set, Tuple

from config.settings import (
    AD_STATUS_ONLINE, AD_STATUS_OFFLINE,
    P2P_ASSETS_ARS, ASSET_DEFAULTS,
)
from data.models import BotConfig, Benchmark, RepositionDecision
from core.antiban_validator import AntiBanValidator

logger = logging.getLogger("orchestrator.calibrator")


class CalibratorMixin:
    """Mixin para calibración en frío y auditoría de mercado simulada."""
    async def _calibrate_internal(self) -> int:
        """
        Lógica interna de calibración SIN adquirir _op_lock.
        Llamada por calibrate_all_ads() (que adquiere el lock) y por turn_on() (que ya lo tiene).
        """
        logger.info("🎯 Iniciando calibración de anuncios en frío (Pre-flight Calibration)...")
        if not self.method_groups or not self.assets:
            logger.warning("Sin métodos o activos configurados para calibración")
            return 0

        # 1. Escaneo completo de mercado (precios spot, benchmarks, libros)
        max_stock_ars = await self._get_max_stock_ars()
        scan_result = await self.scanner.scan_full_cycle(
            assets=self.assets,
            method_groups=self.method_groups,
            volume_ref=self.config.volume_ref,
            max_stock_ars=max_stock_ars,
        )

        spot_prices = scan_result["spot_prices"]
        benchmarks = scan_result["benchmarks"]
        competitors = scan_result["competitors"]
        volatilities = scan_result.get("volatilities", {})
        self.last_benchmarks = benchmarks

        # 2. Sincronizar anuncios locales si es necesario
        if not self.my_ads:
            self.my_ads = self.db.get_my_ads()

        if hasattr(self.repositioner, "_paused_by_liquidity"):
            self.repositioner._paused_by_liquidity.clear()
        if hasattr(self.repositioner, "_paused_by_market_data"):
            self.repositioner._paused_by_market_data.clear()

        # 3. Reposicionar en frío (allow_offline=True)
        results = await self.repositioner.run_cycle(
            ads=self.my_ads,
            competitors=competitors,
            benchmarks=benchmarks,
            spot_prices=spot_prices,
            config=self.config,
            allow_offline=True,
            volatilities=volatilities,
        )

        updated_adv_nos = set()
        for item in (results or []):
            if isinstance(item, tuple) and len(item) == 2:
                ad, decision = item
                updated_adv_nos.add(ad.adv_no)
                if isinstance(decision, RepositionDecision):
                    self.latest_decisions[ad.adv_no] = decision
                    if decision.should_pause:
                        reason_l = (decision.pause_reason or "").lower()
                        if "saldo" in reason_l or "capital" in reason_l:
                            self.repositioner._paused_by_liquidity.add(ad.adv_no)
                        else:
                            self.repositioner._paused_by_market_data.add(ad.adv_no)

        # Registrar en _paused_by_liquidity o _paused_by_market_data anuncios donde decision.should_pause sea True
        for ad in self.my_ads:
            if ad.adv_no in self.config.paused_ads or ad.asset in self.config.paused_assets:
                continue
            if ad.adv_no in updated_adv_nos:
                continue
            try:
                decision = await self.repositioner.evaluate_ad(
                    ad, competitors, benchmarks, spot_prices, self.config, volatilities=volatilities
                )
                if isinstance(decision, RepositionDecision):
                    self.latest_decisions[ad.adv_no] = decision
                    if decision.should_pause:
                        reason_l = (decision.pause_reason or "").lower()
                        if "saldo" in reason_l or "capital" in reason_l:
                            self.repositioner._paused_by_liquidity.add(ad.adv_no)
                            self.repositioner._paused_by_market_data.discard(ad.adv_no)
                        else:
                            self.repositioner._paused_by_market_data.add(ad.adv_no)
                            self.repositioner._paused_by_liquidity.discard(ad.adv_no)
            except Exception as e_cal_eval:
                logger.debug("Error evaluando estado de pausa en calibración para %s: %s", ad.adv_no, e_cal_eval)

        # 4. Calibración en frío de Ventas (SELL)
        sell_calibrated_count = 0
        sell_decisions = []
        if hasattr(self, "sell_repositioner") and self.sell_repositioner:
            try:
                available_crypto = getattr(self, "_last_free_usdt", None)
                if available_crypto is None or available_crypto <= 0:
                    available_crypto = 350.0  # valor de referencia para cotización
                sell_decisions = await self.sell_repositioner.evaluate_sell_clusters(
                    benchmarks=benchmarks,
                    available_crypto_stock=available_crypto,
                    config=self.config,
                )
                self._last_sell_decisions = sell_decisions
                to_exec_sell = [
                    d for d in sell_decisions
                    if d.is_safe and d.adv_no and (d.should_update or not d.should_pause)
                ]
                if to_exec_sell:
                    sell_results = await self.sell_repositioner.execute_sell_decisions(
                        to_exec_sell, config=self.config, allow_offline=True
                    )
                    sell_calibrated_count = len([d for d, ok in sell_results if ok])
                    logger.info("🎯 Ventas calibradas en frío en Binance: %d anuncios actualizados", sell_calibrated_count)
            except Exception as e_cal_sell:
                logger.warning("Error en calibración en frío de ventas: %s", e_cal_sell)

        self._last_sell_calibrated_count = sell_calibrated_count

        logger.info("🎯 Calibración completada: %d anuncios de compra y %d de venta actualizados en frío", len(results), sell_calibrated_count)
        return len(results)

    async def calibrate_all_ads(self) -> int:
        """
        Calibra los precios y cantidades de cripto de TODOS los anuncios en frío (OFFLINE).
        Se ejecuta bajo demanda (/calibrar). Adquiere _op_lock para evitar concurrencia.
        NOTA: turn_on() llama a _calibrate_internal() directamente porque ya tiene el lock.
        """
        if getattr(self, "_op_lock_owner", None) is asyncio.current_task() and asyncio.current_task() is not None:
            return await self._calibrate_internal()
        async with self._get_op_lock():
            self._op_lock_owner = asyncio.current_task()
            try:
                return await self._calibrate_internal()
            finally:
                self._op_lock_owner = None

    async def audit_market_dry_run(self) -> dict:
        """
        Ejecuta una simulación completa de mercado (dry-run) y audita todas las reglas anti-baneo
        usando AntiBanValidator.
        NO realiza ninguna llamada de modificación a la API de Binance (0 llamadas emitidas).
        """
        import copy
        async with self._get_op_lock():
            logger.info("🛡️ Iniciando simulación y auditoría anti-baneo (Dry-Run)...")
            if not self.method_groups or not self.assets:
                return {"error": "Sin métodos o activos configurados", "passed": False}

            # 1. Escaneo completo de mercado
            max_stock_ars = await self._get_max_stock_ars()
            scan_result = await self.scanner.scan_full_cycle(
                assets=self.assets,
                method_groups=self.method_groups,
                volume_ref=self.config.volume_ref,
                max_stock_ars=max_stock_ars,
            )
            spot_prices = scan_result.get("spot_prices", {})
            benchmarks = scan_result.get("benchmarks", {})
            competitors = scan_result.get("competitors", {})
            volatilities = scan_result.get("volatilities", {})

            # 2. Sincronizar anuncios locales
            ads = self.my_ads if self.my_ads else self.db.get_my_ads()
            if not ads:
                return {"error": "No se encontraron anuncios configurados en BD", "passed": False}

            from collections import defaultdict
            evaluated_by_asset = defaultdict(list)
            all_ads_by_asset = defaultdict(list)
            for a in ads:
                all_ads_by_asset[a.asset].append(a)

            saved_paused_liq = set(getattr(self.repositioner, "_paused_by_liquidity", set()))
            saved_paused_mkt = set(getattr(self.repositioner, "_paused_by_market_data", set()))
            saved_paused_ab = set(getattr(self.repositioner, "_paused_by_antiban", set()))
            saved_war_trackers = (
                copy.deepcopy(self.war_detector._trackers)
                if hasattr(self, "war_detector") and hasattr(self.war_detector, "_trackers")
                else None
            )

            try:
                # 3. Evaluar cada anuncio individualmente
                for ad in ads:
                    d = await self.repositioner.evaluate_ad(
                        ad, competitors, benchmarks, spot_prices, self.config, volatilities=volatilities
                    )
                    evaluated_by_asset[ad.asset].append((ad, d))

                # 4. Resolver colisiones y auditar invariantes con AntiBanValidator por activo
                all_violations = []
                asset_summaries = []

                ref_fiat_rate = 0.0
                if "USDT" in benchmarks and getattr(benchmarks["USDT"], "benchmark_price", 0.0) > 0:
                    ref_fiat_rate = benchmarks["USDT"].benchmark_price
                elif "USDT" in benchmarks and getattr(benchmarks["USDT"], "avg_top_n_price", 0.0) > 0:
                    ref_fiat_rate = benchmarks["USDT"].avg_top_n_price
                elif benchmarks:
                    bm_vals = [
                        float(getattr(b, "avg_top_n_price", 0.0) or getattr(b, "benchmark_price", 0.0) or 0.0)
                        for b in benchmarks.values()
                        if b is not None
                    ]
                    bm_vals = [v for v in bm_vals if v > 0]
                    if bm_vals:
                        ref_fiat_rate = sum(bm_vals) / len(bm_vals)

                for asset, pairs in evaluated_by_asset.items():
                    resolved = self.repositioner.resolve_asset_price_collisions(
                        asset=asset,
                        evaluated=pairs,
                        config=self.config,
                        all_asset_ads=all_ads_by_asset.get(asset, []),
                        allow_offline=True,
                    )
                    resolved_map = {a.adv_no: d for a, d in resolved}
                    final_pairs = []
                    for a, d in pairs:
                        final_dec = resolved_map.get(a.adv_no, d)
                        final_pairs.append((a, final_dec))

                    spot_p = spot_prices.get(asset, 1.0)
                    asset_viols = AntiBanValidator.audit_asset_decisions(
                        asset=asset,
                        ad_decision_pairs=final_pairs,
                        spot_price=spot_p,
                        price_step=self.config.price_step,
                        fiat_rate=ref_fiat_rate,
                    )
                    all_violations.extend(asset_viols)

                    group_data = []
                    for a, d in sorted(final_pairs, key=lambda x: x[0].ad_group):
                        target_p = d.new_price if d.new_price > 0 else a.current_price
                        init_a = d.new_init_amount if d.new_init_amount is not None else a.init_amount
                        min_l = d.new_min_trans_amount if d.new_min_trans_amount is not None else a.min_trans_amount
                        max_l = d.new_max_trans_amount if d.new_max_trans_amount is not None else a.max_trans_amount
                        group_data.append({
                            "group": a.ad_group,
                            "current_price": a.current_price,
                            "simulated_price": target_p,
                            "init_amount": init_a,
                            "min_limit": min_l,
                            "max_limit": max_l,
                            "reason": d.reason,
                            "should_pause": d.should_pause,
                            "pause_reason": d.pause_reason,
                        })

                    asset_summaries.append({
                        "asset": asset,
                        "spot_price": spot_p,
                        "groups": group_data,
                        "violations": asset_viols,
                    })

                return {
                    "passed": len(all_violations) == 0,
                    "total_ads": len(ads),
                    "audited_assets": len(evaluated_by_asset),
                    "asset_summaries": asset_summaries,
                    "violations": all_violations,
                    "timestamp": datetime.now(),
                }
            finally:
                self.repositioner._paused_by_liquidity = saved_paused_liq
                self.repositioner._paused_by_market_data = saved_paused_mkt
                self.repositioner._paused_by_antiban = saved_paused_ab
                if saved_war_trackers is not None:
                    self.war_detector._trackers = saved_war_trackers

