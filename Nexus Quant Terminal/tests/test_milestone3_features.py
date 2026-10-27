import unittest
import numpy as np
import pandas as pd
import optuna

from engine.optimizer_optuna import OptunaStrategyOptimizer, OptunaSearchSpace, calculate_wilson_lower_bound
from engine.auto_tuner import WalkForwardEngine
from engine.simulator import BinarySimulator, VectorizedBinarySimulator
from engine.optimizer import ParallelOptimizer, monte_carlo_vectorized_2d
from strategies.base import BaseStrategy


class DummyStrategy(BaseStrategy):
    """Simple deterministic strategy for testing Optuna and WFO optimization."""

    def get_params_schema(self) -> dict:
        return {"rsi_period": "int", "wick_ratio": "float"}

    def prepare_data(self, df: pd.DataFrame) -> dict:
        close = df['close']
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(14, min_periods=1).mean()
        avg_loss = loss.rolling(14, min_periods=1).mean()
        rs = avg_gain / (avg_loss + 1e-8)
        rsi = 100 - (100 / (1 + rs))
        return {"rsi": rsi}

    def generate_signals(self, df: pd.DataFrame, params: dict, precomputed: dict = None) -> pd.Series:
        signals = pd.Series(index=df.index, dtype=object)
        rsi_period = params.get("rsi_period", 14)
        if precomputed and "rsi" in precomputed:
            rsi = precomputed["rsi"]
        else:
            rsi = self.prepare_data(df)["rsi"]

        # Signal condition: CALL when RSI < 40, PUT when RSI > 60
        signals[rsi < (30 + rsi_period % 15)] = 'CALL'
        signals[rsi > (70 - rsi_period % 15)] = 'PUT'
        return signals


