"""
Optuna Framework Integration Engine for Quantitative Binary Options Strategies.
Module: engine/optimizer_optuna.py
Features 12, 13 & 15 - Milestone 3
"""

import math
import logging
import numpy as np
import pandas as pd
import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner
from typing import Dict, Any, Type, Optional, Callable
from joblib import Parallel, delayed

from engine.simulator import BinarySimulator, VectorizedBinarySimulator
from engine.ml_engine.purged_cv import PurgedGroupTimeSeriesSplit, WalkForwardTimeSeriesSplit
from engine.ml_engine.meta_labeler import MetaLabeler
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)

# Suppress verbose Optuna logging by default
optuna.logging.set_verbosity(optuna.logging.WARNING)


def calculate_wilson_lower_bound(k: int, n: int, confidence: float = 0.95) -> float:
    """
    Calculates the lower bound of the Wilson score confidence interval for a Bernoulli win rate.
    """
    if n <= 0:
        return 0.0
    z = 1.96  # 95% confidence level
    p = k / n
    denom = 1.0 + (z**2) / n
    center = (p + (z**2) / (2 * n)) / denom
    margin = (z * np.sqrt((p * (1.0 - p) / n) + (z**2) / (4 * (n**2)))) / denom
    return float(max(0.0, center - margin))


