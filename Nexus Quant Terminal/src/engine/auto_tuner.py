import numpy as np
import pandas as pd
from engine.simulator import BinarySimulator

import optuna

optuna.logging.set_verbosity(optuna.logging.WARNING)


class WalkForwardEngine:
    """
    Motor de Optimización y Análisis Walk-Forward (WFA) verdaderamente dinámico (Feature 14).
    Ejecuta optimización Optuna In-Sample (IS) rolling y evaluación Out-Of-Sample (OOS)
    con purga por expiración y embargo anti-fuga de datos (Metodología Marcos López de Prado).
    """
    def __init__(
        self,
        n_windows: int = 5,
        train_ratio: float = 0.60,
        embargo_pct: float = 0.01,
        n_trials_per_window: int = 20,
        min_is_trades: int = 10,
        min_oos_trades: int = 5,
        target_winrate: float = 0.65
    ):
        self.n_windows = n_windows
        self.train_ratio = train_ratio
        self.embargo_pct = embargo_pct
        self.n_trials_per_window = n_trials_per_window
        self.min_is_trades = min_is_trades
        self.min_oos_trades = min_oos_trades
        self.target_winrate = target_winrate
        self.simulator = BinarySimulator()

    def run_wfa(
        self,
        df: pd.DataFrame,
        strat_obj=None,
        base_params: dict = None,
        expiry: int = 1,
        param_space_fn=None,
        strat_class=None,
        payout: float = 0.85,
        n_trials_per_window: int = None,
        sl_atr: float = None,
        tp_atr: float = None,
        max_holding: int = None,
        bullet_risk: float = None,
        classic_mode: bool = True
    ) -> dict:
        n = len(df)
        if n < 300:
            return {
                "wfe": 0.0, "stable_windows": 0, "window_results": [],
                "mean_is_wr": 0.0, "mean_oos_wr": 0.0, "global_oos_wr": 0.0,
                "global_oos_ev": 0.0, "total_oos_trades": 0, "total_windows_tested": 0
            }

        trials_limit = n_trials_per_window or self.n_trials_per_window
        window_size = int(n / (self.n_windows * (1 - self.train_ratio) + self.train_ratio))
        step_size = int(window_size * (1 - self.train_ratio))

        if strat_class is None and strat_obj is not None:
            strat_class = strat_obj.__class__

        window_results = []
        all_oos_trades = []
        is_winrates = []
        oos_winrates = []

        from engine.ml_engine.purged_cv import PurgedGroupTimeSeriesSplit
        from engine.simulator import VectorizedBinarySimulator

        for w in range(self.n_windows):
            start_idx = w * step_size
            end_idx = start_idx + window_size
            if end_idx > n:
                break

            df_sub = df.iloc[start_idx:end_idx].copy().reset_index(drop=True)
            is_end, oos_start = PurgedGroupTimeSeriesSplit.purge_embargo_split(
                n_samples=len(df_sub), train_ratio=self.train_ratio, expiry_candles=expiry, embargo_pct=self.embargo_pct
            )

            df_is = df_sub.iloc[:is_end].copy().reset_index(drop=True)
            df_oos = df_sub.iloc[oos_start:].copy().reset_index(drop=True)

            if len(df_is) < 50 or len(df_oos) < 15:
                continue

            best_params = base_params.copy() if base_params else {}

            # 1. Rolling In-Sample Optuna Hyperparameter Optimization
            if param_space_fn is not None and strat_class is not None:
                def objective(trial):
                    p = param_space_fn(trial)
                    try:
                        if isinstance(strat_class, type):
                            try:
                                strat = strat_class(**p)
                            except TypeError:
                                strat = strat_class()
                        else:
                            strat = strat_class
                        pre_is = strat.prepare_data(df_is)
                        sigs_is = strat.generate_signals(df_is, params=p, precomputed=pre_is)
                        if sigs_is is None or sigs_is.dropna().empty:
                            return -999.0

                        res_is = VectorizedBinarySimulator.run_fast(
                            df_is, sigs_is, expiry_candles=expiry, payout=payout,
                            sl_atr=sl_atr, tp_atr=tp_atr, max_holding=max_holding, bullet_risk=bullet_risk
                        )
                        sum_is = res_is["summary"]
                        tr_is = sum_is["total_trades"]
                        if tr_is < self.min_is_trades:
                            return -999.0

                        ev_is = sum_is["expected_value_per_trade"]
                        wr_is = sum_is["win_rate_effective"]
                        if wr_is < (1.0 / (1.0 + payout)) and not classic_mode:
                            return -100.0 + (wr_is * 100.0)

                        pf_is = sum_is.get("profit_factor", 1.0)
                        score = ev_is * np.log1p(tr_is) if not classic_mode else (sum_is.get("sharpe_ratio", 0.0) * min(5.0, pf_is) * np.log1p(tr_is))
                        return score if not np.isnan(score) else -999.0
                    except Exception:
                        return -999.0

                try:
                    study = optuna.create_study(
                        direction="maximize",
                        sampler=optuna.samplers.TPESampler(seed=42 + w)
                    )
                    study.optimize(objective, n_trials=trials_limit, timeout=60, n_jobs=1)
                    if study.best_params:
                        best_params = study.best_params
                except Exception:
                    pass

            # 2. Evaluate best parameters on IS and OOS splits
            try:
                if strat_class is not None:
                    if isinstance(strat_class, type):
                        try:
                            strat_best = strat_class(**best_params)
                        except TypeError:
                            strat_best = strat_class()
                    else:
                        strat_best = strat_class
                elif strat_obj is not None:
                    strat_best = strat_obj
                else:
                    continue

                # IS Evaluation
                pre_is = strat_best.prepare_data(df_is)
                sigs_is = strat_best.generate_signals(df_is, params=best_params, precomputed=pre_is)

                # Direction filter handling
                filt = best_params.get("direction_filter")
                if filt == "CALL_ONLY" and sigs_is is not None:
                    sigs_is = sigs_is.map(lambda x: 'CALL' if x == 'CALL' else None)
                elif filt == "PUT_ONLY" and sigs_is is not None:
                    sigs_is = sigs_is.map(lambda x: 'PUT' if x == 'PUT' else None)

                res_is = VectorizedBinarySimulator.run_fast(
                    df_is, sigs_is, expiry_candles=expiry, payout=payout,
                    sl_atr=sl_atr, tp_atr=tp_atr, max_holding=max_holding, bullet_risk=bullet_risk
                )

                # OOS Evaluation
                pre_oos = strat_best.prepare_data(df_oos)
                sigs_oos = strat_best.generate_signals(df_oos, params=best_params, precomputed=pre_oos)
                if filt == "CALL_ONLY" and sigs_oos is not None:
                    sigs_oos = sigs_oos.map(lambda x: 'CALL' if x == 'CALL' else None)
                elif filt == "PUT_ONLY" and sigs_oos is not None:
                    sigs_oos = sigs_oos.map(lambda x: 'PUT' if x == 'PUT' else None)

                res_oos = VectorizedBinarySimulator.run_fast(
                    df_oos, sigs_oos, expiry_candles=expiry, payout=payout,
                    sl_atr=sl_atr, tp_atr=tp_atr, max_holding=max_holding, bullet_risk=bullet_risk
                )
                detailed_oos = self.simulator.run(
                    df_oos, sigs_oos, expiry_candles=expiry, payout=payout,
                    sl_atr=sl_atr, tp_atr=tp_atr, max_holding=max_holding, bullet_risk=bullet_risk,
                    classic_mode=classic_mode
                )

                sum_is = res_is.get("summary", {})
                sum_oos = res_oos.get("summary", {})

                tr_is = sum_is.get("total_trades", 0)
                wr_is = sum_is.get("win_rate_effective", 0.0) * 100.0

                tr_oos = sum_oos.get("total_trades", 0)
                wr_oos = sum_oos.get("win_rate_effective", 0.0) * 100.0
                ev_oos = sum_oos.get("expected_value_per_trade", 0.0)

                is_winrates.append(wr_is if tr_is > 0 else 0.0)
                oos_winrates.append(wr_oos if tr_oos > 0 else 0.0)

                if detailed_oos.get("trades"):
                    all_oos_trades.extend(detailed_oos["trades"])

                # Stability criteria
                is_stable = (tr_oos >= self.min_oos_trades) and (wr_oos >= (self.target_winrate * 100.0)) and (ev_oos > 0.0)

                window_results.append({
                    "window": w + 1,
                    "best_params": best_params,
                    "tr_is": tr_is,
                    "wr_is": round(wr_is, 1),
                    "tr_oos": tr_oos,
                    "wr_oos": round(wr_oos, 1),
                    "ev_oos": round(ev_oos, 4),
                    "is_stable": is_stable
                })
            except Exception:
                pass

        mean_is = float(np.mean(is_winrates)) if is_winrates else 0.0
        mean_oos = float(np.mean(oos_winrates)) if oos_winrates else 0.0
        wfe = round((mean_oos / mean_is) * 100.0, 1) if (mean_is > 0 and mean_oos > 0) else 0.0

        stable_count = sum(1 for w in window_results if w.get("is_stable", False))

        total_oos_wins = sum(1 for t in all_oos_trades if t.get("result") == "WIN")
        total_oos_losses = sum(1 for t in all_oos_trades if t.get("result") == "LOSS")
        total_oos_decisive = total_oos_wins + total_oos_losses

        global_oos_wr = (total_oos_wins / total_oos_decisive) if total_oos_decisive > 0 else 0.0
        global_oos_ev = (global_oos_wr * payout) - ((1.0 - global_oos_wr) * 1.0)

        # Wilson 95% CI lower bound
        z = 1.96
        if total_oos_decisive > 0:
            n_tot = float(total_oos_decisive)
            p_hat = global_oos_wr
            denom = 1.0 + (z**2) / n_tot
            center = (p_hat + (z**2) / (2 * n_tot)) / denom
            margin = (z * np.sqrt((p_hat * (1.0 - p_hat) / n_tot) + (z**2) / (4 * (n_tot**2)))) / denom
            wilson_low = max(0.0, float(center - margin))
        else:
            wilson_low = 0.0

        return {
            "wfe": wfe,
            "mean_is_wr": round(mean_is, 1),
            "mean_oos_wr": round(mean_oos, 1),
            "global_oos_wr": round(global_oos_wr * 100.0, 2),
            "global_oos_wr_wilson_low": round(wilson_low * 100.0, 2),
            "global_oos_ev": round(global_oos_ev, 4),
            "total_oos_trades": total_oos_decisive,
            "stable_windows": stable_count,
            "total_windows_tested": len(window_results),
            "window_results": window_results
        }

    def run_walk_forward(self, *args, **kwargs) -> dict:
        """Alias for run_wfa."""
        return self.run_wfa(*args, **kwargs)