class TestMilestone3Features(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=600, freq='5min')
        prices = 100.0 + np.cumsum(np.random.randn(600) * 0.2)
        self.df = pd.DataFrame({
            'open_time': (dates.astype(np.int64) // 10**6).values,
            'open': prices,
            'high': prices + np.abs(np.random.randn(600) * 0.3),
            'low': prices - np.abs(np.random.randn(600) * 0.3),
            'close': prices + np.random.randn(600) * 0.1,
            'volume': np.random.randint(10, 100, size=600)
        }, index=dates)

    # -------------------------------------------------------------
    # Feature 12 Tests: Optuna Framework Integration
    # -------------------------------------------------------------
    def test_optuna_strategy_optimizer_execution(self):
        optimizer = OptunaStrategyOptimizer(
            payout=0.85,
            target_win_rate=0.65,
            min_trades=5,
            n_splits=3
        )
        res = optimizer.optimize(
            df=self.df,
            strategy_cls=DummyStrategy,
            strategy_name="generic",
            n_trials=10,
            timeout=30,
            n_jobs=1
        )

        self.assertIn("best_params", res)
        self.assertIn("best_value", res)
        self.assertIn("param_importances", res)
        self.assertIn("total_trials", res)
        self.assertIn("completed_trials", res)
        self.assertIn("trials_df", res)
        self.assertIn("oos_verification", res)

        self.assertGreater(res["total_trials"], 0)
        self.assertIsInstance(res["param_importances"], dict)

    def test_wilson_lower_bound_calculation(self):
        # 70 wins out of 100 trades
        wilson_70 = calculate_wilson_lower_bound(70, 100)
        self.assertGreater(wilson_70, 0.5405)  # Should exceed breakeven 54.05%
        self.assertLess(wilson_70, 0.70)

        # 0 wins
        self.assertEqual(calculate_wilson_lower_bound(0, 50), 0.0)

    # -------------------------------------------------------------
    # Feature 13 Tests: Multi-Dimensional Search Space Design
    # -------------------------------------------------------------
    def test_multi_dimensional_search_space_sampling(self):
        study = optuna.create_study(direction="maximize")
        trial = study.ask()

        params = OptunaSearchSpace.sample_strategy_space("bollinger_bounce", trial)
        self.assertIn("expiry_candles", params)
        self.assertIn("session_filter", params)
        self.assertIn("exclude_weekends", params)
        self.assertIn("meta_threshold", params)
        self.assertIn("regime_breakeven", params)
        self.assertIn("bb_period", params)
        self.assertIn("bb_std", params)

        self.assertGreaterEqual(params["expiry_candles"], 1)
        self.assertLessEqual(params["expiry_candles"], 12)
        self.assertIn(params["session_filter"], ["ALL", "ASIAN", "LONDON", "NEW_YORK", "OVERLAP_LDN_NY"])
        self.assertGreaterEqual(params["meta_threshold"], 0.50)
        self.assertLessEqual(params["meta_threshold"], 0.90)

    # -------------------------------------------------------------
    # Feature 14 Tests: True Walk-Forward Optimization Engine
    # -------------------------------------------------------------
    def test_walk_forward_engine_rolling_optuna(self):
        wfe = WalkForwardEngine(
            n_windows=3,
            train_ratio=0.60,
            n_trials_per_window=10,
            min_is_trades=1,
            min_oos_trades=1,
            target_winrate=0.45
        )

        def dummy_space(trial):
            return {
                "rsi_period": trial.suggest_int("rsi_period", 5, 25),
                "wick_ratio": trial.suggest_float("wick_ratio", 0.1, 0.5)
            }

        res = wfe.run_wfa(
            df=self.df,
            strat_class=DummyStrategy,
            param_space_fn=dummy_space,
            expiry=2,
            payout=0.85
        )

        self.assertIn("wfe", res)
        self.assertIn("mean_is_wr", res)
        self.assertIn("mean_oos_wr", res)
        self.assertIn("global_oos_wr", res)
        self.assertIn("global_oos_wr_wilson_low", res)
        self.assertIn("global_oos_ev", res)
        self.assertIn("stable_windows", res)
        self.assertIn("window_results", res)

        self.assertGreaterEqual(res["total_windows_tested"], 1)
        for w in res["window_results"]:
            self.assertIn("best_params", w)
            self.assertIn("is_stable", w)

    # -------------------------------------------------------------
    # Feature 15 Tests: Backtest Engine Parallel Vectorization
    # -------------------------------------------------------------
    def test_vectorized_binary_simulator_parity(self):
        strat = DummyStrategy()
        params = {"rsi_period": 14}
        pre = strat.prepare_data(self.df)
        sigs = strat.generate_signals(self.df, params=params, precomputed=pre)

        # Standard simulator
        sim_standard = BinarySimulator().run(self.df, sigs, expiry_candles=2, payout=0.85, bet_fraction=0.01)
        sum_standard = sim_standard["summary"]

        # Vectorized simulator
        sum_fast = VectorizedBinarySimulator.run_fast(self.df, sigs, expiry_candles=2, payout=0.85, bet_fraction=0.01)["summary"]

        self.assertEqual(sum_fast["total_trades"], sum_standard["total_trades"])
        self.assertEqual(sum_fast["wins"], sum_standard["wins"])
        self.assertEqual(sum_fast["losses"], sum_standard["losses"])
        self.assertEqual(sum_fast["ties"], sum_standard["ties"])
        self.assertAlmostEqual(sum_fast["win_rate_effective"], sum_standard["win_rate_effective"], places=4)
        self.assertAlmostEqual(sum_fast["net_pnl"], sum_standard["net_pnl"], places=4)

    def test_parallel_optimizer_joblib(self):
        optimizer = ParallelOptimizer(n_jobs=2)
        param_grid = [
            {"rsi_period": p} for p in range(5, 15)
        ]
        results = optimizer.optimize_grid_parallel(
            df=self.df,
            strat_class=DummyStrategy,
            param_grid=param_grid,
            expiry=2,
            payout=0.85
        )

        self.assertIsInstance(results, list)
        if len(results) > 0:
            self.assertIn("params", results[0])
            self.assertIn("win_rate", results[0])
            self.assertIn("ev_per_trade", results[0])

    def test_monte_carlo_vectorized_2d_performance(self):
        res = monte_carlo_vectorized_2d(
            win_rate=0.68,
            payout=0.85,
            n_consecutive=3,
            kelly_f=0.05,
            num_simulations=1000,
            num_cycles=200
        )

        self.assertIn("final_equity", res)
        self.assertIn("ruin_probability", res)
        self.assertIn("max_drawdowns", res)

        self.assertIn("mean", res["final_equity"])
        self.assertGreaterEqual(res["ruin_probability"], 0.0)
        self.assertLessEqual(res["ruin_probability"], 1.0)


if __name__ == '__main__':
    unittest.main()
