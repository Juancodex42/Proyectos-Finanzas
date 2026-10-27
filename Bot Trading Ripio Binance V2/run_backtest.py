"""
CLI de ejecución de backtesting cuantitativo, Walk-Forward y Monte Carlo.
Evalúa estrategias sobre datos históricos o sintéticos con test Luck-vs-Skill.
Referencia de diseño: docs/ARQUITECTURA.md
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from analytics import (
    BacktesterEngine,
    WalkForwardAnalyzer,
    MonteCarloSimulator,
    LuckVsSkillDetector,
    DataLoader,
    BacktestReporter,
)

log_dir = ROOT_DIR / "data" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(log_dir / "backtest.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


class SimpleBuyHoldStrategy:
    """Estrategia base Buy & Hold para comparación (benchmark)."""

    def __init__(self):
        self.position = None
        self.entry_price = None

    def on_data(self, row):
        price = BacktesterEngine.extract_price(row)
        if price is None:
            return None

        if self.position is None:
            self.position = "long"
            self.entry_price = price
            return {
                "action": "open_long",
                "position_size_usd": 1000.0,
                "reason": "Buy and hold",
            }
        return None


class SimpleMeanReversionStrategy:
    """Estrategia de reversión a la media basada en Z-score móvil."""

    def __init__(self, lookback: int = 20, z_threshold: float = 2.0):
        self.lookback = lookback
        self.z_threshold = z_threshold
        self.price_history = []
        self.position = None

    def on_data(self, row):
        price = BacktesterEngine.extract_price(row)
        if price is None:
            return None

        self.price_history.append(float(price))
        if len(self.price_history) < self.lookback:
            return None

        recent = self.price_history[-self.lookback:]
        mean = sum(recent) / len(recent)
        std = (sum((p - mean) ** 2 for p in recent) / len(recent)) ** 0.5
        if std <= 1e-12:
            return None

        z_score = (price - mean) / std

        if self.position is None:
            if z_score < -self.z_threshold:
                self.position = "long"
                return {
                    "action": "open_long",
                    "position_size_usd": 1000.0,
                    "reason": f"Mean reversion entry - Z-score: {z_score:.2f}",
                }
        else:
            if z_score > -0.2:
                self.position = None
                return {
                    "action": "close_long",
                    "position_size_usd": 1000.0,
                    "reason": f"Mean reversion exit - Z-score: {z_score:.2f}",
                }
        return None


def _build_strategy(args):
    """Instancia la estrategia solicitada por CLI."""
    if args.strategy == "buy_hold":
        return SimpleBuyHoldStrategy(), "Buy & Hold"
    if args.strategy in ("mean_reversion", "stat_arb"):
        return (
            SimpleMeanReversionStrategy(lookback=args.lookback, z_threshold=args.z_threshold),
            "Mean Reversion" if args.strategy == "mean_reversion" else "Statistical Arbitrage",
        )
    return SimpleMeanReversionStrategy(lookback=args.lookback, z_threshold=args.z_threshold), "Mean Reversion"


def _load_or_generate_data(args) -> pd.DataFrame:
    """Carga datos desde CSV o genera datos sintéticos si se solicita o no hay archivo."""
    loader = DataLoader()
    if not args.synthetic and args.data:
        df = loader.load_csv(args.data)
        if df is not None:
            return df
    return loader.generate_synthetic_data(
        pair="USDT_ARS",
        start_date=datetime.now() - timedelta(days=args.days),
        end_date=datetime.now(),
        freq="5min",
        initial_price=1500.0,
        volatility=0.02,
    )


async def run_basic_backtest(args, save_files: bool = True):
    """Ejecuta simulación histórica básica con reporte."""
    logger.info("=" * 80)
    logger.info("BACKTEST - Basic Historical Simulation")
    logger.info("=" * 80)

    df = _load_or_generate_data(args)
    strategy, strategy_name = _build_strategy(args)

    backtester = BacktesterEngine(
        strategy=strategy,
        historical_data=df,
        initial_capital=args.capital,
        maker_fee=0.0013,
        taker_fee=0.0030,
        slippage_bps=5.0,
    )
    result = backtester.run()

    reporter = BacktestReporter(output_dir=args.output_dir)
    reporter.print_report(result, strategy_name=strategy_name, save_to_file=save_files)

    if getattr(args, "export", False):
        reporter.export_trades_csv(result["trades"])
        reporter.export_equity_curve_csv(result["equity_curve"])

    return result


async def run_walk_forward(args):
    """Ejecuta validación Walk-Forward multi-fold."""
    logger.info("=" * 80)
    logger.info("BACKTEST - Walk-Forward Analysis")
    logger.info("=" * 80)

    df = _load_or_generate_data(args)
    strategy, _ = _build_strategy(args)

    wf_analyzer = WalkForwardAnalyzer(
        strategy=strategy,
        data=df,
        train_window_days=args.train_window,
        test_window_days=args.test_window,
        num_folds=args.num_folds,
    )
    result = wf_analyzer.run()

    print("\n" + "=" * 80)
    print("WALK-FORWARD ANALYSIS RESULTS")
    print("=" * 80)
    for fold in result["folds"]:
        print(
            f"  Fold {fold['fold']}: Sharpe={fold['metrics']['sharpe_ratio']:.2f} | "
            f"MaxDD={fold['metrics']['max_drawdown_pct']:.2f}% | "
            f"WinRate={fold['metrics']['win_rate']:.1f}%"
        )
    print("-" * 80)
    print(
        f"  AVERAGE: Sharpe={result['average']['sharpe_ratio']:.2f} | "
        f"MaxDD={result['average']['max_drawdown_pct']:.2f}% | "
        f"WinRate={result['average']['win_rate']:.1f}%"
    )
    print("=" * 80)
    return result


async def run_monte_carlo(args, trades_data=None, save_files: bool = True):
    """Ejecuta simulación Monte Carlo sobre los retornos de las operaciones."""
    if trades_data is None:
        bt_res = await run_basic_backtest(args, save_files=save_files)
        trades_data = bt_res["trades"]

    if not trades_data:
        logger.warning("[MONTE CARLO] No trades to analyze")
        return None

    returns = [t["pnl"] / args.capital for t in trades_data]
    mc_simulator = MonteCarloSimulator(
        returns=returns,
        num_simulations=args.simulations,
        confidence_level=0.95,
    )
    result = mc_simulator.run()
    reporter = BacktestReporter(output_dir=args.output_dir)
    reporter.print_monte_carlo_report(result, save_to_file=save_files)
    return result


async def run_luck_vs_skill(args, trades_data=None, save_files: bool = True):
    """Ejecuta test de permutación de signos de señales (Luck vs Skill)."""
    if trades_data is None:
        bt_res = await run_basic_backtest(args, save_files=save_files)
        trades_data = bt_res["trades"]

    if not trades_data:
        logger.warning("[LUCK vs SKILL] No trades to analyze")
        return None

    lvs_detector = LuckVsSkillDetector(
        trades=trades_data,
        num_permutations=args.permutations,
    )
    result = lvs_detector.run()
    reporter = BacktestReporter(output_dir=args.output_dir)
    reporter.print_luck_vs_skill_report(result, save_to_file=save_files)
    return result


async def run_full_analysis(args, save_files: bool = True):
    """Ejecuta suite completa: Backtest + Walk-Forward + Monte Carlo + Luck vs Skill."""
    bt_res = await run_basic_backtest(args, save_files=save_files)
    wf_res = await run_walk_forward(args)
    mc_res = await run_monte_carlo(args, trades_data=bt_res["trades"], save_files=save_files)
    lvs_res = await run_luck_vs_skill(args, trades_data=bt_res["trades"], save_files=save_files)
    return {
        "backtest": bt_res,
        "walk_forward": wf_res,
        "monte_carlo": mc_res,
        "luck_vs_skill": lvs_res,
    }


def main():
    parser = argparse.ArgumentParser(description="Backtest Trading Strategies")
    parser.add_argument(
        "--mode",
        choices=["basic", "walk_forward", "monte_carlo", "luck_vs_skill", "full"],
        default="full",
    )
    parser.add_argument(
        "--strategy",
        choices=["buy_hold", "mean_reversion", "stat_arb", "market_making"],
        default="mean_reversion",
    )
    parser.add_argument("--data", type=str, default=None)
    parser.add_argument("--synthetic", action="store_true", default=True)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--capital", type=float, default=10000.0)
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--z-threshold", type=float, default=2.0)
    parser.add_argument("--train-window", type=int, default=30)
    parser.add_argument("--test-window", type=int, default=7)
    parser.add_argument("--num-folds", type=int, default=4)
    parser.add_argument("--simulations", type=int, default=1000)
    parser.add_argument("--permutations", type=int, default=1000)
    parser.add_argument("--output-dir", type=str, default="reports")
    parser.add_argument("--export", action="store_true")

    args = parser.parse_args()

    if args.mode == "basic":
        asyncio.run(run_basic_backtest(args))
    elif args.mode == "walk_forward":
        asyncio.run(run_walk_forward(args))
    elif args.mode == "monte_carlo":
        asyncio.run(run_monte_carlo(args))
    elif args.mode == "luck_vs_skill":
        asyncio.run(run_luck_vs_skill(args))
    elif args.mode == "full":
        asyncio.run(run_full_analysis(args))


if __name__ == "__main__":
    main()
