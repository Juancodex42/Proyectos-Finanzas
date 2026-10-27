"""
Cycle Execution Engine for Bot P2P Binance.
Coordinates polling intervals, market scans, order processing, and repositioning passes.
"""
import asyncio
import time
import logging
from datetime import datetime
from typing import Optional, Any, Union, Dict, List, Set, Tuple

from config.settings import (
    REGROUP_INTERVAL_HOURS, DEFAULT_POLL_INTERVAL,
    WATCHDOG_TIMEOUT_SECONDS,
)
from telegram_bot.formatters import format_live_dashboard
from .order_processor import OrderProcessor
from .reposition_cycle import RepositionCycle

logger = logging.getLogger("orchestrator.cycle")


class CycleExecutorMixin:
    """Mixin que orquesta la ejecución cíclica del bot."""
    async def run_cycle(self):
        """Ejecuta un ciclo completo de polling y reposicionamiento."""
        if getattr(self, "_op_lock_owner", None) is asyncio.current_task() and asyncio.current_task() is not None:
            return await self._run_cycle_unlocked()
        async with self._get_op_lock():
            self._op_lock_owner = asyncio.current_task()
            try:
                return await self._run_cycle_unlocked()
            finally:
                self._op_lock_owner = None

    async def _run_cycle_unlocked(self):
        """Ejecución interna de un ciclo bajo protección de _op_lock."""
        # Recargar config (puede haber cambiado por Telegram)
        self.config = self.db.load_bot_config()
        initial_cfg_balance = self.config.balance_ars

        # Verificar sleep
        if self.config.sleep_until and isinstance(self.config.sleep_until, datetime):
            if datetime.now() < self.config.sleep_until:
                logger.debug("💤 En sleep hasta %s", self.config.sleep_until)
                return
            else:
                # Sleep expirado → encendido seguro con calibración previa (nunca reactivar con precios viejos)
                logger.info("⏰ Sleep expirado: encendiendo con calibración previa...")
                try:
                    await self.turn_on()
                    self.config = self.db.load_bot_config()
                    initial_cfg_balance = self.config.balance_ars
                    await self.telegram.notify("⏰ Sleep terminado, bot reactivado (calibrado antes de salir online)")
                except Exception as e_wake:
                    logger.error("Fallo al reactivar tras sleep: %s", e_wake, exc_info=True)
                    self.config.is_paused = True
                    self.config.sleep_until = None
                    self.db.save_bot_config(self.config)
                    self._notify_state_change()
                    await self.telegram.notify(
                        f"⚠️ El sleep terminó pero NO se pudo reactivar de forma segura: `{str(e_wake)[:150]}`\n"
                        f"El bot queda en espera. Usá /encender cuando quieras."
                    )
                    return

        if self.config.is_paused:
            logger.debug("🛡️ Bot en Modo Centinela (anuncios pausados / vigilancia activa)")

        if not self.method_groups or not self.assets:
            logger.warning("Sin métodos o activos configurados")
            return

        # ── Determinar volumen vendible real para calibración de benchmarks ──
        max_stock_ars = await self._get_max_stock_ars()

        # ── Escaneo completo ──────────────────────────────────────────
        t_scan_start = time.time()
        try:
            scan_result = await asyncio.wait_for(
                self.scanner.scan_full_cycle(
                    assets=self.assets,
                    method_groups=self.method_groups,
                    volume_ref=self.config.volume_ref,
                    max_stock_ars=max_stock_ars,
                ),
                timeout=45.0,
            )
        except asyncio.TimeoutError:
            elapsed_scan = time.time() - t_scan_start
            if elapsed_scan >= 44.0:
                logger.warning("⏱️ Timeout (45s) en escaneo de mercado. Omitiendo ciclo actual...")
            else:
                logger.warning("⏱️ Timeout de red en escaneo de mercado tras %.1fs. Omitiendo ciclo actual...", elapsed_scan)
            if hasattr(self, "client") and hasattr(self.client, "_reset_session"):
                await self.client._reset_session()
            if hasattr(self, "spot_client") and hasattr(self.spot_client, "_reset_session"):
                await self.spot_client._reset_session()
            return

        # Registro de éxito para el Watchdog (Edge Case 5): solo si P2P respondió con benchmarks reales
        watchdog_just_recovered = False
        if bool(scan_result.get("benchmarks")):
            self.last_successful_binance_time = time.time()
            if self._watchdog_alerted:
                self._watchdog_alerted = False
                if getattr(self, "_paused_by_watchdog", False):
                    self._paused_by_watchdog = False
                    self._watchdog_pause_confirmed = False
                    self.config.is_paused = False
                    self.db.save_bot_config(self.config)
                    self._notify_state_change()
                    watchdog_just_recovered = True
                await self.telegram.notify("🟢 *Conexión con Binance restablecida*\nEl bot continúa operando normalmente.")
        else:
            logger.warning("⚠️ Escaneo sin benchmarks de Binance P2P. No se refresca watchdog.")
            if hasattr(self, "client") and hasattr(self.client, "_reset_session"):
                await self.client._reset_session()

        spot_prices = scan_result["spot_prices"]
        competitors = scan_result["competitors"]
        self.last_benchmarks = scan_result["benchmarks"]

        # ── Sync liquidez (órdenes completadas y en curso - Edge Case 1)
        pre_sync_cfg = self.db.load_bot_config()
        if abs(pre_sync_cfg.balance_ars - initial_cfg_balance) > 0.01:
            logger.info(
                "🔄 Saldo ARS actualizado externamente durante escaneo ($%.0f → $%.0f)",
                initial_cfg_balance, pre_sync_cfg.balance_ars,
            )
            self.liquidity.set_balance(pre_sync_cfg.balance_ars)
            self.liquidity._balance = pre_sync_cfg.balance_ars
            if not isinstance(getattr(type(self.liquidity), "balance", None), property):
                self.liquidity.balance = pre_sync_cfg.balance_ars
            initial_cfg_balance = pre_sync_cfg.balance_ars

        had_liquidity = (self.config.balance_ars > 0)
        pre_sync_cfg = self.config
        try:
            await OrderProcessor.process_orders_and_arbitrage(self, spot_prices, pre_sync_cfg)
        except Exception as e:
            logger.error("Error sincronizando liquidez/órdenes: %s", e)

        is_sentinel_mode = self.config.is_paused or bool(self.config.sleep_until)
        allow_offline = is_sentinel_mode

        # Sincronización periódica con Binance (Edge Case 6: cambios manuales desde la app de Binance)
        if self.cycle_count % 10 == 0:
            try:
                remote_ads = await self.ads_manager.sync_my_ads()
                if remote_ads:
                    self.my_ads = remote_ads
                    if self.method_groups:
                        await self.ads_manager.assign_groups(self.my_ads, self.method_groups)
                remote_sell_ads = await self.ads_manager.sync_my_sell_ads()
                if remote_sell_ads:
                    self.my_sell_ads = remote_sell_ads
                all_my_nos = {a.adv_no for a in self.my_ads} | {a.adv_no for a in getattr(self, "my_sell_ads", [])}
                self.scanner.set_my_adv_nos(all_my_nos)
            except Exception as e_sync:
                logger.debug("Sincronización periódica de anuncios omitida: %s", e_sync)

        # Sincronizar status y parámetros de anuncios en memoria con la base de datos
        db_ads_map = {a.adv_no: a for a in self.db.get_my_ads()}
        for ad in self.my_ads:
            if ad.adv_no in db_ads_map:
                db_ad = db_ads_map[ad.adv_no]
                ad.status = db_ad.status
                ad.surplus_amount = db_ad.surplus_amount
                ad.init_amount = db_ad.init_amount
                ad.min_trans_amount = db_ad.min_trans_amount
                ad.max_trans_amount = db_ad.max_trans_amount
            # Si Binance lo apagó por saldo/agotamiento y no fue pausado manualmente ni estamos en modo centinela, marcar para reactivación
            if not is_sentinel_mode and ad.status != 1 and ad.adv_no not in self.config.paused_ads and ad.asset not in self.config.paused_assets:
                self.repositioner._paused_by_liquidity.add(ad.adv_no)


        shutdown_set = self.shutdown_event.is_set() if self.shutdown_event else False
        await RepositionCycle.execute_buy_repositioning(
            self,
            scan_result=scan_result,
            spot_prices=spot_prices,
            allow_offline=allow_offline,
            shutdown_set=shutdown_set,
            watchdog_just_recovered=watchdog_just_recovered,
        )

        await RepositionCycle.execute_sell_repositioning(
            self,
            scan_result=scan_result,
            spot_prices=spot_prices,
            allow_offline=allow_offline,
            shutdown_set=shutdown_set,
            is_sentinel_mode=is_sentinel_mode,
        )

        # ── Dashboard en vivo en Telegram (un solo mensaje auto-actualizable) ──
        if self.my_ads:
            dashboard_text = format_live_dashboard(
                ads=self.my_ads,
                decisions=self.latest_decisions,
                spot_prices=spot_prices,
                config=self.config,
                balance=self.liquidity.balance,
                available=self.liquidity.available_balance,
                cycle_num=self.cycle_count,
            )
            await self.telegram.update_live_dashboard(dashboard_text)

        # ── Re-agrupamiento periódico ─────────────────────────────────
        hours_since_regroup = (
            datetime.now() - self._last_regroup
        ).total_seconds() / 3600

        if hours_since_regroup >= REGROUP_INTERVAL_HOURS:
            my_adv_nos = self.db.get_all_my_adv_nos() | self.db.get_all_my_sell_adv_nos()
            new_groups = await self.method_selector.regroup_if_needed(
                current_groups=self.method_groups,
                my_adv_nos=my_adv_nos,
            )
            if new_groups:
                self.method_groups = new_groups
                if self.my_ads:
                    await self.ads_manager.assign_groups(self.my_ads, self.method_groups)
                my_adv_nos = self.db.get_all_my_adv_nos() | self.db.get_all_my_sell_adv_nos()
                self.scanner.set_my_adv_nos(my_adv_nos)
                await self.telegram.notify(
                    "🔄 *Re-agrupamiento de métodos sugerido*\n"
                    "Los grupos de métodos se actualizaron."
                )
            self._last_regroup = datetime.now()

