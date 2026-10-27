import numpy as np


def purged_embargo_cv_splits(
    n_samples: int,
    n_splits: int = 5,
    max_holding: int = 30,
    embargo_pct: float = 0.01
) -> list:
    """
    Genera particiones Purged & Embargoed Group TimeSeries Splits (Marcos López de Prado).
    Garantiza cero fuga de datos (Lookahead Leakage) entre trades que cruzan fronteras de split.
    """
    indices = np.arange(n_samples)
    embargo_offset = max(1, int(n_samples * embargo_pct))
    test_size = n_samples // n_splits
    splits = []

    for i in range(n_splits):
        test_start = i * test_size
        test_end = (i + 1) * test_size if i < n_splits - 1 else n_samples

        train_mask = np.ones(n_samples, dtype=bool)
        train_mask[test_start:test_end] = False

        purge_start = max(0, test_start - max_holding)
        train_mask[purge_start:test_start] = False

        embargo_end = min(n_samples, test_end + max(embargo_offset, max_holding))
        train_mask[test_end:embargo_end] = False

        train_idx = indices[train_mask]
        test_idx = indices[test_start:test_end]
        splits.append((train_idx, test_idx))

    return splits


def optimize_sl_tp_parameters(
    df,
    signal_indices,
    signal_types,
    atr,
    fee_pct: float = 0.0005,
    slippage_pct: float = 0.0002,
    n_trials: int = 40
) -> dict:
    """
    Optimiza de forma Bayesiana (Optuna) o Grid Search sistemático los hiperparámetros:
      - sl_multiplier in [0.8, 3.0]
      - tp_multiplier in [1.5, 6.0]
      - max_holding in [5, 35]
    Utilizando validación cruzada Purged & Embargoed TimeSeries Out-Of-Sample.
    """
    from engine.simulator import TripleBarrierSimulator
    n = len(df)
    splits = purged_embargo_cv_splits(n, n_splits=5, max_holding=30, embargo_pct=0.01)

    def evaluate_params(sl_mult: float, tp_mult: float, max_hold: int) -> float:
        oos_scores = []
        for _, test_indices in splits:
            test_mask = np.isin(signal_indices, test_indices)
            split_sig_idx = signal_indices[test_mask]
            split_sig_type = signal_types[test_mask]

            if len(split_sig_idx) < 3:
                continue

            trade_pnls = []
            next_allowed = 0
            for s_idx, s_type in zip(split_sig_idx, split_sig_type):
                if s_idx + 1 < next_allowed or s_idx + 1 >= n or atr[s_idx] <= 0:
                    continue

                trade = TripleBarrierSimulator.evaluate_single_trade(
                    df=df,
                    entry_idx=s_idx + 1,
                    direction=s_type,
                    atr_val=atr[s_idx],
                    sl_multiplier=sl_mult,
                    tp_multiplier=tp_mult,
                    max_holding=max_hold,
                    bullet_risk=33.3333,
                    fee_pct=fee_pct,
                    slippage_pct=slippage_pct
                )
                if trade:
                    trade_pnls.append(trade['pnl'])
                    next_allowed = trade['exit_idx'] + 1

            if len(trade_pnls) > 0:
                mean_pnl = np.mean(trade_pnls)
                std_pnl = np.std(trade_pnls) + 1e-6
                sharpe = (mean_pnl / std_pnl) * np.sqrt(min(252, len(trade_pnls)))
                gross_win = sum(p for p in trade_pnls if p > 0)
                gross_loss = abs(sum(p for p in trade_pnls if p < 0))
                pf = gross_win / gross_loss if gross_loss > 0 else 2.0
                score = sharpe * min(5.0, pf) * np.log1p(len(trade_pnls))
                oos_scores.append(score)

        if not oos_scores:
            return -999.0
        return float(np.mean(oos_scores))

    best_params = {"sl_multiplier": 1.5, "tp_multiplier": 3.0, "max_holding": 20}
    best_score = -999.0

    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        has_optuna = True
    except ImportError:
        has_optuna = False

    if has_optuna and len(signal_indices) >= 15:
        def objective(trial):
            sl_m = trial.suggest_float("sl_multiplier", 0.8, 3.0, step=0.1)
            tp_m = trial.suggest_float("tp_multiplier", 1.5, 6.0, step=0.25)
            hold = trial.suggest_int("max_holding", 5, 35, step=1)
            return evaluate_params(sl_m, tp_m, hold)

        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
        study.optimize(objective, n_trials=n_trials, timeout=20)
        best_params = study.best_params
        best_score = study.best_value
    else:
        grid_sl = [1.0, 1.2, 1.5, 1.8, 2.2]
        grid_tp = [2.0, 2.5, 3.0, 3.5, 4.5]
        grid_hold = [10, 15, 20, 25]
        for sl_m in grid_sl:
            for tp_m in grid_tp:
                for hold in grid_hold:
                    score = evaluate_params(sl_m, tp_m, hold)
                    if score > best_score:
                        best_score = score
                        best_params = {"sl_multiplier": sl_m, "tp_multiplier": tp_m, "max_holding": hold}

    return {
        "best_params": best_params,
        "best_oos_score": best_score
    }