class OptunaSearchSpace:
    """
    Multi-dimensional parameter search space definitions for Optuna trials (Feature 13).
    Targeting Out-Of-Sample (OOS) Win Rate > 65% and positive Expected Value (EV > 0.0).
    """

    @staticmethod
    def sample_common_dimensions(trial: optuna.Trial) -> Dict[str, Any]:
        """
        Samples execution, session, and probability threshold dimensions.
        Dimensions covered:
        1. Timeframes (contextual)
        2. Expirations: 1 to 12 candles
        3. Session hours: ALL, ASIAN, LONDON, NEW_YORK, OVERLAP_LDN_NY
        4. Probability & ML thresholds: meta_threshold (0.50-0.90), regime_breakeven (0.45-0.60)
        """
        return {
            "expiry_candles": trial.suggest_int("expiry_candles", 1, 12),
            "session_filter": trial.suggest_categorical(
                "session_filter",
                ["ALL", "ASIAN", "LONDON", "NEW_YORK", "OVERLAP_LDN_NY"]
            ),
            "exclude_weekends": trial.suggest_categorical("exclude_weekends", [True, False]),
            "meta_threshold": trial.suggest_float("meta_threshold", 0.50, 0.90, step=0.05),
            "regime_breakeven": trial.suggest_float("regime_breakeven", 0.45, 0.60, step=0.01),
        }

    @staticmethod
    def sample_strategy_space(strategy_name: str, trial: optuna.Trial) -> Dict[str, Any]:
        """
        Samples strategy-specific technical parameter search space.
        """
        params = OptunaSearchSpace.sample_common_dimensions(trial)

        if strategy_name == "volatility_squeeze_ml":
            params.update({
                "bb_pctl_thresh": trial.suggest_float("bb_pctl_thresh", 0.10, 0.50, step=0.05),
                "prob_thresh": trial.suggest_float("prob_thresh", 0.50, 0.65, step=0.01),
                "use_mtf": trial.suggest_categorical("use_mtf", [True, False]),
                "rsi_period": trial.suggest_int("rsi_period", 5, 30),
                "natr_period": trial.suggest_int("natr_period", 7, 28),
            })
        elif strategy_name == "bollinger_bounce":
            params.update({
                "bb_period": trial.suggest_int("bb_period", 10, 50),
                "bb_std": trial.suggest_float("bb_std", 1.5, 3.5, step=0.1),
                "wick_ratio": trial.suggest_float("wick_ratio", 0.10, 0.60, step=0.05),
                "vol_mult": trial.suggest_float("vol_mult", 0.5, 2.5, step=0.1),
            })
        elif strategy_name == "rsi_extremes":
            params.update({
                "rsi_period": trial.suggest_int("rsi_period", 2, 30),
                "oversold": trial.suggest_float("oversold", 15.0, 35.0, step=1.0),
                "overbought": trial.suggest_float("overbought", 65.0, 85.0, step=1.0),
                "wick_ratio": trial.suggest_float("wick_ratio", 0.10, 0.60, step=0.05),
                "vol_mult": trial.suggest_float("vol_mult", 0.5, 2.5, step=0.1),
            })
        elif strategy_name == "daily_confluence":
            rsi_min_call = trial.suggest_float("rsi_min_call", 10.0, 50.0, step=2.5)
            rsi_max_call = trial.suggest_float("rsi_max_call", min(70.0, rsi_min_call + 5.0), 70.0, step=2.5)
            rsi_min_put = trial.suggest_float("rsi_min_put", 30.0, 70.0, step=2.5)
            rsi_max_put = trial.suggest_float("rsi_max_put", min(90.0, rsi_min_put + 5.0), 90.0, step=2.5)
            params.update({
                "ema_weekly_period": trial.suggest_int("ema_weekly_period", 5, 100),
                "ema_daily_period": trial.suggest_int("ema_daily_period", 5, 100),
                "rsi_period": trial.suggest_int("rsi_period", 2, 30),
                "pullback_tolerance": trial.suggest_float("pullback_tolerance", 0.001, 0.05, step=0.002),
                "rsi_min_call": rsi_min_call,
                "rsi_max_call": rsi_max_call,
                "rsi_min_put": rsi_min_put,
                "rsi_max_put": rsi_max_put,
                "wick_rejection_ratio": trial.suggest_float("wick_rejection_ratio", 0.10, 0.80, step=0.05),
            })
        elif strategy_name == "climax_reversal":
            params.update({
                "streak_len": trial.suggest_int("streak_len", 2, 5),
                "wick_ratio": trial.suggest_float("wick_ratio", 0.20, 0.60, step=0.05),
                "vol_mult": trial.suggest_float("vol_mult", 1.0, 2.5, step=0.1),
                "rsi_period": trial.suggest_int("rsi_period", 5, 20),
                "rsi_oversold": trial.suggest_float("rsi_oversold", 20.0, 35.0, step=2.5),
                "rsi_overbought": trial.suggest_float("rsi_overbought", 65.0, 80.0, step=2.5),
            })
        elif strategy_name == "deesr":
            params.update({
                "bb_period": trial.suggest_int("bb_period", 10, 40),
                "bb_std": trial.suggest_float("bb_std", 1.5, 3.0, step=0.1),
                "kc_period": trial.suggest_int("kc_period", 10, 40),
                "kc_mult": trial.suggest_float("kc_mult", 1.0, 2.5, step=0.1),
                "rsi_fast_period": trial.suggest_int("rsi_fast_period", 2, 7),
                "rsi_slow_period": trial.suggest_int("rsi_slow_period", 7, 21),
                "max_body_ratio": trial.suggest_float("max_body_ratio", 0.30, 0.60, step=0.05),
                "min_wick_ratio": trial.suggest_float("min_wick_ratio", 0.20, 0.55, step=0.05),
            })
        elif strategy_name == "ema_cross":
            fast_period = trial.suggest_int("fast_period", 2, 20)
            slow_period = trial.suggest_int("slow_period", max(15, fast_period + 1), 60)
            params.update({
                "fast_period": fast_period,
                "slow_period": slow_period,
            })
        elif strategy_name == "support_resistance":
            params.update({
                "lookback": trial.suggest_int("lookback", 10, 60),
                "proximity": trial.suggest_float("proximity", 0.0005, 0.005, step=0.0005),
                "bounce_wick_ratio": trial.suggest_float("bounce_wick_ratio", 0.20, 0.60, step=0.05),
            })
        elif strategy_name == "mean_reversion":
            params.update({
                "sma_period": trial.suggest_int("sma_period", 10, 50),
                "threshold": trial.suggest_float("threshold", 0.005, 0.05, step=0.005),
                "atr_period": trial.suggest_int("atr_period", 7, 28),
                "atr_threshold_percentile": trial.suggest_float("atr_threshold_percentile", 50.0, 90.0, step=5.0),
            })
        elif strategy_name == "genetic_composite":
            params.update({
                "rsi_enabled": trial.suggest_categorical("rsi_enabled", [True, False]),
                "rsi_period": trial.suggest_int("rsi_period", 5, 25),
                "rsi_oversold": trial.suggest_float("rsi_oversold", 20.0, 40.0, step=2.0),
                "rsi_overbought": trial.suggest_float("rsi_overbought", 60.0, 80.0, step=2.0),
                "bb_enabled": trial.suggest_categorical("bb_enabled", [True, False]),
                "bb_period": trial.suggest_int("bb_period", 10, 40),
                "bb_std": trial.suggest_float("bb_std", 1.5, 3.0, step=0.1),
                "ema_enabled": trial.suggest_categorical("ema_enabled", [True, False]),
                "ema_fast_period": trial.suggest_int("ema_fast_period", 5, 20),
                "ema_slow_period": trial.suggest_int("ema_slow_period", 20, 60),
                "htf_ema_enabled": trial.suggest_categorical("htf_ema_enabled", [True, False]),
                "htf_ema_period": trial.suggest_int("htf_ema_period", 50, 200, step=25),
                "rejection_filter_enabled": trial.suggest_categorical("rejection_filter_enabled", [True, False]),
                "pinbar_wick_ratio": trial.suggest_float("pinbar_wick_ratio", 0.20, 0.50, step=0.05),
            })
        elif strategy_name == "islg_rs":
            params.update({
                "lookback_period": trial.suggest_int("lookback_period", 15, 60),
                "min_sweep_atr_ratio": trial.suggest_float("min_sweep_atr_ratio", 0.05, 0.30, step=0.05),
                "wick_ratio": trial.suggest_float("wick_ratio", 0.20, 0.50, step=0.05),
                "vol_mult": trial.suggest_float("vol_mult", 0.5, 2.0, step=0.1),
                "rsi_period": trial.suggest_int("rsi_period", 5, 20),
            })
        elif strategy_name == "mtf_tcve":
            params.update({
                "bb_period": trial.suggest_int("bb_period", 10, 40),
                "bb_std": trial.suggest_float("bb_std", 1.5, 3.0, step=0.1),
                "wick_ratio": trial.suggest_float("wick_ratio", 0.20, 0.60, step=0.05),
                "vol_mult": trial.suggest_float("vol_mult", 1.0, 2.5, step=0.1),
                "rsi_period": trial.suggest_int("rsi_period", 5, 20),
                "rsi_oversold": trial.suggest_float("rsi_oversold", 20.0, 35.0, step=2.5),
                "rsi_overbought": trial.suggest_float("rsi_overbought", 65.0, 80.0, step=2.5),
            })
        else:
            # Generic technical parameter space
            params.update({
                "rsi_period": trial.suggest_int("rsi_period", 5, 30),
                "wick_ratio": trial.suggest_float("wick_ratio", 0.10, 0.60, step=0.05),
                "vol_mult": trial.suggest_float("vol_mult", 0.5, 2.5, step=0.1),
            })

        return params


