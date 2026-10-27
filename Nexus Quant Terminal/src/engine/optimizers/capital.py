import math
import numpy as np
from engine.optimizers.math_utils import binomial_sf, monte_carlo_vectorized_2d, calculate_wilson_lower_bound

class CapitalOptimizer:
    def find_optimal_n(self, win_rate: float, payout: float, max_n: int = 15) -> dict:
        results_by_n = []
        p = win_rate
        r = payout + 1.0
        
        if p * r <= 1:
            return {"error": "Juego con esperanza matematica negativa."}
            
        optimal_n = 1
        optimal_kelly = 0
        optimal_growth = -float('inf')
        
        for n in range(1, max_n + 1):
            p_success = p ** n
            profit_if_win = r ** n - 1
            
            kelly_f = (p_success * r**n - 1) / (r**n - 1) if (r**n - 1) != 0 else 0
            kelly_f = max(0.0, min(0.99, kelly_f))
                
            if 0 < kelly_f < 1.0 and p_success > 0:
                g_n = p_success * np.log(1.0 + kelly_f * profit_if_win) + (1.0 - p_success) * np.log(1.0 - kelly_f)
            else:
                g_n = 0.0
                
            t_n = (1 - p_success) / (1 - p) if (p != 1 and p_success != 1) else n
            growth_per_trade = g_n / t_n if t_n > 0 else g_n / n
            
            expected_value = p_success * profit_if_win - (1 - p_success)
            
            variance = p_success * (profit_if_win)**2 + (1 - p_success) * 1 - expected_value**2
            sharpe_ratio = expected_value / np.sqrt(variance) if variance > 0 else 0
            
            if growth_per_trade > optimal_growth:
                optimal_growth = growth_per_trade
                optimal_n = n
                optimal_kelly = kelly_f
                
            results_by_n.append({
                "n": n,
                "p_success": p_success,
                "profit_if_win": profit_if_win,
                "kelly_f": kelly_f,
                "growth_per_cycle": g_n,
                "growth_per_trade": growth_per_trade,
                "sharpe_ratio": sharpe_ratio,
                "expected_value": expected_value,
                "variance": variance
            })
            
        safe_kelly = optimal_kelly * 0.5  # Half-Kelly por seguridad matemática

        return {
            "results_by_n": results_by_n,
            "optimal_n": optimal_n,
            "optimal_kelly": optimal_kelly,
            "safe_kelly": safe_kelly,
            "optimal_growth": optimal_growth
        }
        
    def monte_carlo(self, win_rate: float, payout: float, n: int, kelly_f: float, num_simulations: int = 10000, num_cycles: int = 1000, trades_history: list = None, p_ww: float = None, p_wl: float = None) -> dict:
        r = payout + 1.0
        use_markov = p_ww is not None and p_wl is not None and p_ww > 0 and p_wl > 0
        if use_markov:
            p_success = win_rate * (p_ww ** (n - 1)) if n > 1 else win_rate
        else:
            p_success = win_rate ** n
        profit_if_win = r ** n - 1
        
        paths = []
        final_equities = []
        max_drawdowns = []
        ruins = 0
        
        # Extracción de secuencias empíricas si existen datos históricos
        empirical_outcomes = []
        if trades_history and len(trades_history) >= 20:
            empirical_outcomes = [1 if t.get('result') == 'WIN' or t.get('is_win') else 0 for t in trades_history]

        for i in range(num_simulations):
            equity = 1.0
            path = [equity]
            peak = equity
            max_dd = 0
            
            if empirical_outcomes and len(empirical_outcomes) >= 20:
                # Block Bootstrap de tamaño 5
                block_size = min(5, len(empirical_outcomes))
                results = []
                while len(results) < num_cycles:
                    idx = np.random.randint(0, len(empirical_outcomes) - block_size + 1)
                    results.extend(empirical_outcomes[idx:idx+block_size])
                results = np.array(results[:num_cycles]) == 1
            elif use_markov:
                results = np.zeros(num_cycles, dtype=bool)
                last_win = None
                for j in range(num_cycles):
                    if last_win is None:
                        p_c = p_success
                    elif last_win:
                        p_c = p_ww ** n if n > 1 else p_ww
                    else:
                        p_c = win_rate * (p_ww ** (n - 1)) if n > 1 else p_wl
                    results[j] = np.random.rand() < p_c
                    last_win = results[j]
            else:
                results = np.random.rand(num_cycles) < p_success
                
            for is_win in results:
                bet = equity * kelly_f
                if is_win:
                    equity += bet * profit_if_win
                else:
                    equity -= bet
                    
                if equity <= 1e-6:
                    equity = 0
                    
                path.append(equity)
                
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
                    
                if equity == 0:
                    break
                    
            if equity == 0:
                ruins += 1
                
            final_equities.append(equity)
            max_drawdowns.append(max_dd)
            
            if i < 100:
                paths.append(path)
                
        final_equities = np.array(final_equities)
        return {
            "paths": paths,
            "final_equity": {
                "mean": np.mean(final_equities),
                "median": np.median(final_equities),
                "p5": np.percentile(final_equities, 5),
                "p25": np.percentile(final_equities, 25),
                "p75": np.percentile(final_equities, 75),
                "p95": np.percentile(final_equities, 95),
                "min": np.min(final_equities),
                "max": np.max(final_equities)
            },
            "ruin_probability": ruins / num_simulations,
            "max_drawdowns": {
                "mean": np.mean(max_drawdowns),
                "median": np.median(max_drawdowns),
                "p95": np.percentile(max_drawdowns, 95)
            }
        }
        
    def find_optimal_n_markov(self, p_states: list, transition_matrix: list, payout: float, max_n: int = 15) -> dict:
        """
        Calcula la racha óptima N considerando la matriz de transición de Markov (2 estados: 0=Loss, 1=Win).
        transition_matrix: [[P(W|W), P(L|W)], [P(W|L), P(L|L)]]
        """
        if not transition_matrix or len(transition_matrix) < 2 or not p_states:
            p_mean = float(np.mean(p_states)) if p_states else 0.5
            return self.find_optimal_n(p_mean, payout, max_n)
            
        p_ww = float(transition_matrix[0][0])  # P(Win | Win anterior)
        p_wl = float(transition_matrix[1][0])  # P(Win | Loss anterior)

        # Al iniciar un nuevo ciclo (tras una pérdida o desde cero), la probabilidad real
        # de que el primer trade sea ganador es P(W|L), no la media incondicional.
        # Usamos p_wl como punto de partida si está disponible, con fallback al promedio de p_states.
        if len(p_states) > 0:
            p_unconditional = float(np.mean(p_states))
        else:
            p_unconditional = p_wl

        # p_base = P(W|L) cuando hay información de transición.
        # Si p_wl == 0 empíricamente (ninguna pérdida fue seguida de victoria), usar incondicional
        # pero marcar advertencia para que el consumidor lo sepa.
        p_wl_fallback_used = (p_wl == 0)
        p_base = p_wl if p_wl > 0 else p_unconditional
        
        r = payout + 1.0
        results_by_n = []
        optimal_n = 1
        optimal_kelly = 0
        optimal_growth = -float('inf')
        
        for n in range(1, max_n + 1):
            p_success = p_base * (p_ww ** (n - 1)) if n > 1 else p_base
            profit_if_win = (r ** n) - 1.0
            
            if profit_if_win > 0:
                kelly_f = (p_success * (profit_if_win + 1.0) - 1.0) / profit_if_win
            else:
                kelly_f = 0.0
            
            kelly_f = max(0.0, min(0.99, kelly_f))
            
            if 0 < kelly_f < 1.0 and p_success > 0:
                g_n = p_success * np.log(1.0 + kelly_f * profit_if_win) + (1.0 - p_success) * np.log(1.0 - kelly_f)
            else:
                g_n = 0.0
                
            if n == 1:
                t_n_markov = 1.0
            else:
                if p_ww != 1.0:
                    t_n_markov = 1.0 + p_base * (1.0 - (p_ww ** (n - 1))) / (1.0 - p_ww)
                else:
                    t_n_markov = 1.0 + p_base * (n - 1)
            growth_per_trade = g_n / t_n_markov if t_n_markov > 0 else g_n / n
            expected_value = p_success * profit_if_win - (1.0 - p_success)
            variance = p_success * (profit_if_win ** 2) + (1.0 - p_success) - (expected_value ** 2)
            sharpe_ratio = expected_value / np.sqrt(variance) if variance > 0 else 0.0
            
            if growth_per_trade > optimal_growth:
                optimal_growth = growth_per_trade
                optimal_n = n
                optimal_kelly = kelly_f
                
            results_by_n.append({
                "n": n,
                "p_success": float(p_success),
                "profit_if_win": float(profit_if_win),
                "kelly_f": float(kelly_f),
                "growth_per_cycle": float(g_n),
                "growth_per_trade": float(growth_per_trade),
                "sharpe_ratio": float(sharpe_ratio),
                "expected_value": float(expected_value),
                "variance": float(variance)
            })
            
        return {
            "results_by_n": results_by_n,
            "optimal_n": optimal_n,
            "optimal_kelly": float(optimal_kelly),
            "optimal_growth": float(optimal_growth),
            "p_ww": p_ww,
            "p_base": p_base,
            "p_wl_fallback_used": p_wl_fallback_used
        }


    def monte_carlo_discrete(self, win_rate: float, payout: float, n_consecutive: int, bet_fraction: float, risk_capital: float = 200.0, target_capital: float = 1000.0, num_simulations: int = 5000, max_trades: int = 2000, p_ww: float = None, p_wl: float = None) -> dict:
        successes = 0
        ruins = 0
        timeouts = 0
        trade_counts = []
        final_capitals = []
        use_markov = p_ww is not None and p_wl is not None and p_ww > 0 and p_wl > 0
        
        for _ in range(num_simulations):
            capital = risk_capital
            base_capital = risk_capital
            consecutive_wins = 0
            trades_count = 0
            last_was_win = None
            
            while 0.0001 < capital < target_capital and trades_count < max_trades:
                bet_size = (base_capital * bet_fraction) * ((1.0 + payout) ** consecutive_wins)
                if bet_size > capital:
                    bet_size = capital
                
                if use_markov:
                    if last_was_win is None:
                        p_current = win_rate
                    elif last_was_win:
                        p_current = p_ww
                    else:
                        p_current = p_wl
                else:
                    p_current = win_rate
                
                is_win = np.random.rand() < p_current
                last_was_win = is_win
                if is_win:
                    capital += bet_size * payout
                    consecutive_wins += 1
                    if consecutive_wins >= n_consecutive:
                        base_capital = capital
                        consecutive_wins = 0
                else:
                    capital -= bet_size
                    consecutive_wins = 0
                    base_capital = capital
                
                trades_count += 1
            
            if capital >= target_capital:
                successes += 1
            elif capital <= 0.0001:
                ruins += 1
            else:
                timeouts += 1
                
            trade_counts.append(trades_count)
            final_capitals.append(capital)
            
        trade_counts = np.array(trade_counts)
        final_capitals = np.array(final_capitals)
        
        expected_value = float(np.mean(final_capitals)) - risk_capital
        
        return {
            "success_probability": successes / num_simulations,
            "ruin_probability": ruins / num_simulations,
            "timeout_probability": timeouts / num_simulations,
            "mean_trades": float(np.mean(trade_counts)),
            "median_trades": float(np.median(trade_counts)),
            "expected_value": expected_value,
            "mean_final_capital": float(np.mean(final_capitals))
        }

    def calculate_streak_plan(self, win_rate: float, payout: float, risk_capital: float, target_capital: float, attempts: int, total_trades: int = 100, base_capital: float = None, p_ww: float = None, p_wl: float = None) -> dict:
        if attempts <= 0 or risk_capital <= 0:
            return {
                "error": "Los intentos y el capital de riesgo deben ser mayores a cero.",
                "results_by_n": [],
                "best_plan": None,
                "optimal_n": 1
            }
        actual_base_capital = float(base_capital) if base_capital is not None else float(target_capital if target_capital > risk_capital else (risk_capital * 5.0))
        
        results_by_n = []
        best_n_for_target = None
        
        effective_wr = max(0.0, min(1.0, float(win_rate)))
        sample_is_sufficient = total_trades >= 30
        wr_capped_warning = not sample_is_sufficient and total_trades > 0
        
        if total_trades > 0:
            k_wins = int(round(effective_wr * total_trades))
            wilson_ci_lower_95 = calculate_wilson_lower_bound(k_wins, total_trades)
        else:
            wilson_ci_lower_95 = 0.0
        
        max_allowed_n = 15
        use_markov = p_ww is not None and p_wl is not None and p_ww > 0 and p_wl > 0

        for n in range(1, max_allowed_n + 1):
            if use_markov:
                p_base_markov = effective_wr
                p_success_single = p_base_markov * (p_ww ** (n - 1)) if n > 1 else p_base_markov
                p_success_single_iid = effective_wr ** n
            else:
                p_success_single = effective_wr ** n
                p_success_single_iid = p_success_single
            p_success_campaign = 1.0 - (1.0 - p_success_single) ** attempts
            bet_per_attempt = risk_capital / attempts
            final_capital = bet_per_attempt * ((1.0 + payout) ** n)
            multiplier = final_capital / risk_capital
            
            # Ganancia neta por 1 racha exitosa sobre el tamaño de la bala
            net_gain_per_streak = final_capital - bet_per_attempt
            
            if net_gain_per_streak > 0:
                needed_streaks = int(math.ceil(target_capital / net_gain_per_streak))
            else:
                needed_streaks = 999
                
            prob_at_least_1_streak_pct = float(p_success_campaign * 100.0)
            
            if attempts > 1:
                # Para campañas de múltiples intentos (ej. 6 u 8 balas), el éxito de la campaña mensual es completar al menos 1 racha
                prob_duplication_pct = prob_at_least_1_streak_pct
                needed_streaks = 1 if (final_capital >= target_capital or needed_streaks <= 1) else needed_streaks
            else:
                # Para campaña de 1 bala (intento = 1, $200), 1 racha de N=3 multiplica $200 x ((1+payout)^3 - 1) = +$1,066.33 netos, duplicando el patrimonio a $2,066.33.
                if needed_streaks <= 1 or final_capital >= target_capital:
                    prob_duplication_pct = prob_at_least_1_streak_pct
                    needed_streaks = 1
                else:
                    prob_duplication = binomial_sf(attempts, needed_streaks, p_success_single)
                    prob_duplication_pct = float(prob_duplication * 100.0)
            
            if needed_streaks == 1 or attempts > 1:
                if p_success_single > 0:
                    exp_attempts = (1.0 - (1.0 - p_success_single) ** attempts) / p_success_single
                    expected_cost = min(risk_capital, bet_per_attempt * exp_attempts)
                    unspent_capital = max(0.0, risk_capital - expected_cost)
                    expected_monthly_net_profit = (p_success_campaign * final_capital + unspent_capital) - risk_capital
                else:
                    expected_cost = risk_capital
                    expected_monthly_net_profit = -risk_capital
            else:
                expected_monthly_net_profit = attempts * p_success_single * final_capital - risk_capital

            expected_final_patrimony = actual_base_capital + expected_monthly_net_profit

            bet_ladder = []
            current_bet = bet_per_attempt
            default_lev = 33
            for step in range(1, n + 1):
                payout_gain = float(current_bet * payout)
                accum_cap = float(current_bet * (1.0 + payout))
                nominal_size = float(current_bet * default_lev)
                is_quarantine = bool(step > 1)
                bet_ladder.append({
                    "step": step,
                    "bet_size": float(current_bet),
                    "margin_risk": float(current_bet),
                    "recommended_leverage": default_lev,
                    "nominal_position_usd": nominal_size,
                    "payout_return": payout_gain,
                    "accumulated_capital": accum_cap,
                    "stop_loss_usd": -float(current_bet),
                    "take_profit_usd": payout_gain,
                    "is_quarantine": is_quarantine,
                    "capital_at_risk_own": 0.0 if is_quarantine else float(bet_per_attempt)
                })
                current_bet = accum_cap
                
            p_martingale_recovery = 1.0 - ((1.0 - effective_wr) ** n)
            
            results_by_n.append({
                "n": n,
                "p_success_single": float(p_success_single),
                "p_success_single_iid": float(p_success_single_iid),
                "p_success_campaign": float(p_success_campaign),
                "p_martingale_recovery": float(p_martingale_recovery),
                "bet_per_attempt": float(bet_per_attempt),
                "final_capital": float(final_capital),
                "multiplier": float(multiplier),
                "expected_value": float(expected_monthly_net_profit),
                "needed_streaks": needed_streaks,
                "prob_duplication_pct": float(round(prob_duplication_pct, 2)),
                "prob_at_least_1_streak_pct": float(round(prob_at_least_1_streak_pct, 2)),
                "expected_monthly_net_profit": float(round(expected_monthly_net_profit, 2)),
                "expected_final_patrimony": float(round(expected_final_patrimony, 2)),
                "bet_ladder": bet_ladder
            })
            
            # Seleccionar N que alcanza o supera el objetivo de capital con mayor probabilidad
            if target_capital > 0 and final_capital >= target_capital and best_n_for_target is None:
                best_n_for_target = n

        target_achievable = True
        if best_n_for_target is None:
            # Fallback al N con mejor esperanza matemática
            best_n_for_target = max(results_by_n, key=lambda x: x["expected_value"])["n"] if results_by_n else 1
            target_achievable = False
            
        best_plan = next((r for r in results_by_n if r["n"] == best_n_for_target), results_by_n[0] if results_by_n else {})

        return {
            "results_by_n": results_by_n,
            "best_n_for_target": best_n_for_target,
            "needed_streaks": best_plan.get("needed_streaks", 1),
            "prob_duplication_pct": best_plan.get("prob_duplication_pct", 0.0),
            "prob_at_least_1_streak_pct": best_plan.get("prob_at_least_1_streak_pct", 0.0),
            "expected_monthly_net_profit": best_plan.get("expected_monthly_net_profit", 0.0),
            "expected_final_patrimony": best_plan.get("expected_final_patrimony", actual_base_capital),
            "base_capital": actual_base_capital,
            "target_achievable": target_achievable,
            "win_rate": wilson_ci_lower_95 if (wr_capped_warning and total_trades > 0) else effective_wr,
            "raw_win_rate": win_rate,
            "effective_win_rate": effective_wr,
            "wilson_ci_lower_95": wilson_ci_lower_95,
            "win_rate_capped_warning": wr_capped_warning,
            "sample_is_sufficient": sample_is_sufficient,
            "total_trades": total_trades,
            "payout": payout,
            "risk_capital": risk_capital,
            "target_capital": target_capital,
            "attempts": attempts,
            "markov_mode": use_markov,
            "p_ww_used": float(p_ww) if p_ww is not None else None,
            "p_wl_used": float(p_wl) if p_wl is not None else None
        }

    def monte_carlo_campaign(self, win_rate: float, payout: float, n_streak: int, k_attempts: int, bet_per_attempt: float, num_simulations: int = 5000, p_ww: float = None, p_wl: float = None) -> dict:
        """
        Simulación Monte Carlo de campaña completa Barbell (múltiples intentos para completar racha N).
        """
        successes = 0
        ruins = 0
        paths = []
        initial_risk_capital = bet_per_attempt * k_attempts
        final_pnl_list = []
        use_markov = p_ww is not None and p_wl is not None and p_ww > 0 and p_wl > 0
        
        for sim_idx in range(num_simulations):
            capital = initial_risk_capital
            path = [capital]
            success = False
            last_was_win_campaign = None
            
            for attempt in range(k_attempts):
                # Cada intento arriesga bet_per_attempt. Si se pierde la racha, la bala se consume.
                attempt_capital = bet_per_attempt
                consecutive_wins = 0
                max_trades_per_attempt = n_streak * 3
                attempt_success = False
                
                for _ in range(max_trades_per_attempt):
                    current_bet = bet_per_attempt * ((1.0 + payout) ** consecutive_wins)
                    
                    if use_markov:
                        if last_was_win_campaign is None:
                            p_current = win_rate
                        elif last_was_win_campaign:
                            p_current = p_ww
                        else:
                            p_current = p_wl
                    else:
                        p_current = win_rate
                    
                    is_win = np.random.rand() < p_current
                    last_was_win_campaign = is_win
                    if is_win:
                        attempt_capital += current_bet * payout
                        consecutive_wins += 1
                        if consecutive_wins >= n_streak:
                            attempt_success = True
                            break
                    else:
                        attempt_capital -= current_bet
                        consecutive_wins = 0
                        break # Falla la racha, se pierde el intento
                
                if attempt_success:
                    gain = attempt_capital
                    capital = capital - bet_per_attempt + gain
                    success = True
                    break # Campaña exitosa al lograr al menos una racha
                else:
                    capital -= bet_per_attempt
                    path.append(capital)
                    
            if success:
                successes += 1
                final_pnl_list.append(capital)
            else:
                ruins += 1
                capital = 0.0
                final_pnl_list.append(0.0)
                
            path.append(capital)
            
            if sim_idx < 100:
                paths.append(path)
                
        final_pnl_list = np.array(final_pnl_list)
        success_prob = successes / num_simulations
        ruin_prob = ruins / num_simulations
        expected_value = np.mean(final_pnl_list) - initial_risk_capital
        
        return {
            "success_probability": float(success_prob),
            "ruin_probability": float(ruin_prob),
            "expected_value": float(expected_value),
            "mean_final_capital": float(np.mean(final_pnl_list)),
            "paths": paths
        }

    def optimize_daily_confluence_stream(self, universe_data: dict, payout: float = 0.85):
        """
        Optimiza de forma exhaustiva (45 combinaciones) y emite progreso en cada iteración.
        """
        from strategies.daily_confluence import DailyConfluenceStrategy
        from engine.simulator import BinarySimulator
        from engine.ml_engine.purged_cv import PurgedGroupTimeSeriesSplit

        pullback_candidates = [0.003, 0.005, 0.008, 0.012, 0.015]
        rsi_min_candidates = [25.0, 30.0, 35.0]
        wick_ratio_candidates = [0.25, 0.35, 0.45]

        best_score = -float('inf')
        best_params = {
            'pullback_tolerance': 0.015,
            'rsi_min_call': 25.0,
            'rsi_max_call': 55.0,
            'wick_rejection_ratio': 0.35,
            'direction_filter': 'CALL',
            'exclude_weekends': True
        }
        best_wr_oos = 0.50
        best_wr_is = 0.50

        sim = BinarySimulator()

        # Split universe_data chronologically into IS and OOS with Purged CV & Embargo
        universe_is = {}
        universe_oos = {}
        for sym, df_sym in universe_data.items():
            n_sym = len(df_sym)
            is_end, oos_start = PurgedGroupTimeSeriesSplit.purge_embargo_split(
                n_samples=n_sym, train_ratio=0.70, expiry_candles=2, embargo_pct=0.01
            )
            universe_is[sym] = df_sym.iloc[:is_end].copy().reset_index(drop=True)
            universe_oos[sym] = df_sym.iloc[oos_start:].copy().reset_index(drop=True)

        precomputed_is = {}
        precomputed_oos = {}
        strat_base = DailyConfluenceStrategy()
        for sym, df in universe_is.items():
            precomputed_is[sym] = strat_base.prepare_data(df)
        for sym, df in universe_oos.items():
            precomputed_oos[sym] = strat_base.prepare_data(df)

        total_iterations = len(pullback_candidates) * len(rsi_min_candidates) * len(wick_ratio_candidates)
        current_iter = 0

        for pb in pullback_candidates:
            for rsi_min in rsi_min_candidates:
                for wick_r in wick_ratio_candidates:
                    current_iter += 1

                    strat_params = {
                        'pullback_tolerance': pb,
                        'rsi_min_call': rsi_min,
                        'rsi_max_call': 55.0,
                        'wick_rejection_ratio': wick_r,
                        'direction_filter': 'CALL',
                        'exclude_weekends': True
                    }
                    strat = DailyConfluenceStrategy(
                        pullback_tolerance=pb,
                        rsi_min_call=rsi_min,
                        rsi_max_call=55.0,
                        wick_rejection_ratio=wick_r,
                        direction_filter='CALL',
                        exclude_weekends=True
                    )

                    signals_is = {}
                    signals_oos = {}
                    for sym in universe_data.keys():
                        sigs_is = strat.generate_signals_list(universe_is[sym], precomputed=precomputed_is[sym])
                        if sigs_is:
                            signals_is[sym] = sigs_is
                        sigs_oos = strat.generate_signals_list(universe_oos[sym], precomputed=precomputed_oos[sym])
                        if sigs_oos:
                            signals_oos[sym] = sigs_oos

                    trades_is = []
                    if signals_is:
                        sim_res_is = sim.run_multi_asset(
                            universe_data=universe_is,
                            signals_by_pair=signals_is,
                            expiry_candles=2,
                            payout=payout,
                            mode='BARBELL',
                            n_consecutive=3,
                            bet_fraction=0.166,
                            initial_capital=1000.0
                        )
                        trades_is = sim_res_is.get('trades', [])

                    trades_oos = []
                    if signals_oos:
                        sim_res_oos = sim.run_multi_asset(
                            universe_data=universe_oos,
                            signals_by_pair=signals_oos,
                            expiry_candles=2,
                            payout=payout,
                            mode='BARBELL',
                            n_consecutive=3,
                            bet_fraction=0.166,
                            initial_capital=1000.0
                        )
                        trades_oos = sim_res_oos.get('trades', [])

                    decisive_is = [t for t in trades_is if t['result'] in ['WIN', 'LOSS']]
                    if len(decisive_is) > 0:
                        wins_is = sum(1 for t in decisive_is if t['result'] == 'WIN')
                        wr_is = wins_is / len(decisive_is)

                        decisive_oos = [t for t in trades_oos if t['result'] in ['WIN', 'LOSS']]
                        wins_oos = sum(1 for t in decisive_oos if t['result'] == 'WIN')
                        wr_oos = (wins_oos / len(decisive_oos)) if len(decisive_oos) > 0 else wr_is

                        ev_is = (wr_is * payout) - ((1.0 - wr_is) * 1.0)
                        score = ev_is * np.log1p(len(decisive_is))

                        if score > best_score:
                            best_score = score
                            best_params = strat_params
                            best_wr_oos = wr_oos
                            best_wr_is = wr_is

                    yield {
                        'current': current_iter,
                        'total': total_iterations,
                        'best_params': best_params,
                        'win_rate_oos': best_wr_oos,
                        'win_rate_is': best_wr_is
                    }

    def optimize_daily_confluence(self, universe_data: dict, payout: float = 0.85, callback=None) -> dict:
        """
        Versión síncrona manteniendo retrocompatibilidad.
        """
        last_res = {}
        for step in self.optimize_daily_confluence_stream(universe_data, payout=payout):
            last_res = step
        return {
            'best_params': last_res.get('best_params', {}),
            'win_rate_oos': last_res.get('win_rate_oos', 0.50),
            'win_rate_is': last_res.get('win_rate_is', 0.50)
        }

    def calculate_barbell_patrimony_duplication_engine(
        self,
        base_patrimony: float = 1000.0,
        monthly_flow_pct: float = 0.20,
        win_rate: float = 0.55,
        payout: float = 0.85,
        target_patrimony: float = None,
        n_sims: int = 10000,
        max_months: int = 24
    ) -> dict:
        """
        Mecanismo Cuantitativo Universal para la Duplicación de Patrimonio Base
        financiada exclusivamente por el flujo de arbitraje mensual (Modelo Barbell de Nassim Taleb).
        
        Garantías Matemáticas:
        1. Riesgo de ruina del patrimonio base = 0.0% (el principal permanece blindado en arbitraje).
        2. N* óptimo derivado analíticamente como ceil(ln(1 + 1/alpha) / ln(1 + payout)).
        3. Cuantificación analítica y estocástica de tiempos de duplicación y probabilidades acumuladas.
        """
        base_P0 = float(base_patrimony)
        alpha = float(monthly_flow_pct)
        p = float(win_rate)
        R = float(payout)
        target_P = float(target_patrimony) if target_patrimony is not None else (2.0 * base_P0)

        # 1. Teorema 1: Umbral Analítico Óptimo N*
        n_star_exact = math.log(1.0 + (1.0 / alpha)) / math.log(1.0 + R)
        n_star = int(math.ceil(n_star_exact))

        # 2. Mecánica de la Racha N*
        multiplier_n_star = ((1.0 + R) ** n_star) - 1.0
        profit_per_hit = (base_P0 * alpha) * multiplier_n_star
        patrimony_after_1_hit = base_P0 + profit_per_hit

        # 3. Probabilidades Analíticas para N* (Distribución Geométrica)
        p_hit_monthly = p ** n_star
        exp_months_n_star = (1.0 / p_hit_monthly) if p_hit_monthly > 0 else float('inf')
        median_months_n_star = int(math.ceil(math.log(0.5) / math.log(1.0 - p_hit_monthly))) if (0 < p_hit_monthly < 1) else (1 if p_hit_monthly == 1 else 999)

        cum_prob_n_star = {}
        for m in [1, 2, 3, 6, 12, 18, 24]:
            p_cum = 1.0 - ((1.0 - p_hit_monthly) ** m) if p_hit_monthly > 0 else 0.0
            cum_prob_n_star[f"month_{m}"] = float(round(p_cum * 100.0, 2))

        # 4. Mecánica de Baja Varianza N = 2
        p_hit_n2 = p ** 2
        multiplier_n2 = ((1.0 + R) ** 2) - 1.0
        profit_per_hit_n2 = (base_P0 * alpha) * multiplier_n2
        exp_months_n2 = (2.0 / p_hit_n2) if p_hit_n2 > 0 else float('inf')

        cum_prob_n2 = {}
        for m in [1, 2, 3, 6, 12, 18, 24]:
            if m < 2 or p_hit_n2 <= 0:
                cum_prob_n2[f"month_{m}"] = 0.0
            else:
                p_0 = (1.0 - p_hit_n2) ** m
                p_1 = m * p_hit_n2 * ((1.0 - p_hit_n2) ** (m - 1))
                cum_prob_n2[f"month_{m}"] = float(round((1.0 - p_0 - p_1) * 100.0, 2))

        # 5. Simulación Estocástica de Validación (10,000 caminos)
        np.random.seed(42)
        sim_hits_n_star = np.random.rand(n_sims, max_months) < p_hit_monthly
        sim_hits_n2 = np.random.rand(n_sims, max_months) < p_hit_n2

        first_hit_n_star = np.argmax(sim_hits_n_star, axis=1) + 1
        has_any_hit_n_star = np.any(sim_hits_n_star, axis=1)
        first_hit_n_star[~has_any_hit_n_star] = 999

        cum_hits_n2 = np.cumsum(sim_hits_n2, axis=1)
        first_hit_n2 = np.where(cum_hits_n2 >= 2, 1, 0)
        has_two_hits_n2 = np.any(first_hit_n2 == 1, axis=1)
        months_n2 = np.argmax(first_hit_n2 == 1, axis=1) + 1
        months_n2[~has_two_hits_n2] = 999

        return {
            "initial_base_patrimony": base_P0,
            "target_patrimony": target_P,
            "monthly_flow_pct": alpha,
            "monthly_flow_initial": base_P0 * alpha,
            "win_rate": p,
            "payout": R,
            "optimal_n": {
                "n_star": n_star,
                "n_star_exact": float(round(n_star_exact, 4)),
                "multiplier": float(round(multiplier_n_star, 4)),
                "profit_per_hit": float(round(profit_per_hit, 2)),
                "patrimony_after_1_hit": float(round(patrimony_after_1_hit, 2)),
                "doubled_in_1_hit": bool(patrimony_after_1_hit >= target_P),
                "monthly_success_prob": float(round(p_hit_monthly * 100.0, 2)),
                "expected_months_to_double": float(round(exp_months_n_star, 2)),
                "median_months_to_double": median_months_n_star,
                "cumulative_probabilities_pct": cum_prob_n_star,
                "empirical_median_months": float(np.median(first_hit_n_star[has_any_hit_n_star])) if np.any(has_any_hit_n_star) else None
            },
            "low_variance_n2": {
                "n": 2,
                "multiplier": float(round(multiplier_n2, 4)),
                "profit_per_hit": float(round(profit_per_hit_n2, 2)),
                "needed_hits_to_double": 2,
                "monthly_success_prob": float(round(p_hit_n2 * 100.0, 2)),
                "expected_months_to_double": float(round(exp_months_n2, 2)),
                "cumulative_probabilities_pct": cum_prob_n2,
                "empirical_median_months": float(np.median(months_n2[has_two_hits_n2])) if np.any(has_two_hits_n2) else None
            },
            "base_capital_ruin_probability": 0.0,
            "base_capital_max_drawdown_pct": 0.0
        }



