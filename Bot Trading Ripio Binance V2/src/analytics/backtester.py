"""
Motor de backtesting histórico y validación estadística de estrategias.
Ejecuta simulación con comisiones reales, Walk-Forward, Monte Carlo y Luck-vs-Skill.
Referencia de diseño: docs/ARQUITECTURA.md
"""

import copy
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from domain.models import TradeRecord
from domain.quant_math import (
    sharpe_ratio,
    sortino_ratio,
    max_drawdown,
    permutation_test_signals,
)

logger = logging.getLogger(__name__)


class BacktesterEngine:
    """
    Motor de backtesting con descuento real de comisiones (maker/taker),
    slippage, curva de capital Mark-to-Market y liquidación al cierre.
    """

    PRICE_COLUMNS = ("close", "price", "USDT_ARS_mid", "USDC_ARS_mid", "mid")

    def __init__(
        self,
        strategy,
        historical_data: pd.DataFrame,
        initial_capital: float = 10000.0,
        maker_fee: float = 0.0013,
        taker_fee: float = 0.0030,
        slippage_bps: float = 5.0,
        periods_per_year: float = 252.0,
    ):
        self.strategy = strategy
        self.data = historical_data
        self.initial_capital = float(initial_capital)
        self.maker_fee = float(maker_fee)
        self.taker_fee = float(taker_fee)
        self.slippage_bps = float(slippage_bps)
        self.periods_per_year = float(periods_per_year)

        self.capital = float(initial_capital)
        self.positions: List[Dict] = []
        self.trades: List[Dict] = []
        self.order_executions: List[Dict] = []
        self.equity_curve: List[Dict] = []

        logger.info(f"[BACKTEST] Engine initialized - Capital: ${self.initial_capital:,.2f}")

    @classmethod
    def extract_price(cls, row) -> Optional[float]:
        """Extrae el precio de referencia soportando formatos OHLCV y CSV de Ripio."""
        for col in cls.PRICE_COLUMNS:
            if col in row and row[col] is not None and not pd.isna(row[col]):
                return float(row[col])
        return None

    def apply_fees_and_slippage(
        self,
        price: float,
        size: float,
        side: str,
        order_type: str = "limit",
    ) -> Tuple[float, float]:
        """Aplica slippage al precio de ejecución y calcula el costo total con comisión."""
        fee = self.maker_fee if order_type == "limit" else self.taker_fee
        slippage_multiplier = 1.0 if order_type == "limit" else 2.0
        slippage_pct = (self.slippage_bps / 10000.0) * slippage_multiplier

        if side == "buy":
            price_final = price * (1.0 + slippage_pct)
            cost = size * (1.0 + fee)
        else:
            price_final = price * (1.0 - slippage_pct)
            cost = size * (1.0 - fee)

        return float(price_final), float(cost)

    def _calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calcula el P&L flotante de todas las posiciones abiertas al precio actual."""
        if not self.positions or current_price <= 0:
            return 0.0

        unrealized = 0.0
        for pos in self.positions:
            entry_price = pos["price"]
            size_usd = pos["size_usd"]
            if pos["type"] == "long":
                unrealized += (current_price / entry_price - 1.0) * size_usd
            else:
                unrealized += (entry_price / current_price - 1.0) * size_usd
        return float(unrealized)

    def execute_trade(
        self,
        timestamp,
        action: str,
        price: float,
        size_usd: float,
    ) -> Dict:
        """
        Ejecuta apertura o cierre de posición descontando comisiones reales.
        Registra en `self.trades` exclusivamente los trades cerrados (round-trip).
        """
        if "open" in action:
            side = "buy" if "long" in action else "sell"
            order_type = "limit"
            fee_rate = self.maker_fee
            price_final, cost_total = self.apply_fees_and_slippage(
                price, size_usd, side, order_type
            )
            entry_fee = size_usd * fee_rate
            self.capital -= entry_fee

            pos_type = "long" if "long" in action else "short"
            self.positions.append({
                "type": pos_type,
                "price": price_final,
                "raw_price": price,
                "size_usd": size_usd,
                "entry_fee": entry_fee,
                "timestamp": timestamp,
            })

            exec_event = {
                "timestamp": timestamp,
                "action": action,
                "price": price_final,
                "size_usd": size_usd,
                "cost": cost_total,
                "fee_cost": entry_fee,
                "gross_pnl": 0.0,
                "pnl": -entry_fee,
                "capital": self.capital,
            }
            self.order_executions.append(exec_event)
            return exec_event

        if "close" in action and self.positions:
            entry = self.positions.pop()
            pos_size = entry["size_usd"] if size_usd <= 0 else size_usd
            side = "sell" if entry["type"] == "long" else "buy"
            order_type = "market"
            fee_rate = self.taker_fee

            price_final, cost_total = self.apply_fees_and_slippage(
                price, pos_size, side, order_type
            )
            exit_fee = pos_size * fee_rate
            entry_fee = entry.get("entry_fee", pos_size * self.maker_fee)
            total_fee = entry_fee + exit_fee

            if entry["type"] == "long":
                gross_pnl = (price_final / entry["price"] - 1.0) * pos_size
            else:
                gross_pnl = (entry["price"] / price_final - 1.0) * pos_size

            # entry_fee ya fue descontado al abrir; descontamos exit_fee y sumamos gross_pnl
            self.capital += (gross_pnl - exit_fee)
            net_pnl = gross_pnl - total_fee

            trade_record = TradeRecord(
                timestamp=timestamp,
                action=action,
                price=price_final,
                size_usd=pos_size,
                cost=cost_total,
                pnl=net_pnl,
                capital=self.capital,
                gross_pnl=gross_pnl,
                fee_cost=total_fee,
                entry_price=entry["price"],
            ).to_dict()

            self.trades.append(trade_record)
            self.order_executions.append(trade_record)
            return trade_record

        return {}

    def run(self) -> Dict:
        """Ejecuta la simulación completa barra por barra con valoración Mark-to-Market."""
        logger.info(f"[BACKTEST] Starting - {len(self.data)} data points")

        for idx, row in self.data.iterrows():
            price = self.extract_price(row)
            ts = row["timestamp"] if "timestamp" in row else idx

            if price is not None and self.strategy and hasattr(self.strategy, "on_data"):
                try:
                    signal = self.strategy.on_data(row)
                    if signal:
                        action = signal.get("action", "")
                        size_usd = float(signal.get("position_size_usd", 100.0))
                        self.execute_trade(
                            timestamp=ts,
                            action=action,
                            price=price,
                            size_usd=size_usd,
                        )
                except Exception as e:
                    logger.error(f"[BACKTEST] Error executing strategy: {e}")

            unrealized = self._calculate_unrealized_pnl(price) if price is not None else 0.0
            mtm_equity = self.capital + unrealized
            self.equity_curve.append({
                "timestamp": ts,
                "capital": mtm_equity,
                "realized_capital": self.capital,
                "unrealized_pnl": unrealized,
            })

        # Liquidar posiciones abiertas al finalizar la serie histórica
        if self.positions and len(self.data) > 0:
            last_row = self.data.iloc[-1]
            last_price = self.extract_price(last_row)
            last_ts = last_row["timestamp"] if "timestamp" in last_row else len(self.data) - 1
            if last_price is not None:
                while self.positions:
                    pos = self.positions[-1]
                    close_action = "close_long" if pos["type"] == "long" else "close_short"
                    self.execute_trade(
                        timestamp=last_ts,
                        action=close_action,
                        price=last_price,
                        size_usd=pos["size_usd"],
                    )
                if self.equity_curve:
                    self.equity_curve[-1]["capital"] = self.capital
                    self.equity_curve[-1]["realized_capital"] = self.capital
                    self.equity_curve[-1]["unrealized_pnl"] = 0.0

        metrics = self.calculate_metrics()
        logger.info(f"[BACKTEST] Complete - Final capital: ${self.capital:,.2f}")
        logger.info(f"[BACKTEST] Total return: {metrics['total_return_pct']:.2f}%")
        logger.info(f"[BACKTEST] Sharpe ratio: {metrics['sharpe_ratio']:.2f}")
        logger.info(f"[BACKTEST] Total trades: {metrics['num_trades']}")

        return {
            "metrics": metrics,
            "trades": self.trades,
            "equity_curve": self.equity_curve,
        }

    def calculate_metrics(self) -> Dict:
        """Calcula métricas financieras sobre trades cerrados y curva Mark-to-Market."""
        closed_trades = [
            t for t in self.trades if str(t.get("action", "close")).startswith("close")
        ]
        equity_values = [p["capital"] for p in self.equity_curve]
        max_dd_pct = max_drawdown(equity_values) if equity_values else 0.0

        if not closed_trades:
            return {
                "total_return_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown_pct": max_dd_pct,
                "win_rate": 0.0,
                "num_trades": 0,
                "avg_pnl_per_trade": 0.0,
            }

        total_return_pct = ((self.capital - self.initial_capital) / self.initial_capital) * 100.0

        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_cap = self.equity_curve[i - 1]["capital"]
            curr_cap = self.equity_curve[i]["capital"]
            if prev_cap > 0:
                returns.append((curr_cap - prev_cap) / prev_cap)

        sharpe = sharpe_ratio(returns, periods_per_year=self.periods_per_year)
        sortino = sortino_ratio(returns, periods_per_year=self.periods_per_year)

        winning_trades = [t for t in closed_trades if t.get("pnl", 0.0) > 0]
        win_rate = (len(winning_trades) / len(closed_trades)) * 100.0
        avg_pnl = float(np.mean([t.get("pnl", 0.0) for t in closed_trades]))

        return {
            "total_return_pct": float(total_return_pct),
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "max_drawdown_pct": float(max_dd_pct),
            "win_rate": float(win_rate),
            "num_trades": len(closed_trades),
            "avg_pnl_per_trade": avg_pnl,
        }


class WalkForwardAnalyzer:
    """Análisis Walk-Forward dividiendo la serie temporal en ventanas sucesivas."""

    def __init__(
        self,
        strategy,
        data: pd.DataFrame,
        train_window_days: int = 30,
        test_window_days: int = 7,
        num_folds: int = 4,
    ):
        self.strategy = strategy
        self.data = data
        self.train_window = train_window_days
        self.test_window = test_window_days
        self.num_folds = max(1, num_folds)
        logger.info(f"[WALK FORWARD] Initialized - {self.num_folds} folds")

    def run(self) -> Dict:
        """Ejecuta validación temporal en cada fold con instancias frescas de estrategia."""
        results = []
        total_rows = len(self.data)
        fold_size = max(1, total_rows // self.num_folds)

        for i in range(self.num_folds):
            train_start = i * fold_size
            train_end = train_start + int(fold_size * 0.7)
            test_end = min((i + 1) * fold_size, total_rows)
            test_data = self.data.iloc[train_end:test_end]
            if test_data.empty:
                test_data = self.data.iloc[train_start:test_end]

            strat_copy = copy.deepcopy(self.strategy)
            backtester = BacktesterEngine(strategy=strat_copy, historical_data=test_data)
            fold_result = backtester.run()
            results.append({"fold": i + 1, "metrics": fold_result["metrics"]})

        avg_metrics = {
            "sharpe_ratio": float(np.mean([r["metrics"]["sharpe_ratio"] for r in results])),
            "max_drawdown_pct": float(np.mean([r["metrics"]["max_drawdown_pct"] for r in results])),
            "win_rate": float(np.mean([r["metrics"]["win_rate"] for r in results])),
            "total_return_pct": float(np.mean([r["metrics"]["total_return_pct"] for r in results])),
        }
        return {"folds": results, "average": avg_metrics}


class MonteCarloSimulator:
    """Simulador Monte Carlo mediante remuestreo bootstrap de retornos por operación."""

    def __init__(
        self,
        returns: List[float],
        num_simulations: int = 1000,
        confidence_level: float = 0.95,
        seed: Optional[int] = 42,
    ):
        self.returns = np.asarray(returns, dtype=float)
        self.num_simulations = num_simulations
        self.confidence_level = confidence_level
        self.seed = seed
        logger.info(f"[MONTE CARLO] Initialized - {num_simulations} simulations")

    def run(self) -> Dict:
        """Genera distribución empírica de Sharpe y retorno acumulado."""
        if len(self.returns) == 0:
            return {
                "sharpe_mean": 0.0,
                "sharpe_5th_percentile": 0.0,
                "sharpe_95th_percentile": 0.0,
                "sharpe_distribution": [],
                "prob_profitable": 0.0,
                "prob_sharpe_gt_1": 0.0,
            }

        rng = np.random.default_rng(self.seed)
        sharpe_ratios = []
        total_returns = []

        for _ in range(self.num_simulations):
            sampled = rng.choice(self.returns, size=len(self.returns), replace=True)
            std_ret = float(np.std(sampled))
            sharpe = float((np.mean(sampled) / std_ret) * np.sqrt(252.0)) if std_ret > 1e-12 else 0.0
            sharpe_ratios.append(sharpe)
            cum_ret = float(np.prod(1.0 + sampled) - 1.0)
            total_returns.append(cum_ret * 100.0)

        sharpe_arr = np.asarray(sharpe_ratios)
        ret_arr = np.asarray(total_returns)

        return {
            "sharpe_mean": float(np.mean(sharpe_arr)),
            "sharpe_5th_percentile": float(np.percentile(sharpe_arr, 5)),
            "sharpe_95th_percentile": float(np.percentile(sharpe_arr, 95)),
            "sharpe_distribution": sharpe_ratios,
            "prob_profitable": float((ret_arr > 0).mean() * 100.0),
            "prob_sharpe_gt_1": float((sharpe_arr > 1.0).mean() * 100.0),
        }


class LuckVsSkillDetector:
    """
    Detector estadístico Luck-vs-Skill mediante permutación aleatoria de signos de señales.
    Contrasta el P&L neto real contra entradas de dirección aleatoria descontando fees.
    """

    def __init__(
        self,
        trades: List[Dict],
        num_permutations: int = 1000,
        seed: Optional[int] = 42,
    ):
        self.trades = trades
        self.num_permutations = num_permutations
        self.seed = seed
        logger.info(f"[LUCK vs SKILL] Initialized - {num_permutations} permutations")

    def run(self) -> Dict:
        """Ejecuta test de permutación de signos y devuelve t-statistic, p-value y veredicto."""
        if not self.trades:
            return {
                "t_statistic": 0.0,
                "p_value": 1.0,
                "verdict": "BAJA CONFIANZA - Sin operaciones para evaluar",
            }

        gross_pnls = []
        fee_costs = []
        for t in self.trades:
            net_pnl = float(t.get("pnl", 0.0))
            fee = float(t.get("fee_cost", 0.0))
            gross = float(t.get("gross_pnl", net_pnl + fee))
            gross_pnls.append(gross)
            fee_costs.append(fee)

        res = permutation_test_signals(
            gross_pnls=gross_pnls,
            fee_costs=fee_costs,
            num_permutations=self.num_permutations,
            seed=self.seed,
        )
        t_stat = res["t_statistic"]
        p_value = res["p_value"]

        if p_value < 0.01 and res["real_mean"] > 0:
            verdict = "ALTA CONFIANZA - Ventaja estadística real"
        elif p_value < 0.05 and res["real_mean"] > 0:
            verdict = "MODERADA CONFIANZA - Posible ventaja"
        else:
            verdict = "BAJA CONFIANZA - Puede ser suerte"

        logger.info(f"[LUCK vs SKILL] T-statistic: {t_stat:.2f}, P-value: {p_value:.4f}")
        return {
            "t_statistic": float(t_stat),
            "p_value": float(p_value),
            "real_mean": res["real_mean"],
            "null_mean": res["null_mean"],
            "verdict": verdict,
        }