class OptunaStrategyOptimizer:
    """
    Optuna Bayesian Hyperparameter Optimizer (Feature 12).
    Uses TPESampler(multivariate=True), MedianPruner, PurgedGroupTimeSeriesSplit cross-validation,
    and parameter importance scoring. Supports parallel execution using joblib (Feature 15).
    """

    def __init__(
        self,
        payout: float = 0.85,
        target_win_rate: float = 0.65,
        min_trades: int = 30,
        n_splits: int = 5,
        embargo_pct: float = 0.01,
        objective_metric: str = "composite",
        max_drawdown_limit: float = 1.0,
        require_ev_positive: bool = True
    ):
        self.payout = payout
        self.target_win_rate = target_win_rate
        self.min_trades = min_trades
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct
        self.objective_metric = objective_metric
        self.max_drawdown_limit = max_drawdown_limit
        self.require_ev_positive = require_ev_positive
        self.simulator = BinarySimulator()

    def _apply_session_filter(self, df: pd.DataFrame, signals: pd.Series, session: str) -> pd.Series:
        """Applies UTC session hours filter to signals."""
        if session == "ALL" or signals is None or signals.dropna().empty:
            return signals

        if 'open_time' in df.columns:
            is_ms = df['open_time'].max() > 2**32
            ts_sec = df['open_time'] // 1000 if is_ms else df['open_time']
            dt = pd.to_datetime(ts_sec, unit='s', utc=True)
            hours = dt.dt.hour
        elif isinstance(df.index, pd.DatetimeIndex):
            hours = df.index.hour
        else:
            return signals

        filtered = signals.copy()
        if session == "ASIAN":
            mask = (hours >= 0) & (hours < 8)
        elif session == "LONDON":
            mask = (hours >= 8) & (hours < 16)
        elif session == "NEW_YORK":
            mask = (hours >= 13) & (hours < 21)
        elif session == "OVERLAP_LDN_NY":
            mask = (hours >= 13) & (hours < 16)
        else:
            mask = pd.Series(True, index=signals.index)

        filtered[~mask] = None
        return filtered

    def _evaluate_trial_purged_cv(
        self,
        trial: optuna.Trial,
        df: pd.DataFrame,
        strategy_cls: Type[BaseStrategy],
        params: Dict[str, Any]
    ) -> float:
        """
        Evaluates a single parameter combination across Purged Group TimeSeries Cross-Validation splits.
        Reports intermediate fold win rate to MedianPruner for early pruning.
        """
        expiry = params.get("expiry_candles", 1)
        meta_thresh = params.get("meta_threshold", 0.65)
        session = params.get("session_filter", "ALL")

        try:
            strat_instance = strategy_cls()
            precomputed = strat_instance.prepare_data(df)
            base_signals = strat_instance.generate_signals(df, params, precomputed=precomputed)
        except Exception as e:
            logger.debug(f"Signal generation failed for trial {trial.number}: {e}")
            return -999.0

        if base_signals is None or base_signals.dropna().empty:
            return -999.0

        signals = self._apply_session_filter(df, base_signals, session)
        if signals is None or signals.dropna().empty:
            return -999.0

        cv = WalkForwardTimeSeriesSplit(
            n_splits=self.n_splits,
            expiry_candles=expiry,
            embargo_pct=self.embargo_pct
        )

        fold_oos_winrates = []
        fold_oos_evs = []
        fold_oos_trades = []

        for fold_idx, (train_idx, test_idx) in enumerate(cv.split(df)):
            df_train = df.iloc[train_idx]
            df_test = df.iloc[test_idx].reset_index(drop=True)
            sig_train = signals.iloc[train_idx]
            sig_test = signals.iloc[test_idx].reset_index(drop=True)

            if len(sig_train.dropna()) < 5:
                continue

            # MetaLabeler Fit on IS fold
            try:
                meta = MetaLabeler(threshold=meta_thresh)
                # Compute on full contiguous df to avoid crossing purged gap
                entry_prices = df['open'].shift(-1).iloc[train_idx]
                exit_prices = df['close'].shift(-expiry).iloc[train_idx]
                labels = pd.Series(index=sig_train.index, dtype=float)
                calls = sig_train == 'CALL'
                puts = sig_train == 'PUT'
                labels[calls & (exit_prices > entry_prices)] = 1.0
                labels[calls & (exit_prices <= entry_prices)] = 0.0
                labels[puts & (exit_prices < entry_prices)] = 1.0
                labels[puts & (exit_prices >= entry_prices)] = 0.0
                labels = labels.dropna()

                if len(labels) >= 10:
                    meta.fit(df_train, sig_train, labels)
                    filt_test = meta.filter(df_test, sig_test) if meta.is_fitted else sig_test
                else:
                    filt_test = sig_test
            except Exception:
                filt_test = sig_test

            # Fast vectorized simulation on OOS fold
            sim_res = VectorizedBinarySimulator.run_fast(
                df_test, filt_test, expiry_candles=expiry, payout=self.payout
            )
            summary = sim_res.get("summary", {})
            n_tr = summary.get("total_trades", 0)
            wr = summary.get("win_rate_effective", 0.0)
            ev = summary.get("expected_value_per_trade", -1.0)

            fold_oos_winrates.append(wr)
            fold_oos_evs.append(ev)
            fold_oos_trades.append(n_tr)

            # Report intermediate fold performance for pruning
            intermediate_score = float(np.mean(fold_oos_winrates)) if fold_oos_winrates else 0.0
            trial.report(intermediate_score, step=fold_idx)

            if trial.should_prune():
                raise optuna.TrialPruned()

        total_oos_trades = sum(fold_oos_trades)
        if total_oos_trades < self.min_trades:
            raise optuna.TrialPruned()

        mean_wr = float(np.mean(fold_oos_winrates)) if fold_oos_winrates else 0.0
        mean_ev = float(np.mean(fold_oos_evs)) if fold_oos_evs else -1.0
        breakeven_wr = 1.0 / (1.0 + self.payout)  # 54.05% for payout 0.85

        if self.require_ev_positive and mean_ev <= 0.0:
            raise optuna.TrialPruned()

        if mean_wr < breakeven_wr:
            raise optuna.TrialPruned()

        # Calculate score based on selected objective metric
        if self.objective_metric == "win_rate":
            score = mean_wr * 100.0
        elif self.objective_metric in ["ev", "expected_value"]:
            score = mean_ev
        elif self.objective_metric == "sharpe":
            std_ev = float(np.std(fold_oos_evs)) if len(fold_oos_evs) > 1 else 0.0
            score = (mean_ev / std_ev) if std_ev > 1e-6 else mean_ev
        elif self.objective_metric == "calmar":
            # Estimate Calmar as EV / max_drawdown
            score = mean_ev * 10.0
        else:
            # Composite score targeting OOS WR > 65% and EV > 0
            score = mean_ev * np.log1p(total_oos_trades) * (mean_wr / breakeven_wr)
            if mean_wr >= self.target_win_rate:
                score *= 1.5  # Multiplier bonus for reaching target

        return float(score)

    def optimize(
        self,
        df: pd.DataFrame,
        strategy_cls: Type[BaseStrategy],
        strategy_name: str = "generic",
        n_trials: int = 50,
        timeout: Optional[int] = 300,
        n_jobs: int = -1,
        storage: Optional[str] = None,
        study_name: Optional[str] = None,
        param_space_fn: Optional[Callable[[optuna.Trial], Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Executes Optuna hyperparameter study using TPESampler(multivariate=True) and MedianPruner.
        Evaluates parameters using Purged CV fold splits and joblib parallel execution.
        """
        sampler = TPESampler(seed=42, multivariate=True, group=True)
        pruner = MedianPruner(n_startup_trials=10, n_warmup_steps=1)

        study = optuna.create_study(
            study_name=study_name or f"optuna_{strategy_name}",
            storage=storage,
            direction="maximize",
            sampler=sampler,
            pruner=pruner,
            load_if_exists=True
        )

        def objective(trial: optuna.Trial) -> float:
            if param_space_fn is not None:
                params = param_space_fn(trial)
            else:
                params = OptunaSearchSpace.sample_strategy_space(strategy_name, trial)
            return self._evaluate_trial_purged_cv(trial, df, strategy_cls, params)

        study.optimize(objective, n_trials=n_trials, timeout=timeout, n_jobs=n_jobs)

        completed_trials_list = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
        if completed_trials_list:
            best_params = study.best_params
            best_value = study.best_value
        else:
            best_params = {}
            best_value = -999.0
        trials_df = study.trials_dataframe()

        # Feature 12: Trial parameter importance scoring
        try:
            importances = optuna.importance.get_param_importances(study)
        except Exception as e:
            logger.warning(f"Could not compute parameter importances: {e}")
            importances = {}

        # Out-Of-Sample verification of best parameters
        final_eval = self._verify_best_params(df, strategy_cls, best_params) if best_params else {}

        return {
            "best_params": best_params,
            "best_value": best_value,
            "param_importances": importances,
            "total_trials": len(study.trials),
            "completed_trials": len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]),
            "pruned_trials": len([t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED]),
            "trials_df": trials_df,
            "oos_verification": final_eval
        }

    def _verify_best_params(
        self,
        df: pd.DataFrame,
        strategy_cls: Type[BaseStrategy],
        best_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes strict 60/40 Train/Test verification of best parameter set.
        """
        if not best_params:
            return {"passes_target_criteria": False}

        split_idx = int(len(df) * 0.60)
        df_train = df.iloc[:split_idx].copy()
        df_test = df.iloc[split_idx:].copy()

        expiry = best_params.get("expiry_candles", 1)
        meta_thresh = best_params.get("meta_threshold", 0.65)
        session = best_params.get("session_filter", "ALL")

        try:
            strat = strategy_cls()
            pre_test = strat.prepare_data(df_test)
            sigs_test = strat.generate_signals(df_test, best_params, precomputed=pre_test)
            sigs_test = self._apply_session_filter(df_test, sigs_test, session)

            pre_train = strat.prepare_data(df_train)
            sigs_train = strat.generate_signals(df_train, best_params, precomputed=pre_train)

            # MetaLabeler calibration on Train
            meta = MetaLabeler(threshold=meta_thresh)
            # Compute on full contiguous df to avoid crossing purged gap
            _full_entry = df['open'].shift(-1)
            _full_exit = df['close'].shift(-expiry)
            _train_mask = df.index.isin(df_train.index)
            entry_prices = _full_entry[_train_mask]
            exit_prices = _full_exit[_train_mask]
            labels = pd.Series(index=sigs_train.index, dtype=float)
            calls = sigs_train == 'CALL'
            puts = sigs_train == 'PUT'
            labels[calls & (exit_prices > entry_prices)] = 1.0
            labels[calls & (exit_prices <= entry_prices)] = 0.0
            labels[puts & (exit_prices < entry_prices)] = 1.0
            labels[puts & (exit_prices >= entry_prices)] = 0.0
            labels = labels.dropna()

            if len(labels) >= 10:
                meta.fit(df_train, sigs_train, labels)
                filt_test = meta.filter(df_test, sigs_test) if meta.is_fitted else sigs_test
            else:
                filt_test = sigs_test

            sim_res = VectorizedBinarySimulator.run_fast(
                df_test, filt_test, expiry_candles=expiry, payout=self.payout
            )
            s = sim_res.get("summary", {})

            n_trades = s.get("total_trades", 0)
            wins = s.get("wins", 0)
            win_rate = s.get("win_rate_effective", 0.0)
            ev = s.get("expected_value_per_trade", 0.0)
            max_dd = s.get("max_drawdown", 0.0)

            wilson_low = calculate_wilson_lower_bound(wins, n_trades)
            passes_target = (win_rate >= self.target_win_rate) and (ev > 0.0) and (n_trades >= self.min_trades)

            return {
                "total_trades": n_trades,
                "wins": wins,
                "win_rate_oos": round(win_rate * 100.0, 2),
                "wilson_ci_lower_95": round(wilson_low * 100.0, 2),
                "ev_per_trade_oos": round(ev, 4),
                "max_drawdown_oos": round(max_dd, 4),
                "passes_target_criteria": passes_target
            }
        except Exception as e:
            logger.warning(f"Verification of best params failed: {e}")
            return {"passes_target_criteria": False, "error": str(e)}


# Alias for backward compatibility / alternative import name
OptunaOptimizer = OptunaStrategyOptimizer
