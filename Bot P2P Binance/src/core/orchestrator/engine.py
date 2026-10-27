"""
BotEngine Core Orchestrator for Bot P2P Binance.
Coordinates infrastructure, business modules, Telegram interface, and state machines.
"""
import time
import asyncio
import logging
from datetime import datetime
from typing import Optional, Any, Union, Dict, List, Set, Tuple


from config.settings import (
    REGROUP_INTERVAL_HOURS, DEFAULT_POLL_INTERVAL,
    WATCHDOG_TIMEOUT_SECONDS, P2P_ASSETS_ARS,
    DAILY_REPORT_HOUR, DAILY_REPORT_MINUTE,
    AD_STATUS_ONLINE, AD_STATUS_OFFLINE,
)
from core.network.binance_api import BinanceClient
from core.spot_client import SpotClient
from core.fiwind_client import FiwindClient
from core.market_scanner import MarketScanner
from core.method_selector import MethodSelector
from core.ads.manager import AdsManager
from core.pricing.buy_repositioner import Repositioner
from core.liquidity.liquidity_manager import LiquidityTracker
from core.war_detector import WarDetector
from data.database import Database
from data.models import BotConfig, Benchmark, RepositionDecision
from core.profit_tracker import ProfitTracker
from core.pricing.sell_repositioner import SellRepositioner
from telegram_bot.bot import TelegramBot
from telegram_bot.formatters import (
    format_status, format_daily_report,
)

from .lifecycle_manager import LifecycleMixin
from .calibrator import CalibratorMixin
from .initializer import InitializerMixin
from .cycle_executor import CycleExecutorMixin

logger = logging.getLogger("orchestrator.engine")


