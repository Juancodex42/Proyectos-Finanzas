"""Gestor unificado del sistema Dual-Bot (Bot 1 Radar Paroli y Bot 2 Macro Consolidado).
Coordina estado thread-safe, validación de configuración por whitelist y enlace con Telegram.
Referencia de diseño: docs/ARQUITECTURA.md"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from domain.models import BotStateConfig
from engine.execution.binance_client import BinanceFuturesClient
from engine.execution.bot_worker_tasks import (
    process_live_bot2_signals,
    reconcile_active_bot1_trade,
    reconcile_startup_positions,
    scan_bot1_radar_and_dispatch,
)
from engine.execution.signal_dispatcher import StreakMutexManager
from engine.execution.telegram_bot import TelegramBotClient

logger = logging.getLogger("NexusDualBotManager")


class DualBotManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DualBotManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.client: Optional[BinanceFuturesClient] = None
        self.mock_mode: bool = True
        self.last_update_ts: float = time.time()
        self.last_processed_candle_ts: Dict[str, int] = {}
        self.worker_running: bool = False
        self.worker_thread: Optional[threading.Thread] = None
        self.telegram_bot: Optional[TelegramBotClient] = None
        self.telegram_config: Dict[str, Any] = {"token": "", "chat_ids": []}
        self.streak_mutex = StreakMutexManager()

        self.bot1 = {
            "id": "bot_1_daily_convex",
            "name": "Bot 1: Micro-Balas Diarias (Flujo Arbitraje)",
            "state": "STOPPED",
            "strategy": "daily_confluence",
            "strategies": ["daily_confluence", "climax_reversal"],
            "symbol": "BTC/USDT",
            "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
            "mode": "A",
            "streak_target": 3,
            "rr_ratio": 2.5,
            "daily_bullet_usd": 5.0,
            "current_step": 0,
            "current_bullet_usd": 5.0,
            "accumulated_profit_usd": 0.0,
            "streaks_completed": 0,
            "total_pnl_usd": 0.0,
            "today_pnl_usd": 0.0,
            "last_trade_result": None,
            "active_trade": None,
            "mutex_state": "IDLE_WAITING",
        }

        self.bot2 = {
            "id": "bot_2_macro_portfolio",
            "name": "Bot 2: Macro-Portafolio Consolidado (Trading Clásico)",
            "state": "STOPPED",
            "strategy": "volatility_squeeze_ml",
            "symbol": "BTC/USDT",
            "risk_per_trade_pct": 1.5,
            "drawdown_limit_pct": 7.6,
            "allocated_capital_usd": 1000.0,
            "current_equity_usd": 1000.0,
            "peak_equity_usd": 1000.0,
            "current_drawdown_pct": 0.0,
            "total_pnl_usd": 0.0,
            "month_pnl_usd": 0.0,
            "open_positions": [],
        }

        self.equity_history: List[Dict[str, Any]] = [
            {
                "timestamp": int(time.time()),
                "bot1_equity": 5.0,
                "bot2_equity": 1000.0,
                "combined_equity": 1005.0,
                "bot2_drawdown": 0.0,
            }
        ]

        self.events_log: List[Dict[str, Any]] = [
            {
                "id": 1,
                "time": time.strftime("%H:%M:%S"),
                "source": "SISTEMA",
                "message": "Terminal Dual-Bot inicializada en modo Seguro. Radar Multi-Estrategia y Mutex listos.",
            }
        ]

        self._start_worker()

    def _start_worker(self):
        """Inicia el hilo continuo de ejecución."""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.worker_running = True
            self.worker_thread = threading.Thread(target=self._execution_worker_loop, daemon=True)
            self.worker_thread.start()

    def _execution_worker_loop(self):
        """Bucle continuo de supervisión, escaneo de señales en velas cerradas y purga OCO."""
        while self.worker_running:
            try:
                time.sleep(5.0)
                if self.client and self.client.connected and not self.mock_mode:
                    observed_symbols = set(
                        self.bot1.get("symbols", ["BTC/USDT"]) + [self.bot2.get("symbol", "BTC/USDT")]
                    )
                    for sym in observed_symbols:
                        self.client.purge_orphan_orders_if_flat(sym)

                    if self.bot1["state"] == "RUNNING":
                        self._scan_bot1_radar_and_dispatch()

                    if self.bot2["state"] == "RUNNING":
                        self._process_live_bot2_signals()
            except Exception as e:
                logger.error(f"Error en bucle de ejecución worker: {e}")

    def _scan_bot1_radar_and_dispatch(self):
        scan_bot1_radar_and_dispatch(self)

    def _reconcile_active_bot1_trade(self):
        reconcile_active_bot1_trade(self)

    def _process_live_bot2_signals(self):
        process_live_bot2_signals(self)

    def _reconcile_startup_positions(self):
        reconcile_startup_positions(self)

    def set_credentials(self, api_key: str, api_secret: str, testnet: bool = True) -> Dict[str, Any]:
        """Configura y valida las claves de Binance sin bloquear el mutex durante llamadas de red."""
        new_client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
        test_res = new_client.test_connection()
        with self._lock:
            self.client = new_client
            if test_res.get("success"):
                self.mock_mode = False
                free_usdt = test_res.get("usdt_balance", 0.0)
                if free_usdt > 0:
                    self.bot2["current_equity_usd"] = free_usdt
                    self.bot2["peak_equity_usd"] = max(self.bot2["peak_equity_usd"], free_usdt)
                self._add_event(
                    "BINANCE_API",
                    f"Conexión exitosa a Binance Futures ({'Testnet' if testnet else 'Live'}). Balance USDT: ${free_usdt:.2f}",
                )
            else:
                self.mock_mode = True
                self._add_event(
                    "ALERTA",
                    f"Fallo al conectar con Binance API: {test_res.get('error')}. Operando en modo Mock.",
                )

        if test_res.get("success"):
            self._reconcile_startup_positions()
        return test_res

    def toggle_bot(self, bot_id: str, new_state: str) -> Dict[str, Any]:
        """Enciende, pausa o apaga uno de los dos bots (RUNNING, PAUSED, STOPPED)."""
        valid_states = ["RUNNING", "PAUSED", "STOPPED"]
        if new_state not in valid_states:
            return {"success": False, "error": f"Estado inválido: {new_state}"}

        with self._lock:
            target_bot = self.bot1 if bot_id == "bot_1" else self.bot2
            old_state = target_bot["state"]

            if bot_id == "bot_2" and old_state == "AUTO_LOCKED" and new_state == "RUNNING":
                if target_bot["current_drawdown_pct"] >= target_bot["drawdown_limit_pct"]:
                    return {
                        "success": False,
                        "error": f"Bot 2 bloqueado por seguridad: Drawdown actual ({target_bot['current_drawdown_pct']:.1f}%) supera el límite del {target_bot['drawdown_limit_pct']}%.",
                    }

            target_bot["state"] = new_state
            self._add_event(
                bot_id.upper(),
                f"Estado cambiado de {old_state} a {new_state} para {target_bot['name']}.",
            )
            return {"success": True, "bot_id": bot_id, "state": new_state}

    def reset_bot1_streak(self, deposit_to_base: bool = True) -> Dict[str, Any]:
        """Resetea manualmente la racha del Bot 1 o deposita ganancias a la base de arbitraje."""
        with self._lock:
            profit = self.bot1["accumulated_profit_usd"]
            old_step = self.bot1["current_step"]

            if deposit_to_base and profit > 0:
                self.bot2["current_equity_usd"] += profit
                self.bot2["peak_equity_usd"] = max(
                    self.bot2["peak_equity_usd"], self.bot2["current_equity_usd"]
                )
                self._add_event(
                    "BOT_1",
                    f"Ganancia acumulada de ${profit:.2f} transferida y consolidada en Bot 2 / Arbitraje.",
                )

            self.bot1["current_step"] = 0
            self.bot1["current_bullet_usd"] = self.bot1["daily_bullet_usd"]
            self.bot1["accumulated_profit_usd"] = 0.0
            self.bot1["active_trade"] = None
            self.streak_mutex.release_lock("MANUAL_RESET")
            self.bot1["mutex_state"] = "IDLE_WAITING"

            self._add_event(
                "BOT_1",
                f"Racha reseteada desde Paso {old_step} a Paso 0. Bala restablecida a ${self.bot1['daily_bullet_usd']:.2f}.",
            )
            return {"success": True, "transferred_profit": profit}

    def update_bot_config(self, bot_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza parámetros de estrategia o riesgo filtrando estrictamente por lista blanca."""
        if not isinstance(updates, dict):
            return {"success": False, "error": "Formato de actualización inválido."}
        allowed_keys = BotStateConfig.ALLOWED_UPDATE_KEYS
        sanitized_updates = {k: v for k, v in updates.items() if k in allowed_keys}
        with self._lock:
            target = self.bot1 if bot_id == "bot_1" else self.bot2
            for k, v in sanitized_updates.items():
                if k in target:
                    target[k] = v
            if bot_id == "bot_1" and "mode" in sanitized_updates:
                target["streak_target"] = 4 if sanitized_updates["mode"] == "B" else 3
            self._add_event(bot_id.upper(), f"Parámetros del radar actualizados: {sanitized_updates}")
            return {"success": True, "config": target}

    def panic_close_all(self) -> Dict[str, Any]:
        """BOTÓN DE PÁNICO (KILL SWITCH): Detiene ambos bots y cierra posiciones inmediatamente."""
        with self._lock:
            self.bot1["state"] = "STOPPED"
            self.bot2["state"] = "STOPPED"
            self.bot1["active_trade"] = None
            self.streak_mutex.release_lock("PANIC_KILL")
            self.bot1["mutex_state"] = "IDLE_WAITING"
            client_ref = self.client
            is_live = client_ref is not None and not self.mock_mode

        if is_live and client_ref is not None:
            res = client_ref.close_all_positions()
        else:
            res = {"success": True, "mock": True, "message": "Todas las órdenes virtuales cerradas."}

        with self._lock:
            self._add_event(
                "KILL_SWITCH",
                "⚠️ Protocolo de Pánico ejecutado: Bots apagados y posiciones canceladas a mercado.",
            )
        return res

    def record_simulated_trade(
        self, bot_id: str, is_win: bool, pnl_usd: float, symbol: str = "BTC/USDT"
    ):
        """Registra el resultado de un trade para actualizar rachas, drawdowns y gráficas."""
        with self._lock:
            ts = int(time.time())
            if bot_id == "bot_1":
                b1 = self.bot1
                b1["last_trade_result"] = "WIN" if is_win else "LOSS"
                if is_win:
                    b1["current_step"] += 1
                    b1["accumulated_profit_usd"] += pnl_usd
                    b1["today_pnl_usd"] += pnl_usd
                    b1["total_pnl_usd"] += pnl_usd

                    if b1["current_step"] >= b1["streak_target"]:
                        b1["streaks_completed"] += 1
                        total_streak_profit = b1["accumulated_profit_usd"]
                        self.bot2["current_equity_usd"] += total_streak_profit
                        self.bot2["peak_equity_usd"] = max(
                            self.bot2["peak_equity_usd"], self.bot2["current_equity_usd"]
                        )
                        self._add_event(
                            "BOT_1",
                            f"🏆 ¡RACHA DE {b1['streak_target']} TRADES COMPLETADA! Ganancia: +${total_streak_profit:.2f} consolidada en Arbitraje.",
                        )
                        b1["current_step"] = 0
                        b1["current_bullet_usd"] = b1["daily_bullet_usd"]
                        b1["accumulated_profit_usd"] = 0.0
                    else:
                        b1["current_bullet_usd"] = b1["current_bullet_usd"] * (1.0 + b1["rr_ratio"])
                        self._add_event(
                            "BOT_1",
                            f"✅ Trade Ganador en {symbol} (+${pnl_usd:.2f}). Avanza a Paso {b1['current_step']}/{b1['streak_target']} (Próxima bala: ${b1['current_bullet_usd']:.2f}).",
                        )
                else:
                    b1["today_pnl_usd"] -= b1["current_bullet_usd"]
                    b1["total_pnl_usd"] -= b1["current_bullet_usd"]
                    self._add_event(
                        "BOT_1",
                        f"❌ Stop Loss tocado en {symbol} (-${b1['current_bullet_usd']:.2f}). Racha reiniciada a Paso 0. Capital base intacto.",
                    )
                    b1["current_step"] = 0
                    b1["current_bullet_usd"] = b1["daily_bullet_usd"]
                    b1["accumulated_profit_usd"] = 0.0

            elif bot_id == "bot_2":
                b2 = self.bot2
                b2["current_equity_usd"] += pnl_usd
                b2["total_pnl_usd"] += pnl_usd
                b2["month_pnl_usd"] += pnl_usd

                if b2["current_equity_usd"] > b2["peak_equity_usd"]:
                    b2["peak_equity_usd"] = b2["current_equity_usd"]
                    b2["current_drawdown_pct"] = 0.0
                else:
                    dd = (
                        (b2["peak_equity_usd"] - b2["current_equity_usd"])
                        / b2["peak_equity_usd"]
                        * 100.0
                    )
                    b2["current_drawdown_pct"] = round(dd, 2)

                if b2["current_drawdown_pct"] >= b2["drawdown_limit_pct"]:
                    b2["state"] = "AUTO_LOCKED"
                    self._add_event(
                        "SEGURIDAD_BOT_2",
                        f"🛑 AUTO-LOCKDOWN ACTIVADO: Drawdown ({b2['current_drawdown_pct']}%) alcanzó el límite ({b2['drawdown_limit_pct']}%). Bot pausado para reparación pasiva.",
                    )

            comb = self.bot1["current_bullet_usd"] + self.bot2["current_equity_usd"]
            self.equity_history.append(
                {
                    "timestamp": ts,
                    "bot1_equity": round(self.bot1["current_bullet_usd"], 2),
                    "bot2_equity": round(self.bot2["current_equity_usd"], 2),
                    "combined_equity": round(comb, 2),
                    "bot2_drawdown": self.bot2["current_drawdown_pct"],
                }
            )
            if len(self.equity_history) > 500:
                self.equity_history.pop(0)

    def get_status(self) -> Dict[str, Any]:
        """Devuelve el estado completo del sistema Dual-Bot para la interfaz web."""
        with self._lock:
            self.bot1["mutex_state"] = self.streak_mutex.state.value
            return {
                "connected": not self.mock_mode and (self.client is not None and self.client.connected),
                "mock_mode": self.mock_mode,
                "bot1": self.bot1,
                "bot2": self.bot2,
                "equity_history": self.equity_history[-60:],
                "events_log": self.events_log[-20:],
                "timestamp": time.time(),
                "telegram_configured": self.telegram_bot is not None and self.telegram_bot.is_configured(),
            }

    def set_telegram_credentials(self, bot_token: str, allowed_chat_ids: List[int]) -> Dict[str, Any]:
        """Configura e inicia el bot de Telegram institucional."""
        with self._lock:
            try:
                clean_token = bot_token.strip()
                clean_chat_ids = [int(cid) for cid in allowed_chat_ids if str(cid).strip()]

                if self.telegram_bot:
                    self.telegram_bot.stop()

                self.telegram_bot = TelegramBotClient(
                    bot_token=clean_token, allowed_chat_ids=clean_chat_ids, manager=self
                )
                self.telegram_config = {"token": clean_token, "chat_ids": clean_chat_ids}

                if self.telegram_bot.is_configured():
                    self.telegram_bot.start()
                    for cid in clean_chat_ids:
                        self.telegram_bot.send_message(
                            cid,
                            "🚀 *¡NEXUS TERMINAL VINCULADA EXITOSAMENTE!*\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            "Tu terminal de Binance Futuros ahora está conectada a tu Telegram.\n"
                            "Escribe /menu o toca los botones interactivos para controlar tus bots.",
                            reply_markup=self.telegram_bot._get_main_keyboard(),
                        )
                    self._add_event(
                        "TELEGRAM",
                        f"Telegram Bot conectado exitosamente. Operadores autorizados: {clean_chat_ids}",
                    )
                    return {"success": True, "chat_ids": clean_chat_ids}
                return {"success": False, "error": "Token o Chat ID inválidos"}
            except Exception as e:
                logger.error(f"Error al configurar Telegram: {e}")
                return {"success": False, "error": str(e)}

    def _add_event(self, source: str, message: str):
        evt = {
            "id": len(self.events_log) + 1,
            "time": time.strftime("%H:%M:%S"),
            "source": source,
            "message": message,
        }
        self.events_log.append(evt)
        if len(self.events_log) > 100:
            self.events_log.pop(0)

        if self.telegram_bot and self.telegram_bot.is_configured():
            critical_sources = [
                "BOT_1",
                "BOT_2",
                "BOT_1_BREAKEVEN",
                "BOT_1_RADAR",
                "KILL_SWITCH",
                "SEGURIDAD_BOT_2",
                "SISTEMA_RECOVERY",
                "BINANCE_API",
            ]
            if source in critical_sources:
                try:
                    self.telegram_bot.broadcast(f"🔔 *[{source}]*\n{message}")
                except Exception as tg_err:
                    logger.warning(f"Aviso enviando broadcast Telegram: {tg_err}")
