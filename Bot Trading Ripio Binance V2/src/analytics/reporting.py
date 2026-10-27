"""
Módulo de generación de reportes cuantitativos y exportación de métricas.
Calcula ratios de riesgo (Sortino, VaR, CVaR, Calmar) y exporta resultados a CSV/TXT.
Referencia de diseño: docs/ARQUITECTURA.md
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
import numpy as np
import pandas as pd

from domain.quant_math import sortino_ratio, max_drawdown

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class BacktestReporter:
    """Genera reportes de performance, Monte Carlo y Luck-vs-Skill."""

    def __init__(self, output_dir: Optional[Union[str, Path]] = None):
        self.output_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[REPORTER] Initialized - Output dir: {self.output_dir}")

    def generate_summary_report(
        self,
        metrics: Dict,
        trades: List[Dict],
        strategy_name: str = "Strategy",
    ) -> str:
        """Genera un reporte tabular con métricas de rendimiento, operaciones y riesgo."""
        report = [
            "=" * 80,
            f"BACKTEST REPORT - {strategy_name}",
            "=" * 80,
            "",
            "PERFORMANCE METRICS",
            "-" * 80,
            f"Total Return:          {metrics.get('total_return_pct', 0.0):.2f}%",
            f"Sharpe Ratio:          {metrics.get('sharpe_ratio', 0.0):.2f}",
            f"Sortino Ratio:         {metrics.get('sortino_ratio', 0.0):.2f}",
            f"Max Drawdown:          {metrics.get('max_drawdown_pct', 0.0):.2f}%",
            f"Win Rate:              {metrics.get('win_rate', 0.0):.1f}%",
            f"Total Trades:          {metrics.get('num_trades', 0)}",
            "",
        ]

        if trades:
            pnls = [float(t.get("pnl", 0.0)) for t in trades]
            winning = [p for p in pnls if p > 0]
            losing = [p for p in pnls if p < 0]
            total_fees = sum(float(t.get("fee_cost", 0.0)) for t in trades)

            report.extend([
                "TRADE STATISTICS",
                "-" * 80,
                f"Avg P&L per Trade:     ${np.mean(pnls):.2f}",
                f"Avg Winning Trade:     ${np.mean(winning) if winning else 0.0:.2f}",
                f"Avg Losing Trade:      ${np.mean(losing) if losing else 0.0:.2f}",
                f"Best Trade:            ${max(pnls):.2f}",
                f"Worst Trade:           ${min(pnls):.2f}",
                f"Total Fees Paid:       ${total_fees:.2f}",
                f"Profit Factor:         {metrics.get('profit_factor', 0.0):.2f}",
                "",
            ])

        report.extend([
            "RISK METRICS",
            "-" * 80,
            f"Volatility (Annual):   {metrics.get('annual_volatility', 0.0):.2f}%",
            f"VaR (95%):             ${metrics.get('var_95', 0.0):.2f}",
            f"CVaR (95%):            ${metrics.get('cvar_95', 0.0):.2f}",
            f"Calmar Ratio:          {metrics.get('calmar_ratio', 0.0):.2f}",
            "",
            "=" * 80,
            f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 80,
        ])
        return "\n".join(report)

    def calculate_additional_metrics(
        self,
        trades: List[Dict],
        equity_curve: List[Dict],
        initial_capital: float,
    ) -> Dict:
        """Calcula Sortino, volatilidad anualizada, Profit Factor, VaR 95%, CVaR y Calmar."""
        metrics: Dict[str, float] = {}
        if not trades:
            return metrics

        pnls = np.asarray([float(t.get("pnl", 0.0)) for t in trades], dtype=float)
        returns = []
        for i in range(1, len(equity_curve)):
            prev_cap = equity_curve[i - 1]["capital"]
            curr_cap = equity_curve[i]["capital"]
            if prev_cap > 0:
                returns.append((curr_cap - prev_cap) / prev_cap)

        if returns:
            metrics["sortino_ratio"] = sortino_ratio(returns, periods_per_year=252.0)
            metrics["annual_volatility"] = float(np.std(returns) * np.sqrt(252.0) * 100.0)

        winning_pnl = float(pnls[pnls > 0].sum())
        losing_pnl = float(abs(pnls[pnls < 0].sum()))
        if losing_pnl > 0:
            metrics["profit_factor"] = winning_pnl / losing_pnl
        else:
            metrics["profit_factor"] = float("inf") if winning_pnl > 0 else 0.0

        if pnls.size > 0:
            var_95 = float(np.percentile(pnls, 5))
            cvar_95 = float(pnls[pnls <= var_95].mean()) if (pnls <= var_95).any() else var_95
            metrics["var_95"] = var_95
            metrics["cvar_95"] = cvar_95

        final_capital = equity_curve[-1]["capital"] if equity_curve else initial_capital
        total_return = (final_capital - initial_capital) / initial_capital if initial_capital > 0 else 0.0
        max_dd_pct = max_drawdown([p["capital"] for p in equity_curve])
        max_dd_frac = max_dd_pct / 100.0
        metrics["calmar_ratio"] = float(total_return / max_dd_frac) if max_dd_frac > 0 else 0.0

        return metrics

    def print_report(
        self,
        backtest_result: Dict,
        strategy_name: str = "Strategy",
        save_to_file: bool = True,
    ):
        """Imprime el reporte de backtest en consola y opcionalmente lo guarda en disco."""
        metrics = backtest_result.get("metrics", {})
        trades = backtest_result.get("trades", [])
        equity_curve = backtest_result.get("equity_curve", [])

        initial_capital = equity_curve[0]["capital"] if equity_curve else 10000.0
        additional = self.calculate_additional_metrics(trades, equity_curve, initial_capital)
        all_metrics = {**metrics, **additional}

        report = self.generate_summary_report(all_metrics, trades, strategy_name)
        print("\n" + report)

        if save_to_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = strategy_name.replace(" ", "_")
            filename = f"backtest_report_{safe_name}_{timestamp}.txt"
            (self.output_dir / filename).write_text(report, encoding="utf-8")
            logger.info(f"[REPORTER] Report saved to {filename}")

    def print_monte_carlo_report(self, mc_result: Dict, save_to_file: bool = True):
        """Imprime y guarda resultados de simulación Monte Carlo."""
        report = "\n".join([
            "=" * 80,
            "MONTE CARLO SIMULATION REPORT",
            "=" * 80,
            "",
            "SHARPE RATIO DISTRIBUTION",
            "-" * 80,
            f"Mean Sharpe:           {mc_result['sharpe_mean']:.2f}",
            f"5th Percentile:        {mc_result['sharpe_5th_percentile']:.2f}",
            f"95th Percentile:       {mc_result['sharpe_95th_percentile']:.2f}",
            "",
            "PROBABILITY ANALYSIS",
            "-" * 80,
            f"P(Profitable):         {mc_result['prob_profitable']:.1f}%",
            f"P(Sharpe > 1.0):       {mc_result['prob_sharpe_gt_1']:.1f}%",
            "",
            "=" * 80,
        ])
        print("\n" + report)

        if save_to_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"monte_carlo_report_{timestamp}.txt"
            (self.output_dir / filename).write_text(report, encoding="utf-8")

    def print_luck_vs_skill_report(self, lvs_result: Dict, save_to_file: bool = True):
        """Imprime y guarda resultados del test de permutación Luck-vs-Skill."""
        sig_msg = (
            "[OK] Results are statistically significant"
            if lvs_result["p_value"] < 0.05
            else "[WARNING] Results may be due to random chance"
        )
        report = "\n".join([
            "=" * 80,
            "LUCK vs SKILL ANALYSIS",
            "=" * 80,
            "",
            "STATISTICAL SIGNIFICANCE",
            "-" * 80,
            f"T-Statistic:           {lvs_result['t_statistic']:.2f}",
            f"P-Value:               {lvs_result['p_value']:.4f}",
            "",
            "VERDICT",
            "-" * 80,
            f"{lvs_result['verdict']}",
            "",
            sig_msg,
            "",
            "=" * 80,
        ])
        print("\n" + report)

        if save_to_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"luck_vs_skill_report_{timestamp}.txt"
            (self.output_dir / filename).write_text(report, encoding="utf-8")

    def export_trades_csv(self, trades: List[Dict], filename: str = "trades.csv"):
        """Exporta el listado de trades cerrados a CSV."""
        if not trades:
            return
        pd.DataFrame(trades).to_csv(self.output_dir / filename, index=False)

    def export_equity_curve_csv(self, equity_curve: List[Dict], filename: str = "equity_curve.csv"):
        """Exporta la curva de capital Mark-to-Market a CSV."""
        if not equity_curve:
            return
        pd.DataFrame(equity_curve).to_csv(self.output_dir / filename, index=False)
