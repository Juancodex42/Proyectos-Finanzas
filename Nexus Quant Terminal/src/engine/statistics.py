import math
import numpy as np
import pandas as pd

class StatisticsEngine:
    def analyze(self, trades: list[dict], df: pd.DataFrame = None) -> dict:
        if not trades:
            return {}
            
        wins = sum(1 for t in trades if t['result'] == 'WIN')
        losses = sum(1 for t in trades if t['result'] == 'LOSS')
        ties = sum(1 for t in trades if t['result'] == 'TIE')
        total = len(trades)
        decisive = wins + losses  # Operaciones con resultado definitivo (excluye empates)

        # Win Rate Bruto (denominador = total incluyendo empates)
        win_rate = wins / total if total > 0 else 0
        # Win Rate Efectivo (denominador = solo decisivas; métrica de calidad real)
        win_rate_effective = wins / decisive if decisive > 0 else 0

        # Intervalo de Confianza 95% - Wilson Score para win_rate_effective y win_rate gross
        z = 1.96  # z para 95%
        n_decisive = decisive
        if n_decisive > 0:
            p_eff = win_rate_effective
            denom_w = 1 + z**2 / n_decisive
            center_w = (p_eff + z**2 / (2 * n_decisive)) / denom_w
            margin_w = (z * math.sqrt(p_eff * (1 - p_eff) / n_decisive + z**2 / (4 * n_decisive**2))) / denom_w
            wilson_ci_low = max(0.0, center_w - margin_w)
            wilson_ci_high = min(1.0, center_w + margin_w)
        else:
            wilson_ci_low, wilson_ci_high = 0.0, 1.0

        if total > 0:
            p_gross = win_rate
            denom_g = 1 + z**2 / total
            center_g = (p_gross + z**2 / (2 * total)) / denom_g
            margin_g = (z * math.sqrt(p_gross * (1 - p_gross) / total + z**2 / (4 * total**2))) / denom_g
            wilson_gross_low = max(0.0, center_g - margin_g)
            wilson_gross_high = min(1.0, center_g + margin_g)
        else:
            wilson_gross_low, wilson_gross_high = 0.0, 1.0

        # Expectativa Matemática por operación (Trading Clásico Asimétrico y Continuo)
        pnls = [float(t.get('pnl', 0.0)) for t in trades]
        net_pnl = float(np.sum(pnls)) if pnls else 0.0
        avg_trade_pnl = float(net_pnl / total) if total > 0 else 0.0

        r_multiples = []
        for t in trades:
            if 'r_multiple' in t and t['r_multiple'] is not None:
                r_multiples.append(float(t['r_multiple']))
            else:
                b_size = float(t.get('bet_size', 0.0))
                pnl_val = float(t.get('pnl', 0.0))
                if b_size > 0:
                    r_multiples.append(pnl_val / b_size)
                else:
                    r_multiples.append(pnl_val / 33.3333)

        expected_value_r = float(np.mean(r_multiples)) if r_multiples else 0.0
        expected_value_per_trade = avg_trade_pnl

        gross_profit = float(sum(p for p in pnls if p > 0))
        gross_loss = float(abs(sum(p for p in pnls if p < 0)))
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 1.0)

        basic = {
            "win_rate": win_rate,
            "win_rate_effective": win_rate_effective,
            "wilson_ci_95": [wilson_ci_low, wilson_ci_high],
            "wilson_ci_gross_95": [wilson_gross_low, wilson_gross_high],
            "expected_value_per_trade": expected_value_per_trade,
            "expected_value_r": expected_value_r,
            "avg_trade_pnl": avg_trade_pnl,
            "profit_factor": profit_factor,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "total": total,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "decisive": decisive,
            "net_pnl": net_pnl
        }
        
        results = [1 if t['result'] == 'WIN' else 0 for t in trades if t['result'] != 'TIE']
        
        # Streaks
        win_streak_distribution = {}
        loss_streak_distribution = {}
        max_win_streak = 0
        max_loss_streak = 0
        current_streak = 0
        current_type = None
        
        win_streaks = []
        loss_streaks = []
        
        for r in results:
            if current_type is None:
                current_type = r
                current_streak = 1
            elif r == current_type:
                current_streak += 1
            else:
                if current_type == 1:
                    max_win_streak = max(max_win_streak, current_streak)
                    win_streaks.append(current_streak)
                    win_streak_distribution[current_streak] = win_streak_distribution.get(current_streak, 0) + 1
                else:
                    max_loss_streak = max(max_loss_streak, current_streak)
                    loss_streaks.append(current_streak)
                    loss_streak_distribution[current_streak] = loss_streak_distribution.get(current_streak, 0) + 1
                current_type = r
                current_streak = 1
                
        if current_type == 1:
            max_win_streak = max(max_win_streak, current_streak)
            win_streaks.append(current_streak)
            win_streak_distribution[current_streak] = win_streak_distribution.get(current_streak, 0) + 1
        elif current_type == 0:
            max_loss_streak = max(max_loss_streak, current_streak)
            loss_streaks.append(current_streak)
            loss_streak_distribution[current_streak] = loss_streak_distribution.get(current_streak, 0) + 1
        
        avg_win_streak = np.mean(win_streaks) if win_streaks else 0
        avg_loss_streak = np.mean(loss_streaks) if loss_streaks else 0
        
        combined_streak_dist = {}
        for k, v in win_streak_distribution.items():
            combined_streak_dist[k] = combined_streak_dist.get(k, 0) + v
        for k, v in loss_streak_distribution.items():
            combined_streak_dist[k] = combined_streak_dist.get(k, 0) + v

        streaks = {
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
            "avg_win_streak": avg_win_streak,
            "avg_loss_streak": avg_loss_streak,
            "win_streak_distribution": win_streak_distribution,
            "loss_streak_distribution": loss_streak_distribution,
            "streak_distribution": combined_streak_dist
        }
        
        # Dependency
        n = len(results)
        p_hat = win_rate_effective
        autocorr = []
        
        denom = sum((x - p_hat)**2 for x in results)
        if denom > 0:
            for k in range(1, min(11, n)):
                num = sum((results[i] - p_hat)*(results[i+k] - p_hat) for i in range(n-k))
                autocorr.append(num / denom)
                
        win_given_win = 0
        loss_given_win = 0
        win_given_loss = 0
        loss_given_loss = 0
        
        if n > 1:
            for i in range(1, n):
                if results[i-1] == 1 and results[i] == 1: win_given_win += 1
                if results[i-1] == 1 and results[i] == 0: loss_given_win += 1
                if results[i-1] == 0 and results[i] == 1: win_given_loss += 1
                if results[i-1] == 0 and results[i] == 0: loss_given_loss += 1
                
        total_prev_win = win_given_win + loss_given_win
        total_prev_loss = win_given_loss + loss_given_loss
        
        # Runs Test (Wald-Wolfowitz)
        n1 = sum(results)
        n2 = n - n1
        runs_count = len(win_streaks) + len(loss_streaks)
        if n > 1 and n1 > 0 and n2 > 0:
            mu_r = 1.0 + (2.0 * n1 * n2) / n
            var_r = (2.0 * n1 * n2 * (2.0 * n1 * n2 - n)) / ((n ** 2) * (n - 1))
            if var_r > 0:
                z_score = (runs_count - mu_r) / np.sqrt(var_r)
                runs_test_pvalue = float(math.erfc(abs(z_score) / np.sqrt(2.0)))
            else:
                runs_test_pvalue = 1.0
        else:
            runs_test_pvalue = 1.0
        
        dependency = {
            "autocorrelation": autocorr,
            "p_win_given_win": win_given_win / total_prev_win if total_prev_win else 0,
            "p_win_given_loss": win_given_loss / total_prev_loss if total_prev_loss else 0,
            "p_loss_given_win": loss_given_win / total_prev_win if total_prev_win else 0,
            "p_loss_given_loss": loss_given_loss / total_prev_loss if total_prev_loss else 0,
            "runs_test_pvalue": runs_test_pvalue
        }
        
        # Variance
        var = (p_hat * (1 - p_hat)) / n if n > 0 else 0
        std_dev = float(np.sqrt(var))
        # CI normal (complementa Wilson CI del basic block para serie completa)
        ci_95_normal = [max(0.0, p_hat - 1.96 * std_dev), min(1.0, p_hat + 1.96 * std_dev)]

        # Sharpe ratio normalizado sobre retornos ponderados (pnl / bet_size)
        returns_list = [
            t.get('pnl', 0.0) / t.get('bet_size', 1.0)
            for t in trades
            if t.get('bet_size', 0.0) > 0.0
        ]
        if not returns_list:
            returns_list = [t.get('pnl', 0.0) for t in trades]
            
        ret_mean = np.mean(returns_list) if len(returns_list) > 0 else 0.0
        ret_std = np.std(returns_list, ddof=1) if len(returns_list) > 1 else 0.0
        # Sharpe ratio unitario por operación (evita escalado erróneo por la raíz de N total)
        sharpe_val = float(ret_mean / ret_std) if ret_std > 0 else 0.0

        variance = {
            "variance": float(var),
            "std_dev": float(std_dev),
            "confidence_interval_95": ci_95_normal,
            "sharpe_ratio": sharpe_val
        }
        
        # Temporal
        by_hour = {}
        by_day = {}
        for t in trades:
            if t.get('result') == 'TIE':
                continue
            t_val = t.get('time')
            if t_val is None:
                continue
            try:
                if isinstance(t_val, (int, float, np.number)):
                    unit = 'ms' if t_val > 2**32 else 's'
                    time_obj = pd.to_datetime(t_val, unit=unit, errors='coerce')
                else:
                    time_obj = pd.to_datetime(t_val, errors='coerce')
                if pd.isna(time_obj):
                    continue
                hour = time_obj.hour
                day = time_obj.day_name()
                if hour not in by_hour: by_hour[hour] = []
                by_hour[hour].append(1 if t['result'] == 'WIN' else 0)
                if day not in by_day: by_day[day] = []
                by_day[day].append(1 if t['result'] == 'WIN' else 0)
            except Exception as ex:
                print(f"Error parsing trade time {t_val}: {ex}")
            
        by_hour = {k: np.mean(v) for k, v in by_hour.items()}
        by_day = {k: np.mean(v) for k, v in by_day.items()}
        
        temporal = {
            "by_hour": by_hour,
            "by_day": by_day
        }
        
        market_state = {
            "high_vol_wr": 0, "low_vol_wr": 0, "trending_wr": 0, "ranging_wr": 0
        }
        
        if df is not None:
            try:
                high = df['high']
                low = df['low']
                close = df['close']
                tr1 = high - low
                tr2 = (high - close.shift(1)).abs()
                tr3 = (low - close.shift(1)).abs()
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr = tr.rolling(window=14).mean()
                
                sma = close.rolling(20).mean()
                dev = (close - sma).abs() / sma

                # Rolling median de ATR y desviación (ventana de 100 velas) para eliminar look-ahead bias
                # La mediana se calcula solo sobre datos históricos previos a cada punto
                atr_rolling_median = atr.rolling(window=100, min_periods=14).median()
                dev_rolling_median = dev.rolling(window=100, min_periods=20).median()
                
                high_vol_trades = []
                low_vol_trades = []
                trend_trades = []
                range_trades = []
                
                for t in trades:
                    if t.get('result') == 'TIE':
                        continue  # Los empates no aportan a la distribución por estado de mercado
                    idx = t.get('index', -1)
                    trade_result = 1 if t['result'] == 'WIN' else 0
                    if idx is not None and isinstance(idx, (int, np.integer)) and 0 <= idx < len(atr):
                        local_atr_med = atr_rolling_median.iloc[idx]
                        if not np.isnan(atr.iloc[idx]) and not np.isnan(local_atr_med):
                            if atr.iloc[idx] > local_atr_med:
                                high_vol_trades.append(trade_result)
                            else:
                                low_vol_trades.append(trade_result)

                    if idx is not None and isinstance(idx, (int, np.integer)) and 0 <= idx < len(dev):
                        local_dev_med = dev_rolling_median.iloc[idx]
                        if not np.isnan(dev.iloc[idx]) and not np.isnan(local_dev_med):
                            if dev.iloc[idx] > local_dev_med:
                                trend_trades.append(trade_result)
                            else:
                                range_trades.append(trade_result)
                            
                market_state = {
                    "high_vol_wr": float(np.mean(high_vol_trades)) if high_vol_trades else 0,
                    "low_vol_wr": float(np.mean(low_vol_trades)) if low_vol_trades else 0,
                    "trending_wr": float(np.mean(trend_trades)) if trend_trades else 0,
                    "ranging_wr": float(np.mean(range_trades)) if range_trades else 0
                }
            except Exception:
                pass
            
        # Markov estimation & Stationary Distribution
        p_ww = win_given_win / total_prev_win if total_prev_win else win_rate
        p_lw = loss_given_win / total_prev_win if total_prev_win else (1.0 - win_rate)
        p_wl = win_given_loss / total_prev_loss if total_prev_loss else win_rate
        p_ll = loss_given_loss / total_prev_loss if total_prev_loss else (1.0 - win_rate)
        
        # Stationary distribution calculation: pi * P = pi
        denom_stat = (1.0 - p_ww + p_wl)
        if abs(denom_stat) > 1e-9:
            pi_win = max(0.0, min(1.0, p_wl / denom_stat))
            pi_loss = max(0.0, min(1.0, (1.0 - p_ww) / denom_stat))
        else:
            pi_win = win_rate
            pi_loss = 1.0 - win_rate

        # Sequence of estimated Markov states (0 = Loss state, 1 = Win state)
        estimated_states = results if results else []

        markov = {
            "transition_matrix": [
                [p_ww, p_lw],
                [p_wl, p_ll]
            ],
            "state_probs": [float(pi_win), float(pi_loss)],
            "estimated_states": estimated_states,
            "expected_win_streak": float(1.0 / (1.0 - p_ww)) if p_ww < 1.0 else float(n),
            "expected_loss_streak": float(1.0 / (1.0 - p_ll)) if p_ll < 1.0 else float(n)
        }
        
        return {
            "win_rate": win_rate,
            "win_rate_effective": win_rate_effective,
            "wilson_ci_95": [wilson_ci_low, wilson_ci_high],
            "wilson_ci_gross_95": [wilson_gross_low, wilson_gross_high],
            "total_trades": total,
            "net_pnl": net_pnl,
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
            "basic": basic,
            "streaks": streaks,
            "dependency": dependency,
            "variance": variance,
            "temporal": temporal,
            "market_state": market_state,
            "markov": markov
        }

