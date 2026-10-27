"""
Interfaz de control remoto y monitoreo en tiempo real vía Telegram.
Implementa autorización fail-closed, agregación de métricas y despacho de alertas.
Referencia de diseño: docs/TELEGRAM_INTERFACE.md
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from .formatters import format_periodic_alert
from .handlers import TelegramCommandHandlerMixin

logger = logging.getLogger(__name__)


class TradingBotInterface(TelegramCommandHandlerMixin):
    """Interfaz de Telegram con control de acceso fail-closed para operar el bot."""

    def __init__(
        self,
        telegram_token: str,
        trading_bot,
        authorized_users: Optional[List[int]] = None,
    ):
        self.token = telegram_token
        self.trading_bot = trading_bot
        self.authorized_users = list(authorized_users) if authorized_users else []
        self.app = None
        self.alerts_enabled = True
        self.alert_interval_minutes = 60

        logger.info("[TELEGRAM] Bot Interface initialized")

    async def initialize(self):
        """Inicializa la aplicación de Telegram y registra los handlers de comandos."""
        self.app = Application.builder().token(self.token).build()
        self._register_handlers()
        logger.info("[TELEGRAM] Application initialized")

    def _register_handlers(self):
        """Registra todos los comandos interactivos soportados."""
        commands = [
            ("start", self.cmd_start),
            ("help", self.cmd_help),
            ("status", self.cmd_status),
            ("stats", self.cmd_stats),
            ("pnl", self.cmd_pnl),
            ("positions", self.cmd_positions),
            ("trades", self.cmd_trades),
            ("startbot", self.cmd_start_bot),
            ("stopbot", self.cmd_stop_bot),
            ("pause", self.cmd_pause_strategies),
            ("resume", self.cmd_resume_strategies),
            ("strategies", self.cmd_strategies),
            ("enable", self.cmd_enable_strategy),
            ("disable", self.cmd_disable_strategy),
            ("reload", self.cmd_reload_config),
            ("backtest", self.cmd_trigger_backtest),
            ("collect", self.cmd_start_data_collection),
            ("alerts", self.cmd_toggle_alerts),
            ("alertson", self.cmd_alerts_on),
            ("alertsoff", self.cmd_alerts_off),
        ]
        for name, callback in commands:
            self.app.add_handler(CommandHandler(name, callback))

        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        logger.info("[TELEGRAM] Handlers registered")

    def _check_authorization(self, user_id: int) -> bool:
        """Verifica si el usuario está en la lista blanca (política fail-closed)."""
        if not self.authorized_users:
            logger.warning(f"[TELEGRAM] Fail-closed: lista de autorizados vacía (user {user_id})")
            return False
        return user_id in self.authorized_users

    async def _send_unauthorized(self, update: Update):
        """Envía notificación de acceso denegado."""
        await update.message.reply_text(
            "[UNAUTHORIZED]\n\n"
            "No tienes permiso para operar este bot.\n"
            f"Tu user ID: {update.effective_user.id}"
        )
        logger.warning(f"[TELEGRAM] Unauthorized access attempt from {update.effective_user.id}")

    def _extract_trades_from_state(self) -> List[Dict[str, Any]]:
        """Obtiene la lista consolidada de trades soportando `trades_history` y `trades_dia`."""
        if not hasattr(self.trading_bot, "state_manager") or not self.trading_bot.state_manager:
            return []
        state = self.trading_bot.state_manager.state
        history = state.get("trades_history")
        if history:
            return list(history)
        return list(state.get("trades_dia", []))

    async def _calculate_statistics(self) -> Dict[str, Any]:
        """Calcula estadísticas generales del bot desde StateManager."""
        stats: Dict[str, Any] = {
            "sharpe_7d": "N/A",
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "max_drawdown": 0.0,
            "today_trades": 0,
            "today_pnl": 0.0,
            "week_trades": 0,
            "week_pnl": 0.0,
        }

        try:
            trades = self._extract_trades_from_state()
            stats["total_trades"] = len(trades)
            stats["total_pnl"] = sum(float(t.get("pnl", 0.0)) for t in trades)

            if trades:
                winning = sum(1 for t in trades if float(t.get("pnl", 0.0)) > 0)
                stats["win_rate"] = (winning / len(trades)) * 100.0

            today = datetime.now().date()
            today_trades = [
                t for t in trades
                if t.get("timestamp") and datetime.fromisoformat(str(t["timestamp"])).date() == today
            ]
            stats["today_trades"] = len(today_trades)
            stats["today_pnl"] = sum(float(t.get("pnl", 0.0)) for t in today_trades)

            week_ago = datetime.now() - timedelta(days=7)
            week_trades = [
                t for t in trades
                if t.get("timestamp") and datetime.fromisoformat(str(t["timestamp"])) > week_ago
            ]
            stats["week_trades"] = len(week_trades)
            stats["week_pnl"] = sum(float(t.get("pnl", 0.0)) for t in week_trades)

            if len(week_trades) > 1:
                returns = [float(t.get("pnl", 0.0)) for t in week_trades]
                mean_ret = sum(returns) / len(returns)
                std_ret = (sum((r - mean_ret) ** 2 for r in returns) / len(returns)) ** 0.5
                if std_ret > 0:
                    sharpe = (mean_ret / std_ret) * (252.0 ** 0.5)
                    stats["sharpe_7d"] = f"{sharpe:.2f}"

        except Exception as e:
            logger.error(f"[TELEGRAM] Error calculating statistics: {e}")

        return stats

    async def _get_pnl_breakdown(self) -> Dict[str, float]:
        """Obtiene desglose de P&L soportando claves `'strategy'` y `'estrategia'`."""
        pnl = {
            "total": 0.0,
            "stat_arb": 0.0,
            "market_making": 0.0,
            "today": 0.0,
            "week": 0.0,
            "month": 0.0,
        }

        try:
            trades = self._extract_trades_from_state()
            pnl["total"] = sum(float(t.get("pnl", 0.0)) for t in trades)
            pnl["stat_arb"] = sum(
                float(t.get("pnl", 0.0))
                for t in trades
                if (t.get("strategy") or t.get("estrategia")) == "statistical_arbitrage"
            )
            pnl["market_making"] = sum(
                float(t.get("pnl", 0.0))
                for t in trades
                if (t.get("strategy") or t.get("estrategia")) == "market_making"
            )

            now = datetime.now()
            today = now.date()
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)

            for trade in trades:
                if not trade.get("timestamp"):
                    continue
                trade_time = datetime.fromisoformat(str(trade["timestamp"]))
                trade_pnl = float(trade.get("pnl", 0.0))
                if trade_time.date() == today:
                    pnl["today"] += trade_pnl
                if trade_time > week_ago:
                    pnl["week"] += trade_pnl
                if trade_time > month_ago:
                    pnl["month"] += trade_pnl

        except Exception as e:
            logger.error(f"[TELEGRAM] Error getting P&L breakdown: {e}")

        return pnl

    async def _get_current_positions(self) -> List[Dict[str, Any]]:
        """Obtiene posiciones abiertas desde las estrategias activas o StateManager."""
        positions: List[Dict[str, Any]] = []
        try:
            if hasattr(self.trading_bot, "stat_arb_strategy") and self.trading_bot.stat_arb_strategy:
                sa = self.trading_bot.stat_arb_strategy
                if getattr(sa, "current_position", None):
                    positions.append({
                        "pair": "USDT/USDC",
                        "side": str(sa.current_position).upper(),
                        "size_usd": getattr(sa, "position_size_usd", 0.0),
                        "entry_price": getattr(sa, "position_entry_price", 1.0) or 1.0,
                        "current_price": (
                            sa.ratio_history[-1]
                            if getattr(sa, "ratio_history", None)
                            else (getattr(sa, "position_entry_price", 1.0) or 1.0)
                        ),
                        "pnl": 0.0,
                        "pnl_pct": 0.0,
                        "duration": "Abierta",
                    })
            elif hasattr(self.trading_bot, "state_manager") and self.trading_bot.state_manager:
                state = self.trading_bot.state_manager.state
                sa_state = state.get("statistical_arbitrage", {})
                if sa_state.get("position"):
                    positions.append({
                        "pair": "USDT/USDC",
                        "side": str(sa_state["position"]).upper(),
                        "size_usd": sa_state.get("position_size_usd", 0.0),
                        "entry_price": sa_state.get("entry_price", 0.0),
                        "current_price": sa_state.get("entry_price", 0.0),
                        "pnl": 0.0,
                        "pnl_pct": 0.0,
                        "duration": "Abierta",
                    })
        except Exception as e:
            logger.error(f"[TELEGRAM] Error getting positions: {e}")

        return positions

    async def _get_recent_trades(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Obtiene los últimos N trades soportando `'strategy'` y `'estrategia'`."""
        recent_trades: List[Dict[str, Any]] = []
        try:
            trades = self._extract_trades_from_state()
            sorted_trades = sorted(trades, key=lambda t: str(t.get("timestamp", "")), reverse=True)
            for trade in sorted_trades[:limit]:
                recent_trades.append({
                    "timestamp": trade.get("timestamp", "N/A"),
                    "strategy": trade.get("strategy") or trade.get("estrategia", "N/A"),
                    "pair": trade.get("pair", "USDT_ARS"),
                    "side": trade.get("side") or trade.get("action", "N/A"),
                    "size_usd": trade.get("amount_usd", trade.get("size_usd", 0.0)),
                    "pnl": trade.get("pnl", 0.0),
                })
        except Exception as e:
            logger.error(f"[TELEGRAM] Error getting recent trades: {e}")

        return recent_trades

    async def send_alert(self, message: str, chat_id: Optional[int] = None):
        """Envía una alerta a un chat específico o a todos los usuarios autorizados."""
        if not self.alerts_enabled or not self.app:
            return
        try:
            if chat_id:
                await self.app.bot.send_message(chat_id=chat_id, text=f"⚠️ [ALERT]\n\n{message}")
            else:
                for user_id in self.authorized_users:
                    await self.app.bot.send_message(chat_id=user_id, text=f"⚠️ [ALERT]\n\n{message}")
        except Exception as e:
            logger.error(f"[TELEGRAM] Error sending alert: {e}")

    async def start_periodic_alerts(self):
        """Loop asíncrono para despacho periódico de resúmenes operativos."""
        while True:
            try:
                if self.alerts_enabled and self.app:
                    stats = await self._calculate_statistics()
                    alert_msg = format_periodic_alert(stats)
                    for user_id in self.authorized_users:
                        await self.app.bot.send_message(chat_id=user_id, text=alert_msg)
                await asyncio.sleep(self.alert_interval_minutes * 60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TELEGRAM] Error in periodic alerts loop: {e}")
                await asyncio.sleep(60)

    async def start(self):
        """Inicia la interfaz de Telegram y el loop de alertas periódicas."""
        await self.initialize()
        asyncio.create_task(self.start_periodic_alerts())
        await self.app.run_polling()

    async def stop(self):
        """Detiene la aplicación de Telegram de forma segura."""
        if self.app:
            await self.app.stop()
        logger.info("[TELEGRAM] Bot stopped")