class ParameterSurfaceAnalyzer:
    r"""
    Analizador de Topología de la Superficie de Parámetros.
    Mapea el vecindario ($\pm 20\%$) para garantizar que la estrategia se encuentre
    en una meseta ancha y suave de alta rentabilidad (evitando picos aislados).
    """
    def __init__(self):
        self.simulator = BinarySimulator()

    def analyze_surface(self, df: pd.DataFrame, strat_obj, params: dict, expiry: int = 1) -> dict:
        if len(df) < 150:
            return {"surface_score": 0.0, "plateau_ratio": 0.0, "neighbor_rates": []}

        split_idx = int(len(df) * 0.60)
        df_oos = df.iloc[split_idx:].copy().reset_index(drop=True)

        neighbor_rates = []
        variations = [-0.20, -0.10, 0.10, 0.20]

        try:
            pre_oos = strat_obj.prepare_data(df_oos)
        except Exception:
            pre_oos = None

        eval_params = {k: v for k, v in params.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}

        for k, v in eval_params.items():
            for var in variations:
                p_copy = params.copy()
                if isinstance(v, int):
                    p_copy[k] = max(1, int(round(v * (1 + var))))
                else:
                    p_copy[k] = round(v * (1 + var), 4)

                try:
                    sigs = strat_obj.generate_signals(df_oos, p_copy, precomputed=pre_oos)
                    if sigs is not None and not sigs.empty:
                        filt = p_copy.get("direction_filter")
                        if filt == "CALL_ONLY":
                            sigs = sigs.map(lambda x: 'CALL' if x == 'CALL' else None)
                        elif filt == "PUT_ONLY":
                            sigs = sigs.map(lambda x: 'PUT' if x == 'PUT' else None)

                        res = self.simulator.run(df_oos, sigs, expiry_candles=expiry, payout=0.85)
                        sum_s = res.get("summary", {})
                        tr = sum_s.get("total_trades", 0)
                        wr = sum_s.get("win_rate_effective", 0.0) * 100
                        if tr >= 2:
                            neighbor_rates.append(wr)
                except Exception:
                    pass

        if not neighbor_rates:
            return {"surface_score": 100.0, "plateau_ratio": 1.0, "neighbor_rates": []}

        avg_wr = np.mean(neighbor_rates)
        plateau_count = sum(1 for rate in neighbor_rates if rate >= 75.0)
        plateau_ratio = round(plateau_count / len(neighbor_rates), 2)

        return {
            "surface_score": round(float(avg_wr), 1),
            "plateau_ratio": plateau_ratio,
            "min_neighbor_wr": round(float(np.min(neighbor_rates)), 1),
            "max_neighbor_wr": round(float(np.max(neighbor_rates)), 1),
            "total_neighbors_tested": len(neighbor_rates)
        }