class ClassicOptimizer:
    """
    Optimizador Cuantitativo para Trading Clásico Asimétrico.
    Optimiza simultáneamente la selección de señales y las barreras de Stop Loss / Take Profit.
    """
    @staticmethod
    def optimize_sl_tp(df, signal_indices, signal_types, atr, fee_pct=0.0005, slippage_pct=0.0002, n_trials=40):
        return optimize_sl_tp_parameters(df, signal_indices, signal_types, atr, fee_pct, slippage_pct, n_trials)

    @staticmethod
    def calculate_leveraged_execution_plan(
        base_patrimony: float = 1000.0,
        monthly_flow: float = 200.0,
        entry_price: float = 60000.0,
        atr_val: float = 1200.0,
        sl_multiplier: float = 1.5,
        tp_multiplier: float = 3.0,
        direction: str = 'LONG',
        fee_pct: float = 0.0005,
        slippage_pct: float = 0.0002
    ) -> dict:
        """
        Calcula el plan matemático exacto de ejecución con apalancamiento institucional,
        dimensionando el nominal y el apalancamiento para que el riesgo coincida
        exactamente con el flujo asignado ($200 USD o submúltiplos), blindando el patrimonio base ($1,000 USD).
        """
        is_long = direction.upper() in ['LONG', 'CALL', 'BUY', '1']
        sl_distance = sl_multiplier * atr_val
        tp_distance = tp_multiplier * atr_val

        sl_price = entry_price - sl_distance if is_long else entry_price + sl_distance
        tp_price = entry_price + tp_distance if is_long else entry_price - tp_distance

        sl_pct = (sl_distance / entry_price) if entry_price > 0 else 0.02
        tp_pct = (tp_distance / entry_price) if entry_price > 0 else 0.04
        total_friction_pct = (2.0 * fee_pct) + (2.0 * slippage_pct)

        effective_loss_fraction = max(1e-5, sl_pct + total_friction_pct)
        
        # Apalancamiento exacto para arriesgar el flujo mensual (bullet_risk = monthly_flow)
        bullet_risk = float(monthly_flow)
        position_nominal_usd = bullet_risk / effective_loss_fraction
        position_coins = position_nominal_usd / entry_price if entry_price > 0 else 0.0
        
        # Apalancamiento efectivo sobre el margen
        effective_leverage = position_nominal_usd / bullet_risk
        recommended_leverage_tier = min(100, max(1, int(np.ceil(effective_leverage))))

        rr_ratio = tp_multiplier / sl_multiplier if sl_multiplier > 0 else 2.0
        gross_profit_usd = position_nominal_usd * tp_pct
        net_profit_usd = position_nominal_usd * (tp_pct - total_friction_pct)

        # Duplicación del patrimonio base ($1,000)
        trades_needed_to_double = int(np.ceil(base_patrimony / net_profit_usd)) if net_profit_usd > 0 else 999

        # Cálculo de rachas compuestas convexas (Paroli / Parlay en Trading Clásico)
        eff_payout = rr_ratio
        streak_2_trades_profit = bullet_risk * (((1.0 + eff_payout) ** 2) - 1.0)
        streak_2_doubles = bool(streak_2_trades_profit >= base_patrimony)
        
        bullet_4 = bullet_risk / 4.0
        streak_4b_3t_profit = bullet_4 * (((1.0 + eff_payout) ** 3) - 1.0)
        streak_4b_doubles = bool(streak_4b_3t_profit >= base_patrimony)

        bullet_6 = bullet_risk / 6.0
        streak_6b_3t_profit = bullet_6 * (((1.0 + eff_payout) ** 3) - 1.0)
        streak_6b_doubles = bool(streak_6b_3t_profit >= base_patrimony)

        compounding_plans = {
            "single_bullet_streak_2": {
                "bullet_risk_usd": round(bullet_risk, 2),
                "streak_length": 2,
                "net_profit_usd": round(float(streak_2_trades_profit), 2),
                "resulting_patrimony": round(float(base_patrimony + streak_2_trades_profit), 2),
                "doubles_patrimony": streak_2_doubles,
                "summary": f"2 trades seguidos arriesgando ${round(bullet_risk, 1)} generan +${round(streak_2_trades_profit, 1)} (Patrimonio: ${round(base_patrimony + streak_2_trades_profit, 1)})"
            },
            "four_bullets_streak_3": {
                "bullet_risk_usd": round(bullet_4, 2),
                "streak_length": 3,
                "bullets_count": 4,
                "net_profit_usd": round(float(streak_4b_3t_profit), 2),
                "resulting_patrimony": round(float(base_patrimony + streak_4b_3t_profit), 2),
                "doubles_patrimony": streak_4b_doubles,
                "summary": f"4 balas de ${round(bullet_4, 1)}, 1 racha de 3 aciertos genera +${round(streak_4b_3t_profit, 1)}"
            },
            "six_bullets_streak_3": {
                "bullet_risk_usd": round(bullet_6, 2),
                "streak_length": 3,
                "bullets_count": 6,
                "net_profit_usd": round(float(streak_6b_3t_profit), 2),
                "resulting_patrimony": round(float(base_patrimony + streak_6b_3t_profit), 2),
                "doubles_patrimony": streak_6b_doubles,
                "summary": f"6 balas de ${round(bullet_6, 1)}, 1 racha de 3 aciertos genera +${round(streak_6b_3t_profit, 1)}"
            }
        }

        return {
            "base_patrimony_protected": float(base_patrimony),
            "margin_to_commit_usd": bullet_risk,
            "entry_price": float(entry_price),
            "direction": "LONG" if is_long else "SHORT",
            "sl_price": round(float(sl_price), 4),
            "tp_price": round(float(tp_price), 4),
            "sl_distance_pct": round(float(sl_pct * 100.0), 2),
            "tp_distance_pct": round(float(tp_pct * 100.0), 2),
            "rr_ratio": round(float(rr_ratio), 2),
            "effective_leverage": round(float(effective_leverage), 1),
            "recommended_leverage_tier": f"{recommended_leverage_tier}x",
            "position_nominal_usd": round(float(position_nominal_usd), 2),
            "position_nominal_units": round(float(position_coins), 6),
            "potential_net_profit_usd": round(float(net_profit_usd), 2),
            "potential_loss_usd": round(float(bullet_risk), 2),
            "base_capital_at_risk": 0.0,
            "base_capital_drawdown_pct": 0.0,
            "trades_to_double_patrimony": trades_needed_to_double,
            "estimated_days_to_double": f"{trades_needed_to_double * 2} días aprox (en 4h/1D)",
            "compounding_plans": compounding_plans
        }


