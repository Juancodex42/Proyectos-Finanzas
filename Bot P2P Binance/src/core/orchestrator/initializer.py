"""
Bot Initialization and Configuration Loading Module for Bot P2P Binance.
Handles bootstrap sequence, asset discovery, group inference, and payment ID mappings.
"""
import time
import asyncio
import logging
from datetime import datetime
from typing import Optional, Any, Union, Dict, List, Set, Tuple

from config.settings import (
    REGROUP_INTERVAL_HOURS, P2P_ASSETS_ARS,
    GROUP_LIMIT_FACTORS, PAYMENT_METHOD_GROUPS,
    LIQUID_REFERENCE_METHODS, DEFAULT_USDT_BENCHMARK_FALLBACK,
)

logger = logging.getLogger("orchestrator.initializer")


class InitializerMixin:
    """Mixin para inicialización de base de datos, multiactivos, anuncios y métodos."""
    async def initialize(self):
        """Inicialización: DB, sync de anuncios, selección de métodos y multiactivos."""
        logger.info("═" * 60)
        logger.info("  Bot P2P Binance ARS — Inicializando...")
        logger.info("═" * 60)

        # 0. Validar credenciales y sincronizar reloj con Binance
        self.client.validate_credentials()
        await self.client.sync_time()

        # 1. Inicializar DB
        self.db.init_schema()
        try:
            self.db.purge_by_retention()
        except Exception as e:
            logger.warning("No se pudo ejecutar purga inicial de BD: %s", e)
        self.config = self.db.load_bot_config()
        # Siempre arrancar en modo STANDBY (espera): el usuario lo enciende desde Telegram
        self.config.is_paused = True
        self.config.sleep_until = None
        self.db.save_bot_config(self.config)
        self._notify_state_change()
        logger.info("⏸️ Bot iniciado en modo ESPERA (Standby). Esperando activación desde Telegram.")
        logger.info("Config cargada: margen=%s, step=%s, interval=%s",
                     self.config.margin_min, self.config.price_step,
                     self.config.poll_interval)

        # 2. Inicializar liquidez
        await self.liquidity.initialize(self.config)

        # 3. Obtener métodos de pago del usuario y sus IDs
        methods_raw = await self.method_selector.get_available_methods()
        pay_id_map: dict[str, int] = {}
        for m in methods_raw:
            ident = (
                m.get("tradeMethodIdentifier")
                or m.get("identifier")
                or m.get("payType")
                or (m.get("tradeMethod", {}).get("identifier") if isinstance(m.get("tradeMethod"), dict) else "")
            )
            if ident:
                pay_id_map[ident] = int(m.get("id", m.get("payId", 0)))
        self.pay_id_map = pay_id_map

        # Sincronizar anuncios existentes de COMPRA
        self.my_ads = await self.ads_manager.sync_my_ads()

        # Sincronizar anuncios existentes de VENTA
        try:
            self.my_sell_ads = await self.ads_manager.sync_my_sell_ads()
        except Exception as e_sell:
            logger.debug("No se pudieron sincronizar anuncios de venta en inicio: %s", e_sell)
            self.my_sell_ads = []

        my_adv_nos = self.db.get_all_my_adv_nos() | self.db.get_all_my_sell_adv_nos()
        self.scanner.set_my_adv_nos(my_adv_nos)

        # 4. Configurar los 3 grupos oficiales de métodos de pago (5 métodos cada uno)
        self.method_groups = {g: list(m) for g, m in PAYMENT_METHOD_GROUPS.items()}
        logger.info(
            "Grupos oficiales configurados (15 métodos, 5 por grupo): %s",
            {g: len(m) for g, m in self.method_groups.items()},
        )

        # 5. Multiactivos: Asegurar catálogo completo de 14 activos P2P en ARS
        logger.info("Verificando existencia de anuncios para los 14 activos habilitados...")
        try:
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

            await self.ads_manager.reconcile_all_ads(
                method_groups=self.method_groups,
                pay_id_map=pay_id_map,
                spot_prices=initial_spot,
                usdt_benchmark=usdt_bm,
                set_online=False,
                create_missing=True,
            )
            self.my_ads = await self.ads_manager.sync_my_ads()
        except Exception as e:
            logger.error("Error en reconciliación inicial de anuncios: %s", e)

        self.assets = list(P2P_ASSETS_ARS)
        logger.info("Activos configurados (%d): %s", len(self.assets), self.assets)

        self._last_regroup = datetime.now()
        self.last_successful_binance_time = time.time()

        # 6. Asignar grupos a anuncios y actualizar scanner
        if self.my_ads and self.method_groups:
            await self.ads_manager.assign_groups(self.my_ads, self.method_groups)
        my_adv_nos = self.db.get_all_my_adv_nos() | self.db.get_all_my_sell_adv_nos()
        self.scanner.set_my_adv_nos(my_adv_nos)

        # 7. Iniciar Telegram
        await self.telegram.start()
        await self.telegram.send_message(
            f"🛡️ *Bot P2P Binance ARS — INICIADO EN MODO CENTINELA*\n\n"
            f"• Anuncios: 🔴 OFFLINE en Binance (Nadie puede comprarte, 0 riesgo).\n"
            f"• Auditoría Anti-Baneo: 🟢 ACTIVA en segundo plano.\n"
            f"• Activos monitoreados: {len(self.assets)} criptos ({len(self.my_ads)} anuncios).\n"
            f"• Balance asignado: ${self.config.balance_ars:,.0f} ARS\n\n"
            f"👁️ *El bot ya está vigilando el mercado y auditando las 6 reglas en cada ciclo.*\n"
            f"Si alguna regla se incumple ante movimientos del mercado, recibirás una ALERTA inmediata aquí.\n\n"
            f"▶️ Cuando decidas comenzar a comprar, simplemente tocá: *🟢 Encender Bot*.",
            reply_markup=self.telegram.get_inline_panel(),
        )

        logger.info("✅ Inicialización completa (Modo Centinela Activo)")

    def _infer_groups_from_ads(self):
        """Infiere los grupos de métodos a partir de los anuncios existentes."""
        group_methods: dict[int, set[str]] = {}
        for i, ad in enumerate(self.my_ads):
            group_num = (i % 3) + 1  # Distribuir en 3 grupos
            if group_num not in group_methods:
                group_methods[group_num] = set()
            group_methods[group_num].update(ad.payment_methods)
            ad.ad_group = group_num

        self.method_groups = {
            g: list(methods) for g, methods in group_methods.items()
        }
        logger.info("Grupos inferidos: %s",
                     {g: len(m) for g, m in self.method_groups.items()})
    async def _get_max_stock_ars(self) -> Optional[float]:
        """
        Calcula el volumen operativo total para el benchmark de mercado:
        Total que tengo para comprar (saldo ARS disponible) + Total que tengo para venta (USDT libre en Fondos * TC).
        """
        try:
            # 1. Total disponible para compras en ARS
            buy_power = 0.0
            if hasattr(self, "liquidity") and self.liquidity:
                buy_power = float(getattr(self.liquidity, "available_balance", 0.0) or 0.0)
            if buy_power <= 0 and hasattr(self, "config") and self.config:
                buy_power = float(getattr(self.config, "balance_ars", 0.0) or 0.0)

            # 2. Total disponible para ventas en USDT convertido a ARS
            sell_power = 0.0
            free_usdt = await self.client.get_funding_asset("USDT")
            self._last_free_usdt = free_usdt
            if free_usdt > 0:
                approx_tc = 1400.0
                if self.last_benchmarks:
                    bm_vals = [b.avg_top_n_price for b in self.last_benchmarks.values() if b.avg_top_n_price > 0]
                    if bm_vals:
                        approx_tc = sum(bm_vals) / len(bm_vals)
                sell_power = free_usdt * approx_tc

            total_volume = buy_power + sell_power
            if total_volume > 10_000.0:
                return total_volume
            return float(getattr(self.config, "volume_ref", 500_000.0) or 500_000.0)
        except Exception as e_stk:
            logger.debug("No se pudo calcular volumen operativo total: %s", e_stk)
        return float(getattr(self.config, "volume_ref", 500_000.0) or 500_000.0)


    async def get_pay_id_map(self) -> dict[str, int]:
        """Obtiene o refresca el mapeo de identificador a ID de método de pago."""
        if self.pay_id_map:
            return self.pay_id_map
        methods_raw = await self.method_selector.get_available_methods()
        pay_id_map: dict[str, int] = {}
        for m in methods_raw:
            ident = (
                m.get("tradeMethodIdentifier")
                or m.get("identifier")
                or m.get("payType")
                or (m.get("tradeMethod", {}).get("identifier") if isinstance(m.get("tradeMethod"), dict) else "")
            )
            if ident:
                pay_id_map[ident] = int(m.get("id", m.get("payId", 0)))
        self.pay_id_map = pay_id_map
        return self.pay_id_map


