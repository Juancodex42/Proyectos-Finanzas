"""
Handlers de comandos interactivos para la interfaz de Telegram.
Conecta acciones de usuario con el orquestador, estrategias y BacktesterEngine real.
Referencia de diseño: docs/TELEGRAM_INTERFACE.md
"""

import asyncio
import logging
from pathlib import Path
import pandas as pd
from telegram import Update
from telegram.ext import ContextTypes

from .formatters import (
    format_welcome,
    format_help,
    format_status,
    format_stats,
    format_pnl,
    format_positions,
    format_trades,
    format_strategies,
    format_data_collection,
    format_backtest_completed,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TelegramCommandHandlerMixin:
    """Mixin que implementa los handlers de comandos para TradingBotInterface."""

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /start."""
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await self._send_unauthorized(update)
            return
        await update.message.reply_text(format_welcome())

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /help."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return
        await update.message.reply_text(format_help())

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /status - Estado del bot y portafolio."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return

        try:
            bot_running = getattr(self.trading_bot, "running", False)
            strategies_status = []

            if hasattr(self.trading_bot, "stat_arb_strategy") and self.trading_bot.stat_arb_strategy:
                sa_on = self.trading_bot.stat_arb_strategy.enabled
                strategies_status.append(f"Statistical Arbitrage: {'ON' if sa_on else 'OFF'}")

            if hasattr(self.trading_bot, "market_making_strategy") and self.trading_bot.market_making_strategy:
                mm_on = self.trading_bot.market_making_strategy.enabled
                strategies_status.append(f"Market Making: {'ON' if mm_on else 'OFF'}")

            portfolio_status = "N/A"
            if hasattr(self.trading_bot, "portfolio_manager") and self.trading_bot.portfolio_manager:
                pm = self.trading_bot.portfolio_manager
                if hasattr(pm, "calcular_valor_portfolio_usd"):
                    total_value = pm.calcular_valor_portfolio_usd()
                elif hasattr(pm, "get_total_portfolio_value"):
                    total_value = pm.get_total_portfolio_value()
                else:
                    total_value = 0.0
                portfolio_status = f"${total_value:,.2f} USD"

            msg = format_status(
                bot_running=bot_running,
                portfolio_status=portfolio_status,
                strategies_status=strategies_status,
                alerts_enabled=self.alerts_enabled,
            )
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error(f"[TELEGRAM] Error in cmd_status: {e}")
            await update.message.reply_text(f"[ERROR] {str(e)}")

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /stats."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return
        try:
            stats = await self._calculate_statistics()
            await update.message.reply_text(format_stats(stats))
        except Exception as e:
            await update.message.reply_text(f"[ERROR] {str(e)}")

    async def cmd_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /pnl."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return
        try:
            pnl_data = await self._get_pnl_breakdown()
            await update.message.reply_text(format_pnl(pnl_data))
        except Exception as e:
            await update.message.reply_text(f"[ERROR] {str(e)}")

    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /positions."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return
        try:
            positions = await self._get_current_positions()
            await update.message.reply_text(format_positions(positions))
        except Exception as e:
            await update.message.reply_text(f"[ERROR] {str(e)}")

    async def cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /trades."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return
        try:
            recent_trades = await self._get_recent_trades(limit=5)
            await update.message.reply_text(format_trades(recent_trades))
        except Exception as e:
            await update.message.reply_text(f"[ERROR] {str(e)}")

    async def cmd_start_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /startbot - Inicia el loop de estrategias del bot."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return

        try:
            if getattr(self.trading_bot, "running", False):
                await update.message.reply_text("[INFO] Bot ya está corriendo.")
                return

            self.trading_bot.running = True
            if hasattr(self.trading_bot, "run_strategies_loop"):
                asyncio.create_task(self.trading_bot.run_strategies_loop())
            elif hasattr(self.trading_bot, "run"):
                asyncio.create_task(self.trading_bot.run())

            await update.message.reply_text(
                "[SUCCESS]\n\nBot iniciado correctamente.\nUse /status para ver el estado."
            )
        except Exception as e:
            await update.message.reply_text(f"[ERROR] {str(e)}")

    async def cmd_stop_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /stopbot - Detiene el loop y cierra posiciones."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return

        try:
            if hasattr(self.trading_bot, "running"):
                self.trading_bot.running = False

            await update.message.reply_text(
                "[SUCCESS]\n\nBot detenido.\nCerrando posiciones abiertas..."
            )
            if hasattr(self.trading_bot, "close_all_positions"):
                await self.trading_bot.close_all_positions()
        except Exception as e:
            await update.message.reply_text(f"[ERROR] {str(e)}")

    async def cmd_pause_strategies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /pause."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return

        try:
            if hasattr(self.trading_bot, "stat_arb_strategy") and self.trading_bot.stat_arb_strategy:
                self.trading_bot.stat_arb_strategy.enabled = False
            if hasattr(self.trading_bot, "market_making_strategy") and self.trading_bot.market_making_strategy:
                self.trading_bot.market_making_strategy.enabled = False
            await update.message.reply_text(
                "[SUCCESS]\n\nTodas las estrategias pausadas.\nUse /resume para reanudar."
            )
        except Exception as e:
            await update.message.reply_text(f"[ERROR] {str(e)}")

    async def cmd_resume_strategies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /resume."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return

        try:
            if hasattr(self.trading_bot, "stat_arb_strategy") and self.trading_bot.stat_arb_strategy:
                self.trading_bot.stat_arb_strategy.enabled = True
            if hasattr(self.trading_bot, "market_making_strategy") and self.trading_bot.market_making_strategy:
                self.trading_bot.market_making_strategy.enabled = True
            await update.message.reply_text("[SUCCESS]\n\nEstrategias reanudadas.")
        except Exception as e:
            await update.message.reply_text(f"[ERROR] {str(e)}")

    async def cmd_strategies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /strategies - Muestra parámetros reales de cada estrategia."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return

        try:
            strategies_info = []
            if hasattr(self.trading_bot, "stat_arb_strategy") and self.trading_bot.stat_arb_strategy:
                s = self.trading_bot.stat_arb_strategy
                z_entry = getattr(s, "z_score_entry", getattr(s, "z_entry_threshold", 2.0))
                z_exit = getattr(s, "z_score_exit", getattr(s, "z_exit_threshold", 0.5))
                strategies_info.append({
                    "name": "Statistical Arbitrage",
                    "status": "ENABLED" if getattr(s, "enabled", False) else "DISABLED",
                    "allocation": f"{getattr(s, 'allocation_pct', 0.4) * 100:.1f}%",
                    "extra": {"Z-Entry": z_entry, "Z-Exit": z_exit},
                })

            if hasattr(self.trading_bot, "market_making_strategy") and self.trading_bot.market_making_strategy:
                s = self.trading_bot.market_making_strategy
                strategies_info.append({
                    "name": "Market Making",
                    "status": "ENABLED" if getattr(s, "enabled", False) else "DISABLED",
                    "allocation": f"{getattr(s, 'allocation_pct', 0.3) * 100:.1f}%",
                    "extra": {
                        "Spread Target": f"{getattr(s, 'target_spread_bps', 50)} bps",
                        "Gamma": getattr(s, "gamma", 0.1),
                    },
                })

            await update.message.reply_text(format_strategies(strategies_info))
        except Exception as e:
            await update.message.reply_text(f"[ERROR] {str(e)}")

    async def cmd_enable_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /enable <strategy>."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return

        if not context.args:
            await update.message.reply_text(
                "[ERROR]\n\nUso: /enable <strategy>\nEstrategias disponibles: stat_arb, market_making"
            )
            return

        strategy_name = context.args[0].lower()
        if strategy_name == "stat_arb" and hasattr(self.trading_bot, "stat_arb_strategy"):
            self.trading_bot.stat_arb_strategy.enabled = True
            await update.message.reply_text("[SUCCESS] Statistical Arbitrage enabled")
        elif strategy_name == "market_making" and hasattr(self.trading_bot, "market_making_strategy"):
            self.trading_bot.market_making_strategy.enabled = True
            await update.message.reply_text("[SUCCESS] Market Making enabled")
        else:
            await update.message.reply_text(f"[ERROR] Estrategia '{strategy_name}' no encontrada")

    async def cmd_disable_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /disable <strategy>."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return

        if not context.args:
            await update.message.reply_text(
                "[ERROR]\n\nUso: /disable <strategy>\nEstrategias disponibles: stat_arb, market_making"
            )
            return

        strategy_name = context.args[0].lower()
        if strategy_name == "stat_arb" and hasattr(self.trading_bot, "stat_arb_strategy"):
            self.trading_bot.stat_arb_strategy.enabled = False
            await update.message.reply_text("[SUCCESS] Statistical Arbitrage disabled")
        elif strategy_name == "market_making" and hasattr(self.trading_bot, "market_making_strategy"):
            self.trading_bot.market_making_strategy.enabled = False
            await update.message.reply_text("[SUCCESS] Market Making disabled")
        else:
            await update.message.reply_text(f"[ERROR] Estrategia '{strategy_name}' no encontrada")

    async def cmd_reload_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /reload."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return
        try:
            if hasattr(self.trading_bot, "reload_config"):
                await self.trading_bot.reload_config()
                await update.message.reply_text("[SUCCESS] Configuración recargada")
            else:
                await update.message.reply_text("[ERROR] Función reload_config no disponible")
        except Exception as e:
            await update.message.reply_text(f"[ERROR] {str(e)}")

    async def cmd_trigger_backtest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /backtest - Ejecuta BacktesterEngine real y envía métricas."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return

        await update.message.reply_text(
            "🔄 [BACKTEST INICIADO]\n\n"
            "Ejecutando motor cuantitativo BacktesterEngine...\n"
            "Recibirás las métricas calculadas en instantes."
        )
        asyncio.create_task(self._run_backtest_task_enhanced(update.effective_chat.id))

    async def cmd_start_data_collection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /collect."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return
        try:
            data_dir = PROJECT_ROOT / "data" / "historical"
            files = list(data_dir.glob("ripio_*.csv")) if data_dir.exists() else []
            await update.message.reply_text(format_data_collection(files))
        except Exception as e:
            await update.message.reply_text(f"❌ [ERROR] {str(e)}")

    async def cmd_toggle_alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /alerts."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return
        self.alerts_enabled = not self.alerts_enabled
        status = "ON 🔔" if self.alerts_enabled else "OFF 🔕"
        await update.message.reply_text(f"[ALERTS] Alertas: {status}")

    async def cmd_alerts_on(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /alertson."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return
        self.alerts_enabled = True
        await update.message.reply_text("[ALERTS] Alertas activadas ✅")

    async def cmd_alerts_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /alertsoff."""
        if not self._check_authorization(update.effective_user.id):
            await self._send_unauthorized(update)
            return
        self.alerts_enabled = False
        await update.message.reply_text("[ALERTS] Alertas desactivadas 🔕")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para botones inline."""
        if update.callback_query:
            await update.callback_query.answer()

    async def _run_backtest_task_enhanced(self, chat_id: int):
        """Ejecuta `BacktesterEngine` sobre datos históricos o sintéticos y envía el reporte."""
        try:
            from analytics.backtester import BacktesterEngine
            from analytics.data_loader import DataLoader
            from run_backtest import SimpleMeanReversionStrategy

            data_dir = PROJECT_ROOT / "data" / "historical"
            files = list(data_dir.glob("ripio_*.csv")) if data_dir.exists() else []
            loader = DataLoader()

            if files:
                dfs = [pd.read_csv(f) for f in sorted(files)]
                df_full = pd.concat(dfs, ignore_index=True)
                file_count = len(files)
            else:
                df_full = loader.generate_synthetic_data(pair="USDT_ARS")
                file_count = 30

            strategy = SimpleMeanReversionStrategy(lookback=20, z_threshold=2.0)
            engine = BacktesterEngine(strategy=strategy, historical_data=df_full)
            bt_res = engine.run()
            m = bt_res["metrics"]

            live_stats = await self._calculate_statistics()
            try:
                sharpe_live = float(live_stats.get("sharpe_7d", 0.0))
            except (TypeError, ValueError):
                sharpe_live = m["sharpe_ratio"]

            sharpe_bt = m["sharpe_ratio"]
            degradation = (
                max(0.0, ((sharpe_bt - sharpe_live) / sharpe_bt) * 100.0)
                if sharpe_bt > 0
                else 0.0
            )

            metrics_payload = {
                "sharpe": sharpe_bt,
                "win_rate": m["win_rate"],
                "max_drawdown": m["max_drawdown_pct"],
                "total_trades": m["num_trades"],
                "avg_trade": m["avg_pnl_per_trade"],
                "sharpe_live": sharpe_live,
                "degradation": degradation,
            }

            result_msg = format_backtest_completed(
                file_count=file_count,
                total_rows=len(df_full),
                metrics=metrics_payload,
            )
            await self.app.bot.send_message(chat_id=chat_id, text=result_msg)

        except Exception as e:
            logger.error(f"[TELEGRAM] Error in backtest task: {e}")
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ [ERROR]\n\nError ejecutando backtest:\n{str(e)}",
            )
