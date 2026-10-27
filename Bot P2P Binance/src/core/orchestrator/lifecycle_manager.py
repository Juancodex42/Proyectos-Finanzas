"""
Lifecycle and Operational State Management for Bot P2P Binance.
Handles bot ignition, shutdown, ad reconciliations, and bulk deletions.
"""
import time
import asyncio
import logging
from typing import Optional, Any, Union, Dict, List, Set, Tuple

from config.settings import (
    AD_STATUS_ONLINE, AD_STATUS_OFFLINE,
    P2P_ASSETS_ARS, DEFAULT_USDT_BENCHMARK_FALLBACK,
    LIQUID_REFERENCE_METHODS,
)

logger = logging.getLogger("orchestrator.lifecycle")


class LifecycleMixin:
    """Mixin que encapsula el ciclo de vida, apagado, encendido y reconciliación de anuncios."""
    async def turn_off(self) -> dict:
        """Apaga el bot: pausa todos los anuncios en Binance y congela el loop."""
        async with self._get_op_lock():
            logger.info("BotEngine: Apagando bot (pausando anuncios y loop)...")
            self.config = self.db.load_bot_config()
            self.config.is_paused = True
            self._paused_by_watchdog = False
            self._watchdog_pause_confirmed = False
            self.db.save_bot_config(self.config)

            res = await self.ads_manager.pause_all()
            for ad in (getattr(self, "my_ads", None) or []):
                ad.status = AD_STATUS_OFFLINE
            logger.info("BotEngine: Todos los anuncios pausados en Binance. Resultado: %s", res)
            self._notify_state_change()
            return res

    async def _turn_on_internal(self) -> dict:
        """Lógica interna de encendido seguro bajo protección de _op_lock."""
        logger.info("BotEngine: Encendiendo bot de forma segura (Pre-flight Calibration)...")

        # 1. Reconciliar estructura de 42 anuncios y calibrar en frío precios y cantidades
        stats = await self._reconcile_ads_internal(set_online=False, calibrate=True)

        # 2. Poner todos los anuncios ONLINE (ahora que tienen precios óptimos y cantidades calibradas)
        self.config = self.db.load_bot_config()
        auto_paused = (
            getattr(self.repositioner, "_paused_by_liquidity", set())
            | getattr(self.repositioner, "_paused_by_market_data", set())
            | getattr(self.repositioner, "_paused_by_antiban", set())
        )
        online_count = await self.ads_manager.resume_all(
            config=self.config, skip_adv_nos=auto_paused
        )
        stats["total_active"] = online_count
        for ad in (getattr(self, "my_ads", None) or []):
            if (
                ad.adv_no not in self.config.paused_ads
                and ad.asset not in self.config.paused_assets
                and ad.adv_no not in auto_paused
                and ad.init_amount > 0
            ):
                ad.status = AD_STATUS_ONLINE

        # Reactivar anuncios de venta (USDT) si son seguros y tienen saldo
        sell_online_count = 0
        if hasattr(self.ads_manager, "resume_all_sell_ads"):
            try:
                auto_paused_sell = {
                    d.adv_no
                    for d in (getattr(self, "_last_sell_decisions", None) or [])
                    if d.adv_no and (d.should_pause or not d.is_safe)
                }
                paused_sell = (set(self.config.paused_ads) if self.config else set()) | auto_paused_sell
                sell_online_count = await self.ads_manager.resume_all_sell_ads(
                    config=self.config, skip_adv_nos=paused_sell
                )
                stats["sell_active"] = sell_online_count
                for s_ad in (getattr(self, "my_sell_ads", None) or []):
                    if s_ad.adv_no not in paused_sell and s_ad.adv_no:
                        s_ad.status = AD_STATUS_ONLINE
            except Exception as e_s_res:
                logger.error("Error reactivando anuncios de venta en turn_on: %s", e_s_res)

        # 3. Reactivar loop
        self.config.is_paused = False
        self.config.sleep_until = None
        self._paused_by_watchdog = False
        self._watchdog_pause_confirmed = False
        self._watchdog_alerted = False
        self.last_successful_binance_time = time.time()
        self.db.save_bot_config(self.config)
        self._notify_state_change()

        logger.info(
            "🟢 Bot encendido con éxito: %d compras y %d ventas calibradas y puestas ONLINE",
            online_count,
            sell_online_count,
        )
        return stats

    async def turn_on(self) -> dict:
        """
        Enciende el bot con Calibración Previa Segura (Pre-flight Calibration):
        1. Reconcilia estructura de anuncios si falta alguno (permanecen OFFLINE).
        2. Calibra precios y cantidades en frío mientras están OFFLINE.
        3. Solo cuando están 100% calibrados, los pone ONLINE en lotes de 10.
        4. Reactiva el loop de polling.
        """
        if getattr(self, "_op_lock_owner", None) is asyncio.current_task() and asyncio.current_task() is not None:
            return await self._turn_on_internal()
        async with self._get_op_lock():
            self._op_lock_owner = asyncio.current_task()
            try:
                return await self._turn_on_internal()
            finally:
                self._op_lock_owner = None

    async def _reconcile_ads_internal(self, set_online: bool = False, calibrate: bool = True) -> dict:
        """Lógica interna de reconciliación completa de anuncios SIN adquirir _op_lock."""
        pay_id_map = await self.get_pay_id_map()
        initial_spot = await self.spot_client.get_usdt_prices(P2P_ASSETS_ARS)
        usdt_bm = DEFAULT_USDT_BENCHMARK_FALLBACK
        bm_saved = self.db.get_latest_benchmarks()
        if bm_saved:
            liquid_vals = [
                b.avg_top_n_price
                for m, b in bm_saved.items()
                if m in LIQUID_REFERENCE_METHODS and b and b.avg_top_n_price > 0
            ]
            ref_sell = min(liquid_vals) if liquid_vals else min(b.avg_top_n_price for b in bm_saved.values() if b and b.avg_top_n_price > 0)
            margin = self.config.margin_min if self.config else 10.0
            usdt_bm = max(ref_sell - margin, 1000.0)

        stats = await self.ads_manager.reconcile_all_ads(
            method_groups=self.method_groups,
            pay_id_map=pay_id_map,
            spot_prices=initial_spot,
            usdt_benchmark=usdt_bm,
            set_online=set_online,
        )
        self.my_ads = await self.ads_manager.sync_my_ads()
        if self.my_ads and self.method_groups:
            await self.ads_manager.assign_groups(self.my_ads, self.method_groups)
        # 2. Reconciliar y sincronizar anuncios de VENTA USDT (3 clusters)
        free_usdt = 0.0
        try:
            free_usdt = (await self.client.get_funding_asset("USDT")) or 0.0
        except Exception:
            pass

        sell_stats = {}
        if hasattr(self.ads_manager, "reconcile_sell_ads"):
            try:
                res_sell = self.ads_manager.reconcile_sell_ads(
                    pay_id_map=pay_id_map,
                    benchmarks=bm_saved,
                    available_crypto_stock=free_usdt,
                    set_online=set_online,
                )
                if asyncio.iscoroutine(res_sell):
                    sell_stats = await res_sell
                elif isinstance(res_sell, dict):
                    sell_stats = res_sell
            except Exception as e_s:
                logger.debug("Error en reconcile_sell_ads: %s", e_s)

        if hasattr(self.ads_manager, "sync_my_sell_ads"):
            try:
                res_sync = self.ads_manager.sync_my_sell_ads()
                if asyncio.iscoroutine(res_sync):
                    self.my_sell_ads = await res_sync
                elif isinstance(res_sync, list):
                    self.my_sell_ads = res_sync
            except Exception as e_ss:
                logger.debug("Error en sync_my_sell_ads: %s", e_ss)

        my_adv_nos = self.db.get_all_my_adv_nos() | self.db.get_all_my_sell_adv_nos()
        self.scanner.set_my_adv_nos(my_adv_nos)

        if calibrate:
            calibrated_count = await self._calibrate_internal()
            stats["calibrated"] = calibrated_count

        stats["sell_verified"] = sell_stats.get("verified", len(getattr(self, "my_sell_ads", []) or []))
        stats["sell_created"] = sell_stats.get("created", 0)
        stats["sell_calibrated"] = getattr(self, "_last_sell_calibrated_count", 0)
        stats["sell_decisions"] = getattr(self, "_last_sell_decisions", [])
        stats["sell_low_balance"] = sell_stats.get("low_balance", free_usdt < 100.0)
        stats["sell_available_stock"] = sell_stats.get("available_stock", free_usdt)
        stats["sell_min_required"] = sell_stats.get("min_required", 100.0)
        stats["sell_reason"] = sell_stats.get("reason", "")

        return stats

    async def reconcile_ads(self, set_online: bool = False, calibrate: bool = True) -> dict:
        """Ejecuta una reconciliación completa de anuncios en Binance y calibra precios/cantidades."""
        if getattr(self, "_op_lock_owner", None) is asyncio.current_task() and asyncio.current_task() is not None:
            return await self._reconcile_ads_internal(set_online=set_online, calibrate=calibrate)
        async with self._get_op_lock():
            self._op_lock_owner = asyncio.current_task()
            try:
                return await self._reconcile_ads_internal(set_online=set_online, calibrate=calibrate)
            finally:
                self._op_lock_owner = None

    async def delete_all_buy_ads(self) -> dict:
        """Pausa el bot y elimina permanentemente todos los anuncios de COMPRA en Binance."""
        async with self._get_op_lock():
            logger.warning("BotEngine: Eliminando todos los anuncios de COMPRA...")
            # 1. Pausar el bot para congelar el loop de reposicionamiento
            self.config = self.db.load_bot_config()
            self.config.is_paused = True
            self.db.save_bot_config(self.config)

            # 2. Ejecutar eliminación en Binance y BD
            stats = await self.ads_manager.delete_all_buy_ads()

            # 3. Limpiar memoria local
            self.my_ads = []
            all_sell_nos = {a.adv_no for a in getattr(self, "my_sell_ads", [])}
            if hasattr(self, "scanner"):
                self.scanner.set_my_adv_nos(all_sell_nos)

            logger.info("BotEngine: Eliminación de anuncios de compra completada: %s", stats)
            self._notify_state_change()
            return stats

    async def delete_all_sell_ads(self) -> dict:
        """Pausa el bot y elimina permanentemente todos los anuncios de VENTA en Binance."""
        async with self._get_op_lock():
            logger.warning("BotEngine: Eliminando todos los anuncios de VENTA...")
            # 1. Pausar el bot para congelar el loop de reposicionamiento
            self.config = self.db.load_bot_config()
            self.config.is_paused = True
            self.db.save_bot_config(self.config)

            # 2. Ejecutar eliminación en Binance y BD
            stats = await self.ads_manager.delete_all_sell_ads()

            # 3. Limpiar memoria local
            self.my_sell_ads = []
            all_buy_nos = {a.adv_no for a in self.my_ads}
            if hasattr(self, "scanner"):
                self.scanner.set_my_adv_nos(all_buy_nos)

            logger.info("BotEngine: Eliminación de anuncios de venta completada: %s", stats)
            self._notify_state_change()
            return stats

    def request_stop(self):
        """Señaliza parada inmediata del loop principal sin abortar shutdown()."""
        self._running = False
        ev = getattr(self, "shutdown_event", None)
        if ev:
            ev.set()

    async def shutdown(self):
        """Apaga el bot limpiamente."""
        async with self._get_shutdown_lock():
            if getattr(self, "_shutdown_done", False):
                return
            logger.info("Apagando bot...")
            self.request_stop()
            try:
                if hasattr(self, "ads_manager") and hasattr(self, "config") and not self.config.is_paused:
                    logger.info("BotEngine: Pausando anuncios preventivamente antes de apagar...")
                    await self.ads_manager.pause_all()
            except Exception as e_p:
                logger.debug("Error pausando anuncios en shutdown: %s", e_p)
            try:
                await self.telegram.notify("🔴 Bot apagándose...")
            except Exception as e:
                logger.debug("Error notificando apagado en Telegram: %s", e)
            try:
                await self.telegram.stop()
            except Exception as e:
                logger.debug("Error deteniendo Telegram: %s", e)
            try:
                await self.client.close()
            except Exception as e:
                logger.debug("Error cerrando BinanceClient: %s", e)
            try:
                await self.spot_client.close()
            except Exception as e:
                logger.debug("Error cerrando SpotClient: %s", e)
            try:
                await self.fiwind.close()
            except Exception as e:
                logger.debug("Error cerrando FiwindClient: %s", e)
            try:
                self.db.close()
            except Exception as e:
                logger.debug("Error cerrando Database: %s", e)
            self._shutdown_done = True
            logger.info("Bot apagado")


