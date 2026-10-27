"""
Sistema de automatización, monitoreo de degradación de alfa y mantenimiento semanal.
Ejecuta chequeos horarios de salud, backtests automáticos y pausas preventivas por drawdown.
Referencia de diseño: docs/STRATEGY_DEGRADATION.md
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class AutomationManager:
    """Gestor de mantenimiento automático y detección de degradación de estrategias."""

    def __init__(self, trading_bot, telegram_bot):
        self.trading_bot = trading_bot
        self.telegram_bot = telegram_bot

        self.weekly_check_day = 1
        self.weekly_check_hour = 9
        self.last_weekly_check: Optional[datetime] = None

        self.sharpe_warning_threshold = 1.5
        self.sharpe_critical_threshold = 1.0
        self.drawdown_warning_threshold = 0.10
        self.drawdown_critical_threshold = 0.15

        logger.info("[AUTOMATION] Manager initialized")

    async def start_automation_loop(self):
        """Loop continuo de monitoreo horario y mantenimiento semanal."""
        logger.info("[AUTOMATION] Starting automation loop...")
        while True:
            try:
                await self.daily_health_check()
                if self._should_run_weekly_check():
                    await self.weekly_maintenance()
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[AUTOMATION] Error in loop: {e}")
                await asyncio.sleep(3600)

    def _should_run_weekly_check(self) -> bool:
        """Determina si corresponde ejecutar el mantenimiento semanal."""
        now = datetime.now()
        if self.last_weekly_check is None:
            return True
        if now.weekday() == self.weekly_check_day and now.hour == self.weekly_check_hour:
            if self.last_weekly_check.date() < now.date():
                return True
        return False

    async def daily_health_check(self):
        """Evalúa métricas operativas actuales y dispara alertas si violan umbrales."""
        try:
            stats = await self._calculate_current_stats()
            alerts = self._check_thresholds(stats)
            if alerts:
                await self._send_health_alerts(alerts)
        except Exception as e:
            logger.error(f"[AUTOMATION] Error in daily health check: {e}")

    async def weekly_maintenance(self):
        """Ejecuta auditoría semanal de datos, backtest y comparación contra live."""
        self.last_weekly_check = datetime.now()
        await self.telegram_bot.send_alert(
            "[MANTENIMIENTO SEMANAL]\n\nIniciando verificación automática..."
        )
        try:
            data_status = await self._check_historical_data()
            backtest_results = await self._run_automatic_backtest()
            comparison = await self._compare_backtest_vs_live(backtest_results)
            recommendations = self._generate_recommendations(comparison)
            await self._send_weekly_report(
                data_status, backtest_results, comparison, recommendations
            )
        except Exception as e:
            logger.error(f"[AUTOMATION] Error in weekly maintenance: {e}")
            await self.telegram_bot.send_alert(f"[ERROR]\n\nError en mantenimiento semanal:\n{e}")

    async def _calculate_current_stats(self) -> Dict:
        """Calcula métricas reales leyendo `trades_history` o `trades_dia`."""
        stats = {
            "sharpe_7d": 0.0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "avg_trade_duration": 0.0,
        }
        try:
            if hasattr(self.trading_bot, "state_manager") and self.trading_bot.state_manager:
                state = self.trading_bot.state_manager.state
                trades = state.get("trades_history") or state.get("trades_dia", [])
                if trades:
                    stats["total_trades"] = len(trades)
                    stats["total_pnl"] = sum(float(t.get("pnl", 0.0)) for t in trades)
                    winning = sum(1 for t in trades if float(t.get("pnl", 0.0)) > 0)
                    stats["win_rate"] = (winning / len(trades)) * 100.0

                    week_ago = datetime.now() - timedelta(days=7)
                    week_trades = [
                        t for t in trades
                        if t.get("timestamp") and datetime.fromisoformat(str(t["timestamp"])) > week_ago
                    ]
                    if len(week_trades) > 1:
                        returns = [float(t.get("pnl", 0.0)) for t in week_trades]
                        mean_r = sum(returns) / len(returns)
                        std_r = (sum((r - mean_r) ** 2 for r in returns) / len(returns)) ** 0.5
                        if std_r > 0:
                            stats["sharpe_7d"] = (mean_r / std_r) * (252.0 ** 0.5)

                    base_cap = float(state.get("capital", 1000.0) or 1000.0)
                    equity = base_cap
                    peak = base_cap
                    max_dd = 0.0
                    for trade in sorted(trades, key=lambda t: str(t.get("timestamp", ""))):
                        equity += float(trade.get("pnl", 0.0))
                        if equity > peak:
                            peak = equity
                        dd = (peak - equity) / peak if peak > 0 else 0.0
                        max_dd = max(max_dd, dd)
                    stats["max_drawdown"] = max_dd
        except Exception as e:
            logger.error(f"[AUTOMATION] Error calculating stats: {e}")

        return stats

    def _check_thresholds(self, stats: Dict) -> List[Dict]:
        """Verifica si el Sharpe Ratio o el Max Drawdown violan límites de seguridad."""
        alerts = []
        sharpe = stats.get("sharpe_7d", 0.0)
        if 0 < sharpe < self.sharpe_critical_threshold:
            alerts.append({
                "level": "CRITICAL",
                "metric": "Sharpe Ratio",
                "value": sharpe,
                "threshold": self.sharpe_critical_threshold,
                "message": f"Sharpe muy bajo: {sharpe:.2f} (umbral: {self.sharpe_critical_threshold})",
                "action": "Pausar estrategias y revisar",
            })
        elif 0 < sharpe < self.sharpe_warning_threshold:
            alerts.append({
                "level": "WARNING",
                "metric": "Sharpe Ratio",
                "value": sharpe,
                "threshold": self.sharpe_warning_threshold,
                "message": f"Sharpe bajando: {sharpe:.2f} (objetivo: >{self.sharpe_warning_threshold})",
                "action": "Monitorear de cerca",
            })

        dd = stats.get("max_drawdown", 0.0)
        if dd > self.drawdown_critical_threshold:
            alerts.append({
                "level": "CRITICAL",
                "metric": "Max Drawdown",
                "value": dd,
                "threshold": self.drawdown_critical_threshold,
                "message": f"Drawdown crítico: {dd * 100:.1f}% (límite: {self.drawdown_critical_threshold * 100:.1f}%)",
                "action": "DETENER BOT INMEDIATAMENTE",
            })
        elif dd > self.drawdown_warning_threshold:
            alerts.append({
                "level": "WARNING",
                "metric": "Max Drawdown",
                "value": dd,
                "threshold": self.drawdown_warning_threshold,
                "message": f"Drawdown elevado: {dd * 100:.1f}% (alerta: {self.drawdown_warning_threshold * 100:.1f}%)",
                "action": "Reducir tamaño de posiciones",
            })
        return alerts

    async def _send_health_alerts(self, alerts: List[Dict]):
        """Envía alertas por Telegram y pausa estrategias ante drawdown crítico."""
        for alert in alerts:
            emoji = "🔴" if alert["level"] == "CRITICAL" else "⚠️"
            msg = (
                f"{emoji} [{alert['level']}]\n\n"
                f"Métrica: {alert['metric']}\n{alert['message']}\n\n"
                f"Acción recomendada:\n{alert['action']}"
            )
            await self.telegram_bot.send_alert(msg)

            if alert["level"] == "CRITICAL" and alert["metric"] == "Max Drawdown":
                if hasattr(self.trading_bot, "stat_arb_strategy") and self.trading_bot.stat_arb_strategy:
                    self.trading_bot.stat_arb_strategy.enabled = False
                if hasattr(self.trading_bot, "market_making_strategy") and self.trading_bot.market_making_strategy:
                    self.trading_bot.market_making_strategy.enabled = False
                await self.telegram_bot.send_alert(
                    "🛑 [AUTO-PAUSE]\n\nTodas las estrategias han sido pausadas automáticamente."
                )

    async def _check_historical_data(self) -> Dict:
        """Verifica disponibilidad de archivos históricos en `data/historical`."""
        data_dir = PROJECT_ROOT / "data" / "historical"
        data_status = {
            "total_files": 0,
            "total_days": 0,
            "last_update": None,
            "data_gaps": [],
            "status": "OK",
        }
        try:
            if data_dir.exists():
                files = list(data_dir.glob("ripio_*.csv"))
                data_status["total_files"] = len(files)
                data_status["total_days"] = len(files)
                if files:
                    latest = max(files, key=lambda f: f.stat().st_mtime)
                    data_status["last_update"] = datetime.fromtimestamp(
                        latest.stat().st_mtime
                    ).isoformat()
                if len(files) < 30:
                    data_status["status"] = "INSUFFICIENT"
                    data_status["message"] = f"Solo {len(files)} días de datos (óptimo 30)"
        except Exception as e:
            data_status["status"] = "ERROR"
            data_status["message"] = str(e)
        return data_status

    async def _run_automatic_backtest(self) -> Dict:
        """Ejecuta `BacktesterEngine` real sobre datos disponibles o sintéticos."""
        try:
            from analytics.backtester import BacktesterEngine
            from analytics.data_loader import DataLoader
            from run_backtest import SimpleMeanReversionStrategy

            data_dir = PROJECT_ROOT / "data" / "historical"
            files = list(data_dir.glob("ripio_*.csv")) if data_dir.exists() else []
            loader = DataLoader()

            if len(files) >= 1:
                dfs = [pd.read_csv(f) for f in sorted(files)]
                df_full = pd.concat(dfs, ignore_index=True)
            else:
                df_full = loader.generate_synthetic_data(pair="USDT_ARS")

            engine = BacktesterEngine(
                strategy=SimpleMeanReversionStrategy(),
                historical_data=df_full,
            )
            res = engine.run()
            m = res["metrics"]

            return {
                "status": "SUCCESS",
                "total_records": len(df_full),
                "date_range": f"{df_full['timestamp'].min()} - {df_full['timestamp'].max()}",
                "sharpe_backtest": m["sharpe_ratio"],
                "win_rate": m["win_rate"],
                "max_drawdown": m["max_drawdown_pct"],
                "total_trades": m["num_trades"],
                "message": "Backtest completado exitosamente",
            }
        except Exception as e:
            logger.error(f"[AUTOMATION] Error in automatic backtest: {e}")
            return {"status": "ERROR", "message": str(e)}

    async def _compare_backtest_vs_live(self, backtest_results: Dict) -> Dict:
        """Compara Sharpe de backtest vs Sharpe live para medir degradación."""
        comparison = {
            "sharpe_backtest": backtest_results.get("sharpe_backtest", 0.0),
            "sharpe_live": 0.0,
            "degradation_pct": 0.0,
            "status": "OK",
        }
        live_stats = await self._calculate_current_stats()
        comparison["sharpe_live"] = live_stats.get("sharpe_7d", 0.0)

        if comparison["sharpe_backtest"] > 0:
            deg = (comparison["sharpe_backtest"] - comparison["sharpe_live"]) / comparison[
                "sharpe_backtest"
            ]
            comparison["degradation_pct"] = deg * 100.0
            if deg > 0.50:
                comparison["status"] = "CRITICAL"
            elif deg > 0.30:
                comparison["status"] = "WARNING"
        return comparison

    def _generate_recommendations(self, comparison: Dict) -> List[str]:
        """Genera recomendaciones accionables según el porcentaje de degradación."""
        deg = comparison.get("degradation_pct", 0.0)
        if deg > 50:
            return [
                "🔴 URGENTE: Detener trading y revisar estrategia",
                "Acción: /stopbot y analizar cambios de régimen en el mercado",
            ]
        if deg > 30:
            return [
                "⚠️ Advertencia: Performance degradándose",
                "Acción: Reducir tamaño de posiciones y monitorear diariamente",
            ]
        return [
            "✅ Todo OK: Performance dentro de lo esperado",
            "Acción: Continuar operando normalmente",
        ]

    async def _send_weekly_report(
        self,
        data_status: Dict,
        backtest_results: Dict,
        comparison: Dict,
        recommendations: List[str],
    ):
        """Envía el informe semanal consolidado vía Telegram."""
        report = (
            f"📋 [REPORTE SEMANAL AUTOMÁTICO]\n{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"1️⃣ DATOS HISTÓRICOS: {data_status['status']} ({data_status['total_days']} días)\n\n"
            f"2️⃣ BACKTEST AUTOMÁTICO\n"
            f"Sharpe: {backtest_results.get('sharpe_backtest', 0.0):.2f} | "
            f"Win Rate: {backtest_results.get('win_rate', 0.0):.1f}% | "
            f"Trades: {backtest_results.get('total_trades', 0)}\n\n"
            f"3️⃣ DEGRADACIÓN LIVE vs BACKTEST: {comparison.get('degradation_pct', 0.0):.1f}%\n\n"
            "4️⃣ RECOMENDACIONES:\n" + "\n".join(recommendations)
        )
        await self.telegram_bot.send_alert(report)