class BotEngine(LifecycleMixin, CalibratorMixin, InitializerMixin, CycleExecutorMixin):
    """Motor principal del bot. Coordina todos los módulos."""
    shutdown_event = None

    def __init__(self):
        # Infraestructura
        self.db = Database()
        self.client = BinanceClient()
        self.spot_client = SpotClient()
        self.fiwind = FiwindClient(db=self.db)

        # Módulos de negocio
        self.scanner = MarketScanner(self.client, self.spot_client, self.db)
        self.method_selector = MethodSelector(self.client, self.db)
        self.ads_manager = AdsManager(self.client, self.db)
        self.liquidity = LiquidityTracker(self.client, self.db, spot_client=self.spot_client)
        self.war_detector = WarDetector(self.db)
        self.repositioner = Repositioner(
            self.ads_manager, self.scanner,
            self.liquidity, self.war_detector, self.db,
            fiwind_client=self.fiwind,
        )
        self.profit_tracker = ProfitTracker(self.db, self.client)
        self.sell_repositioner = SellRepositioner(
            self.db, self.ads_manager, self.profit_tracker, fiwind_client=self.fiwind
        )

        # Telegram
        self.telegram = TelegramBot(self.db, bot_engine=self)

        # Estado
        self.config = BotConfig()
        self.method_groups: dict[int, list[str]] = {}
        self.assets: list[str] = []
        self.my_ads = []
        self.my_sell_ads = []
        self.pay_id_map: dict[str, int] = {}
        self.last_benchmarks: dict[str, Benchmark] = {}
        self.latest_decisions: dict[str, RepositionDecision] = {}
        self.cycle_count: int = 0
        self._altcoin_notified_orders: set[str] = set()
        self._running = False
        self._last_regroup: datetime = datetime.min

        # Watchdog & Seguridad (Edge Case 5)
        self.last_successful_binance_time: float = time.time()
        self._watchdog_alerted: bool = False
        self._paused_by_watchdog: bool = False
        self._watchdog_pause_confirmed: bool = False
        self._last_antiban_alert_ts: float = 0.0
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self._state_change_callbacks: list = []
        self._op_lock: asyncio.Lock = asyncio.Lock()
        self._op_lock_owner = None
        self._shutdown_lock: asyncio.Lock = asyncio.Lock()
        self.is_fiwind_arbitrage_hold: bool = False

    @property
    def _paused_by_liquidity(self) -> set:
        if hasattr(self, "repositioner") and self.repositioner is not None:
            s = getattr(self.repositioner, "_paused_by_liquidity", None)
            if not isinstance(s, set):
                s = self.__dict__.get("_paused_by_liquidity_fallback", set())
                self.repositioner._paused_by_liquidity = s
            return s
        if "_paused_by_liquidity_fallback" not in self.__dict__:
            self.__dict__["_paused_by_liquidity_fallback"] = set()
        return self.__dict__["_paused_by_liquidity_fallback"]

    @_paused_by_liquidity.setter
    def _paused_by_liquidity(self, val: set):
        self.__dict__["_paused_by_liquidity_fallback"] = val
        if hasattr(self, "repositioner") and self.repositioner is not None:
            self.repositioner._paused_by_liquidity = val

    @property
    def _paused_by_antiban(self) -> set:
        if hasattr(self, "repositioner") and self.repositioner is not None:
            s = getattr(self.repositioner, "_paused_by_antiban", None)
            if not isinstance(s, set):
                s = self.__dict__.get("_paused_by_antiban_fallback", set())
                self.repositioner._paused_by_antiban = s
            return s
        if "_paused_by_antiban_fallback" not in self.__dict__:
            self.__dict__["_paused_by_antiban_fallback"] = set()
        return self.__dict__["_paused_by_antiban_fallback"]

    @_paused_by_antiban.setter
    def _paused_by_antiban(self, val: set):
        self.__dict__["_paused_by_antiban_fallback"] = val
        if hasattr(self, "repositioner") and self.repositioner is not None:
            self.repositioner._paused_by_antiban = val

    def _get_op_lock(self) -> asyncio.Lock:
        lock = getattr(self, "_op_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            self._op_lock = lock
        return lock

    def _get_shutdown_lock(self) -> asyncio.Lock:
        lock = getattr(self, "_shutdown_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            self._shutdown_lock = lock
        return lock

    def add_state_change_callback(self, callback):
        """Registra un callback que se invoca cuando el bot se enciende o apaga."""
        if not hasattr(self, "_state_change_callbacks"):
            self._state_change_callbacks = []
        if callback not in self._state_change_callbacks:
            self._state_change_callbacks.append(callback)

    def _notify_state_change(self):
        """Notifica a los callbacks registrados sobre el cambio de estado (is_paused)."""
        is_paused = self.config.is_paused
        for cb in getattr(self, "_state_change_callbacks", []):
            try:
                cb(is_paused)
            except Exception as e:
                logger.debug("Error en callback de estado: %s", e)


    async def get_status_text(self) -> str:
        """Genera texto de estado para Telegram."""
        ads = self.my_ads if self.my_ads else self.db.get_my_ads()
        return format_status(
            ads=ads,
            config=self.config,
            balance=self.liquidity.balance,
            available=self.liquidity.available_balance,
        )

    async def run(self):
        """Loop principal del bot con Watchdog de seguridad."""
        await self.initialize()
        self._running = True

        logger.info("🚀 Loop principal iniciado (interval=%ds)",
                     self.config.poll_interval)

        cycle_count = 0
        while self._running:
            try:
                # Watchdog de conexión Binance (Edge Case 5)
                # Solo evaluar si el bot está activo (no en pausa ni durmiendo)
                if not self.config.is_paused and not self.config.sleep_until:
                    elapsed_since_success = time.time() - self.last_successful_binance_time
                    if elapsed_since_success > WATCHDOG_TIMEOUT_SECONDS:
                        logger.critical(
                            "🚨 WATCHDOG: Más de %ds sin respuesta de Binance! Pausando anuncios preventivamente.",
                            int(elapsed_since_success),
                        )
                        # 1. Congelar inmediatamente el estado local del bot en SQLite
                        self.config.is_paused = True
                        self._paused_by_watchdog = True
                        self._watchdog_pause_confirmed = False
                        self.db.save_bot_config(self.config)
                        self._notify_state_change()

                        # 2. Intentar pausar anuncios en Binance
                        pause_status = "⚠️ No se pudo confirmar pausa en Binance (red caída)"
                        try:
                            paused_count = await self.ads_manager.pause_all()
                            remaining_online = [
                                a for a in self.db.get_my_ads() if getattr(a, "status", 0) == AD_STATUS_ONLINE
                            ]
                            if not (paused_count == 0 and remaining_online):
                                self._watchdog_pause_confirmed = True
                                pause_status = f"✅ {paused_count} anuncios pausados en Binance"
                        except Exception as e_pause:
                            logger.error("Watchdog: error pausando anuncios en Binance: %s", e_pause)

                        # 3. Notificar a Telegram con reporte verídico
                        if not self._watchdog_alerted:
                            self._watchdog_alerted = True
                            try:
                                await self.telegram.notify(
                                    f"🚨 *ALERTA DE SEGURIDAD (WATCHDOG)*\n\n"
                                    f"Pérdida de conexión con Binance por más de {int(elapsed_since_success)}s (límite {WATCHDOG_TIMEOUT_SECONDS}s).\n"
                                    f"• Estado de anuncios: *{pause_status}*\n"
                                    f"• Estado del motor: *PAUSA PREVENTIVA*\n\n"
                                    f"El bot intentará reconectarse automáticamente cuando vuelva la red (o podés usar `/encender`)."
                                )
                            except Exception:
                                pass
                elif self._paused_by_watchdog and not self._watchdog_pause_confirmed:
                    try:
                        paused_count = await self.ads_manager.pause_all()
                        remaining_online = [
                            a for a in self.db.get_my_ads() if getattr(a, "status", 0) == AD_STATUS_ONLINE
                        ]
                        if not (paused_count == 0 and remaining_online):
                            self._watchdog_pause_confirmed = True
                            logger.info("Watchdog: pausa preventiva en Binance confirmada (%s anuncios).", paused_count)
                    except Exception as e_pause_retry:
                        logger.error("Watchdog (reintento): error pausando anuncios en Binance: %s", e_pause_retry)
                elif not getattr(self, "_paused_by_watchdog", False):
                    self.last_successful_binance_time = time.time()

                cycle_count += 1
                self.cycle_count = cycle_count
                start = datetime.now()

                await self.run_cycle()

                elapsed = (datetime.now() - start).total_seconds()
                logger.info(
                    "Ciclo #%d completado en %.1fs", cycle_count, elapsed
                )

                # Mantenimiento de BD: purga liviana por lotes aprox. cada hora (120 ciclos x 30s)
                if cycle_count % 120 == 0:
                    try:
                        self.db.purge_by_retention()
                    except Exception as e_purge:
                        logger.warning("Purga periódica de BD falló: %s", e_purge)

                # ── Reporte Diario (1 vez al día, cierre de jornada) ──
                now = datetime.now()
                today_str = now.strftime("%Y-%m-%d")
                last_report_date = self.db.get_config("last_daily_report_date", "")

                if (
                    (now.hour > DAILY_REPORT_HOUR or (now.hour == DAILY_REPORT_HOUR and now.minute >= DAILY_REPORT_MINUTE))
                    and last_report_date != today_str
                ):
                    self.db.set_config("last_daily_report_date", today_str)
                    profit_ars = None
                    if hasattr(self, "profit_tracker") and self.profit_tracker:
                        try:
                            rep = await self.profit_tracker.calculate_profit(today_str)
                            profit_ars = rep.total_profit_ars
                        except Exception as e_prof:
                            logger.error("Error calculando ganancia diaria para reporte programado: %s", e_prof)
                    stats = self.db.get_daily_stats(today_str, profit_ars=profit_ars)
                    await self.telegram.notify(format_daily_report(stats))
                    logger.info("📊 Reporte diario enviado para la fecha %s", today_str)

                # Recargar interval (puede haber cambiado)
                self.config = self.db.load_bot_config()
                wait = max(self.config.poll_interval - elapsed, 1)
                try:
                    await asyncio.wait_for(self.shutdown_event.wait(), timeout=wait)
                    if self.shutdown_event.is_set():
                        logger.info("Evento de shutdown recibido, finalizando loop...")
                        break
                except asyncio.TimeoutError:
                    pass

            except asyncio.CancelledError:
                logger.info("Bot cancelado")
                break
            except Exception as e:
                logger.error("Error en ciclo #%d: %s", cycle_count, e, exc_info=True)
                err_clean = str(e).replace("https://api.binance.com", "Binance").replace("`", "'")
                await self.telegram.notify(f"❌ Error en ciclo #{cycle_count}:\n`{err_clean[:200]}`")
                await asyncio.sleep(10)  # Esperar antes de reintentar