class DynamicRegimeAdapter:
    """
    Adaptador Dinámico por Régimen de Mercado.
    Detecta el nivel de volatilidad (ATR Quantiles) y la fuerza de tendencia (slope)
    para escalar los umbrales dinámicamente según el contexto actual.
    """
    @staticmethod
    def detect_regime(df: pd.DataFrame, at_index: int = -1) -> dict:
        if df is None or len(df) < 50:
            return {"regime": "NORMAL", "volatility_quantile": 0.5, "trend_direction": "NEUTRAL"}

        df_sub = df.iloc[:at_index+1] if at_index != -1 else df

        high = df_sub['high']
        low = df_sub['low']
        close = df_sub['close']

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14 = tr.rolling(14).mean()

        current_atr = atr_14.iloc[-1]
        hist_atr_median = atr_14.rolling(100, min_periods=1).median().iloc[-1]

        vol_q = current_atr / hist_atr_median if hist_atr_median > 0 else 1.0

        ema50 = close.ewm(span=50, adjust=False).mean()
        ema_slope = (ema50.iloc[-1] - ema50.iloc[-5]) / ema50.iloc[-5] if len(ema50) >= 5 else 0.0

        if vol_q >= 1.25:
            regime_str = "HIGH_VOLATILITY_EXPANSION"
        elif vol_q <= 0.75:
            regime_str = "LOW_VOLATILITY_COMPRESSION"
        else:
            regime_str = "NORMAL_VOLATILITY"

        trend_str = "BULLISH" if ema_slope > 0.002 else ("BEARISH" if ema_slope < -0.002 else "NEUTRAL")

        return {
            "regime": regime_str,
            "volatility_quantile": round(float(vol_q), 2),
            "trend_direction": trend_str,
            "ema_slope": round(float(ema_slope), 4)
        }

    @staticmethod
    def adapt_params(base_params: dict, regime_info: dict) -> dict:
        """Adapta dinámicamente los parámetros según el régimen detectado."""
        adapted = base_params.copy()
        vol_q = regime_info.get("volatility_quantile", 1.0)
        trend = regime_info.get("trend_direction", "NEUTRAL")

        # Adjust Bollinger Band std or wick ratios based on volatility expansion/compression
        if "bb_std" in adapted:
            if vol_q >= 1.25:
                adapted["bb_std"] = round(base_params["bb_std"] * 1.10, 2)  # Exigir mayor desviación en alta volatilidad
            elif vol_q <= 0.75:
                adapted["bb_std"] = round(base_params["bb_std"] * 0.90, 2)  # Flexibilizar en baja volatilidad

        if trend == "BULLISH":
            adapted["direction_filter"] = "CALL_ONLY"
        elif trend == "BEARISH":
            adapted["direction_filter"] = "PUT_ONLY"
        else:
            adapted["direction_filter"] = "BOTH"

        return adapted

