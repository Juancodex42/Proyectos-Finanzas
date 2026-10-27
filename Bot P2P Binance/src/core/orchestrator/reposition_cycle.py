"""
Repositioning Cycle Execution for Bot P2P Binance.
Executes buy ad evaluation, anti-collision rules, anti-ban validations,
and sell cluster pricing with shared inventory replenishment.
"""
import time
import asyncio
import logging
from collections import defaultdict
from typing import Optional, Any, Union, Dict, List, Set, Tuple

from config.settings import (
    AD_STATUS_ONLINE, AD_STATUS_OFFLINE,
    STABLECOINS, ASSET_DEFAULTS,
    GROUP_LIMIT_FACTORS, DEFAULT_BINANCE_SELL_TC_FALLBACK,
)
from core.antiban_validator import AntiBanValidator
from telegram_bot.formatters import (
    format_reposition_notification,
)

logger = logging.getLogger("orchestrator.reposition")


class RepositionCycle:
    """Ejecutor de los bucles de reposicionamiento de compra y venta."""

    @staticmethod
    async def execute_buy_repositioning(
        self: Any,
        scan_result: dict,
        spot_prices: dict[str, float],
        allow_offline: bool,
        shutdown_set: bool,
        watchdog_just_recovered: bool = False,
    ) -> None:
        """Ejecuta el ciclo completo de reposicionamiento de anuncios de COMPRA."""
        is_sentinel_mode = bool(self.config.is_paused or getattr(self.config, "sleep_until", None))
        competitors = scan_result.get("competitors", {})
        # ── Evaluación de Precios y Auditoría Continua Anti-Baneo ──────
        from collections import defaultdict
        evaluated_by_asset = defaultdict(list)
        all_ads_by_asset = defaultdict(list)
        for a in self.my_ads:
            all_ads_by_asset[a.asset].append(a)

        # 1. Evaluar precios óptimos y gestionar pausas/reactivaciones automáticas
        resume_candidates = set()
        online_eval_pause = []
        for ad in self.my_ads:
            if ad.adv_no in self.config.paused_ads or ad.asset in self.config.paused_assets:
                continue

            # Verificar si un anuncio pausado en Binance es elegible para reactivación segura
            is_resume_candidate = False
            is_explicitly_paused = (
                ad.adv_no in self.repositioner._paused_by_liquidity
                or ad.adv_no in getattr(self.repositioner, "_paused_by_market_data", set())
                or ad.adv_no in getattr(self.repositioner, "_paused_by_antiban", set())
            )
            if is_explicitly_paused and ad.status != 1:
                group_floor_min = self.repositioner.get_group_floor_min(ad.asset, ad.ad_group)
                _, max_factor = GROUP_LIMIT_FACTORS.get(ad.ad_group, (0.50, 0.75))
                min_required = round(group_floor_min / max_factor, 0) if max_factor > 0 else group_floor_min
                spot_val = spot_prices.get(ad.asset, 0.0)
                if self.liquidity.available_balance >= min_required and spot_val > 0:
                    is_resume_candidate = True
                    resume_candidates.add(ad.adv_no)

            # Si el anuncio está apagado en Binance y no califica para reactivación, no reposicionar en vivo
            if not allow_offline and ad.status != 1 and not is_resume_candidate:
                continue

            d = await self.repositioner.evaluate_ad(
                ad, competitors, self.last_benchmarks, spot_prices, self.config,
                volatilities=scan_result.get("volatilities", {})
            )

            # Manejo de pausa automática si falta saldo, spot o benchmark
            if d.should_pause:
                self.latest_decisions[ad.adv_no] = d
                if ad.status == 1:
                    online_eval_pause.append((ad, d))
                else:
                    if "saldo" in (d.pause_reason or ""):
                        self.repositioner._paused_by_liquidity.add(ad.adv_no)
                    else:
                        self.repositioner._paused_by_market_data.add(ad.adv_no)
                continue

            evaluated_by_asset[ad.asset].append((ad, d))

        if online_eval_pause:
            to_p_ids = [a.adv_no for a, _ in online_eval_pause]
            if len(to_p_ids) == 1:
                logger.warning("⏸️ Pausando preventivamente en Binance anuncio %s por falta de saldo/spot", to_p_ids[0])
                await self.ads_manager.pause_ad(to_p_ids[0])
            else:
                logger.warning("⏸️ Pausando preventivamente en Binance (batch) %d anuncios por falta de saldo/spot", len(to_p_ids))
                await self.ads_manager.pause_ads_batch(to_p_ids)
            for a, d in online_eval_pause:
                a.status = 3
                if "saldo" in (d.pause_reason or ""):
                    self.repositioner._paused_by_liquidity.add(a.adv_no)
                else:
                    self.repositioner._paused_by_market_data.add(a.adv_no)

        # 2. Resolver colisiones y auditar invariantes con AntiBanValidator por activo
        binance_sell_tc = DEFAULT_BINANCE_SELL_TC_FALLBACK
        if self.last_benchmarks:
            bm_vals = [b.avg_top_n_price for b in self.last_benchmarks.values() if b.avg_top_n_price > 0]
            if bm_vals:
                binance_sell_tc = sum(bm_vals) / len(bm_vals)

        all_cycle_violations = []
        all_to_execute = []
        allow_offline = is_sentinel_mode
        for asset, pairs in evaluated_by_asset.items():
            resolved = self.repositioner.resolve_asset_price_collisions(
                asset=asset,
                evaluated=pairs,
                config=self.config,
                all_asset_ads=all_ads_by_asset.get(asset, []),
                allow_offline=allow_offline,
            )
            col_pause_online = []
            for a_col, d_col in pairs:
                self.latest_decisions[a_col.adv_no] = d_col
                if d_col.should_pause:
                    resume_candidates.discard(a_col.adv_no)
                reason_check = f"{d_col.reason or ''} {d_col.pause_reason or ''}"
                if d_col.should_pause and a_col.status == 1 and (
                    d_col.reason in (
                        "collision_floor_breach_pause",
                        "stock_agotado_sin_saldo",
                        "max_menor_a_piso",
                    )
                    or any(
                        r in reason_check
                        for r in (
                            "collision_floor_breach_pause",
                            "stock_agotado_sin_saldo",
                            "max_menor_a_piso",
                            "monto_menor_a_piso_binance",
                        )
                    )
                ):
                    col_pause_online.append((a_col, d_col, reason_check))
            if col_pause_online:
                if len(col_pause_online) == 1:
                    await self.ads_manager.pause_ad(col_pause_online[0][0].adv_no)
                else:
                    col_ids = [a.adv_no for a, _, _ in col_pause_online]
                    await self.ads_manager.pause_ads_batch(col_ids)
                for a_col, d_col, r_chk in col_pause_online:
                    a_col.status = AD_STATUS_OFFLINE
                    if d_col.reason == "collision_floor_breach_pause" or "collision_floor_breach_pause" in r_chk:
                        self._paused_by_antiban.add(a_col.adv_no)
                    else:
                        self._paused_by_liquidity.add(a_col.adv_no)
            all_to_execute.extend(resolved)
            for a, d in resolved:
                self.latest_decisions[a.adv_no] = d

            spot_usd = spot_prices.get(asset, 1.0)
            viols = AntiBanValidator.audit_asset_decisions(
                asset=asset,
                ad_decision_pairs=resolved,
                spot_price=spot_usd,
                price_step=self.config.price_step,
                fiat_rate=binance_sell_tc,
            )
            all_cycle_violations.extend(viols)

        # 3. Notificación y protección ante discrepancias o violaciones anti-baneo
        critical_violations = [v for v in all_cycle_violations if v.severity == "CRITICAL"]
        critical_assets = {v.asset for v in critical_violations}

        if all_cycle_violations:
            logger.error(
                "🚨 ALERTA ANTI-BANEO: Se detectaron %d violaciones en el ciclo #%d",
                len(all_cycle_violations), self.cycle_count
            )
            for v in all_cycle_violations[:10]:
                logger.warning("   ⚠️ %s", v)
            now_ts = time.time()
            if (now_ts - self._last_antiban_alert_ts) > 300.0:  # Notificar cada 5 min si persiste
                self._last_antiban_alert_ts = now_ts
                viol_lines = [f"• *{v.asset} G{v.group}*: {v.message}" for v in all_cycle_violations[:5]]
                mode_str = "Anuncios Apagados (Modo Centinela)" if is_sentinel_mode else "Anuncios Operando en Vivo"
                await self.telegram.notify(
                    f"🚨 *CUIDADO: ALERTA DE REGLA ANTI-BANEO*\n\n"
                    f"Estado: *{mode_str}*\n"
                    f"Se detectaron discrepancias que violan normativas de Binance:\n"
                    f"{chr(10).join(viol_lines)}\n\n"
                    f"🛡️ Anuncios conflictivos pausados preventivamente en Binance."
                )

            # Pausar en Binance los anuncios activos de activos que presentan violaciones críticas en batch
            if critical_assets:
                crit_ids = [
                    ad.adv_no for ad in self.my_ads
                    if ad.asset in critical_assets and ad.status == 1
                ]
                if crit_ids:
                    if len(crit_ids) == 1:
                        logger.warning("🛡️ Pausando preventivamente en Binance anuncio %s por violación crítica", crit_ids[0])
                        await self.ads_manager.pause_ad(crit_ids[0])
                    else:
                        logger.warning("🛡️ Pausando preventivamente en Binance (batch) %d anuncios por violación crítica", len(crit_ids))
                        await self.ads_manager.pause_ads_batch(crit_ids)
                    for ad in self.my_ads:
                        if ad.adv_no in crit_ids:
                            ad.status = 3
                            self.repositioner._paused_by_antiban.add(ad.adv_no)

        # 4. Ejecución en Binance (Tanto en Vivo como con Anuncios Apagados / Modo Centinela)
        # Excluir de la ejecución cualquier activo con violaciones críticas
        safe_to_execute = [
            (ad, decision) for ad, decision in all_to_execute
            if ad.asset not in critical_assets
        ]

        if getattr(self.ads_manager, "is_83714_active", False) is True:
            logger.warning("🚫 Circuit-breaker 83714 activo: cuenta con restricción temporal en Binance. Omitiendo actualizaciones en este ciclo.")
        elif self.config.is_paused:
            logger.info("⏸️ Modo Standby / Pausa: escaneo y dashboard completados (sin cambios en Binance hasta encender).")
        else:
            shutdown_set = self.shutdown_event.is_set() if self.shutdown_event is not None else False
            from collections import defaultdict
            to_execute_by_asset = defaultdict(list)
            for ad, decision in safe_to_execute:
                to_execute_by_asset[ad.asset].append((ad, decision))

            failed_assets = set()
            for asset, asset_ad_pairs in to_execute_by_asset.items():
                if shutdown_set:
                    logger.info("Ciclo interrumpido: evento de shutdown detectado.")
                    break

                for ad, decision in asset_ad_pairs:
                    if shutdown_set:
                        break
                    if not decision.should_update:
                        continue
                    success = await self.repositioner.execute_repositioning(
                        ad, decision, self.config, allow_offline=allow_offline
                    )
                    if not success:
                        failed_assets.add(asset)
                        logger.warning("⚠️ Falló actualización de %s G%d en Binance", ad.asset, ad.ad_group)
                        await self.telegram.notify(
                            f"⚠️ *Alerta en Binance*\n"
                            f"No se pudo actualizar el anuncio *{ad.asset} G{ad.ad_group}* (`{ad.adv_no}`).\n"
                            f"Binance rechazó la modificación. Cooldown activado para este anuncio."
                        )
                        # Blindaje de seguridad: si falló la actualización y sus límites actuales superan la liquidez disponible,
                        # pausar preventivamente este anuncio para no dejarlo operando al descubierto.
                        avail_now = self.liquidity.available_balance
                        if ad.status == 1 and (ad.max_trans_amount > avail_now * 1.05 or ad.max_trans_amount <= 0):
                            logger.critical(
                                "🛡️ Pausando preventivamente %s G%d (%s): límites desactualizados ($%.0f) superan el saldo disponible ($%.0f)",
                                ad.asset, ad.ad_group, ad.adv_no, ad.max_trans_amount, avail_now
                            )
                            await self.ads_manager.pause_ad(ad.adv_no)
                            ad.status = 3
                            self.repositioner._paused_by_liquidity.add(ad.adv_no)

                        # Aislamiento por activo: omitir el resto de los anuncios de ESTE MISMO ACTIVO para evitar colisiones 187055,
                        # pero CONTINUAR con los demás activos (USDC, BTC, etc.)
                        break
                    await asyncio.sleep(0.65)

            # Reactivación segura de anuncios en Binance que recuperaron saldo/condiciones
            if not allow_offline and not self.config.is_paused and not shutdown_set:
                if watchdog_just_recovered:
                    try:
                        auto_paused = (
                            getattr(self.repositioner, "_paused_by_liquidity", set())
                            | getattr(self.repositioner, "_paused_by_market_data", set())
                            | getattr(self.repositioner, "_paused_by_antiban", set())
                        )
                        await self.ads_manager.resume_all(
                            config=self.config, skip_adv_nos=auto_paused
                        )
                        logger.info("▶️ Anuncios reactivados tras recuperación de Watchdog y calibración de ciclo.")
                    except Exception as e_wd_res:
                        logger.warning("No se pudieron reactivar todos los anuncios tras Watchdog: %s", e_wd_res)
                for ad in self.my_ads:
                    if (
                        ad.adv_no in resume_candidates
                        and ad.status != 1
                        and ad.asset not in critical_assets
                        and ad.asset not in failed_assets
                    ):
                        try:
                            resumed = await self.ads_manager.resume_ad(ad.adv_no)
                            if resumed:
                                ad.status = 1
                                self.repositioner._paused_by_liquidity.discard(ad.adv_no)
                                self.repositioner._paused_by_market_data.discard(ad.adv_no)
                                self.repositioner._paused_by_antiban.discard(ad.adv_no)
                                logger.info(
                                    "▶️ %s G%d reactivado exitosamente en Binance tras validar solvencia y ausencia de colisiones",
                                    ad.asset, ad.ad_group,
                                )
                            await asyncio.sleep(0.5)
                        except Exception as e_res:
                            logger.debug("No se pudo reactivar %s G%d: %s", ad.asset, ad.ad_group, e_res)



    @staticmethod
    async def execute_sell_repositioning(
        self: Any,
        scan_result: dict,
        spot_prices: dict[str, float],
        allow_offline: bool,
        shutdown_set: bool,
        is_sentinel_mode: bool = False,
    ) -> None:
        """Ejecuta el ciclo de reposicionamiento y recarga de anuncios de VENTA."""
        is_sentinel_mode = bool(is_sentinel_mode or self.config.is_paused or getattr(self.config, "sleep_until", None))
        # ── 5. Ciclo Automático de Ventas P2P (Shared Inventory & Anti-Colisión) ──
        if (
            not is_sentinel_mode
            and not self.config.is_paused
            and not shutdown_set
            and getattr(self.ads_manager, "is_83714_active", False) is not True
            and not getattr(self, "is_fiwind_arbitrage_hold", False)
            and self.last_benchmarks
            and hasattr(self, "sell_repositioner")
        ):
            try:
                available_crypto = getattr(self, "_last_free_usdt", None)
                if available_crypto is not None and available_crypto > 0:
                    sell_decisions = await self.sell_repositioner.evaluate_sell_clusters(
                        benchmarks=self.last_benchmarks,
                        available_crypto_stock=available_crypto,
                        config=self.config,
                    )
                else:
                    sell_decisions = await self.sell_repositioner.evaluate_sell_clusters(
                        benchmarks=self.last_benchmarks,
                        config=self.config,
                    )
                to_execute_sell = [
                    d for d in sell_decisions
                    if (d.should_update or d.should_pause) and d.adv_no
                ]
                if to_execute_sell:
                    sell_results = await self.sell_repositioner.execute_sell_decisions(to_execute_sell, config=self.config)
                    updated_sells = [d for d, ok in sell_results if ok and not d.should_pause]
                    if updated_sells:
                        logger.info(
                            "⚡ Ventas automáticas actualizadas en ciclo %d: %s",
                            self.cycle_count,
                            ", ".join(f"G{d.cluster_id}: ${d.suggested_price:,.2f}" for d in updated_sells),
                        )

                # Recarga en caliente permanente: si algún cluster de venta quedó sin anuncio o agotado (< 10 USDT)
                # y hay saldo fresco en Fondos, reconciliar automáticamente (recarga en caliente sin cerrar
                # para preservar configuraciones y casillas de seguridad Web/App como escaneo facial).
                has_depleted = any(not d.adv_no or (d.should_pause and "saldo_menor_a_piso" in (d.pause_reason or "")) for d in sell_decisions)
                if has_depleted and available_crypto and available_crypto >= 10.0 and hasattr(self.ads_manager, "reconcile_sell_ads"):
                    pay_map = await self.get_pay_id_map()
                    await self.ads_manager.reconcile_sell_ads(
                        pay_id_map=pay_map,
                        benchmarks=self.last_benchmarks,
                        available_crypto_stock=available_crypto,
                        set_online=False,
                    )
                    self.my_sell_ads = await self.ads_manager.sync_my_sell_ads()
            except Exception as e_sell_cycle:
                logger.error("Error en ciclo automático de ventas: %s", e_sell_cycle)


