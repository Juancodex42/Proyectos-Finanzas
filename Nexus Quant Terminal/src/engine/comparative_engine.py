import os
import sys
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple

# Tolerancia epsilon para comparación de precios
_PRICE_EPS = 1e-8

class ComparativeQuantitativeEngine:
    """
    Motor cuantitativo para comparar de forma justa ('ADECUADA')
    el comportamiento de:
      1) Opciones Binarias (Fixed Payout 85%, Flat Risk y Esquema Paroli/Balas).
      2) Trading Clásico con Apalancamiento (1x, 2x, 5x, 10x, 20x, 50x) con:
         - Modelo A: Riesgo de Capital Normalizado (% de cuenta idéntico al trade de binarias)
         - Modelo B: Exposición Nominal Fija y Salida por Tiempo (mismo horizonte N velas que binaria)
         - Modelo C: Take Profit / Stop Loss Asimétrico con Ratio R:R (1:1, 1:1.5, 1:2)
    """

    def __init__(self, initial_capital: float = 1000.0, target_capital: float = 2000.0, ruin_capital: float = 200.0):
        self.initial_capital = float(initial_capital)
        self.target_capital = float(target_capital)
        self.ruin_capital = float(ruin_capital)

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
        high = df['high'].to_numpy(dtype=np.float64)
        low = df['low'].to_numpy(dtype=np.float64)
        close = df['close'].to_numpy(dtype=np.float64)
        n = len(df)
        if n < period:
            return np.zeros(n)
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        for i in range(1, n):
            tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        atr = np.zeros(n)
        atr[period-1] = np.mean(tr[:period])
        for i in range(period, n):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
        return atr

    def simulate_binary_fixed_risk(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        expiry_candles: int = 1,
        payout: float = 0.85,
        risk_pct_per_trade: float = 0.02, # 2% por trade
        slippage_pct: float = 0.0001
    ) -> Dict[str, Any]:
        """
        Simula Opciones Binarias con gestión de riesgo fija proporcional (% de equity).
        """
        n = len(df)
        open_prices = df['open'].to_numpy(dtype=np.float64)
        close_prices = df['close'].to_numpy(dtype=np.float64)
        
        sig_arr = np.zeros(n, dtype=np.int8)
        if hasattr(signals, 'reindex'):
            sig_series = signals.reindex(df.index)
        else:
            sig_series = pd.Series(signals, index=df.index)
        sig_arr[sig_series == 'CALL'] = 1
        sig_arr[sig_series == 'PUT'] = -1
        
        signal_indices = np.flatnonzero(sig_arr != 0)
        valid_indices = []
        next_allowed = 0
        for idx in signal_indices:
            if idx >= next_allowed and (idx + expiry_candles) < n:
                valid_indices.append(idx)
                next_allowed = idx + expiry_candles
                
        if not valid_indices:
            return self._empty_result("Binarias (Flat Risk)")

        idx_arr = np.array(valid_indices, dtype=np.int64)
        sig_type = sig_arr[idx_arr]
        
        entry_raw = open_prices[idx_arr + 1]
        exit_raw = close_prices[idx_arr + expiry_candles]
        
        entry_prices = np.where(sig_type == 1, entry_raw * (1.0 + slippage_pct), entry_raw * (1.0 - slippage_pct))
        price_diff = exit_raw - entry_prices
        
        is_win = np.where(sig_type == 1, price_diff > _PRICE_EPS, price_diff < -_PRICE_EPS)
        is_tie = np.abs(price_diff) <= _PRICE_EPS
        is_loss = ~is_win & ~is_tie
        
        equity = self.initial_capital
        equity_curve = [equity]
        trade_pnls = []
        trade_returns = []
        reached_target = False
        reached_ruin = False
        trades_to_double = None
        
        for i in range(len(idx_arr)):
            stake = equity * risk_pct_per_trade
            if is_win[i]:
                pnl = stake * payout
                ret = risk_pct_per_trade * payout
            elif is_tie[i]:
                pnl = 0.0
                ret = 0.0
            else:
                pnl = -stake
                ret = -risk_pct_per_trade
                
            equity += pnl
            equity_curve.append(equity)
            trade_pnls.append(pnl)
            trade_returns.append(ret)
            
            if equity >= self.target_capital and not reached_target:
                reached_target = True
                trades_to_double = i + 1
            if equity <= self.ruin_capital:
                reached_ruin = True
                break

        return self._compute_performance_metrics(
            name=f"Binarias Flat Risk ({risk_pct_per_trade*100:.0f}%)",
            trade_pnls=trade_pnls,
            trade_returns=trade_returns,
            equity_curve=equity_curve,
            is_win=is_win[:len(trade_pnls)],
            is_loss=is_loss[:len(trade_pnls)],
            is_tie=is_tie[:len(trade_pnls)],
            reached_target=reached_target,
            reached_ruin=reached_ruin,
            trades_to_double=trades_to_double
        )

    def simulate_binary_paroli_bullets(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        expiry_candles: int = 1,
        payout: float = 0.85,
        committed_risk_pct: float = 0.20, # Arriesgar el 20% del capital base
        n_bullets: int = 6,              # Dividido en 6 balas (3.33% por bala)
        streak_target: int = 3,          # Racha de 3 seguidas para duplicar/capitalizar
        slippage_pct: float = 0.0001
    ) -> Dict[str, Any]:
        """
        Simula Opciones Binarias con el Esquema Barbell / Paroli (Balas Compuestas).
        Estrategia de asimetría positiva: arriesga una bala pequeña; si gana, reinvierte la ganancia 3 veces.
        """
        n = len(df)
        open_prices = df['open'].to_numpy(dtype=np.float64)
        close_prices = df['close'].to_numpy(dtype=np.float64)
        
        sig_arr = np.zeros(n, dtype=np.int8)
        if hasattr(signals, 'reindex'):
            sig_series = signals.reindex(df.index)
        else:
            sig_series = pd.Series(signals, index=df.index)
        sig_arr[sig_series == 'CALL'] = 1
        sig_arr[sig_series == 'PUT'] = -1
        
        signal_indices = np.flatnonzero(sig_arr != 0)
        valid_indices = []
        next_allowed = 0
        for idx in signal_indices:
            if idx >= next_allowed and (idx + expiry_candles) < n:
                valid_indices.append(idx)
                next_allowed = idx + expiry_candles
                
        if not valid_indices:
            return self._empty_result("Binarias Paroli Balas")

        idx_arr = np.array(valid_indices, dtype=np.int64)
        sig_type = sig_arr[idx_arr]
        
        entry_raw = open_prices[idx_arr + 1]
        exit_raw = close_prices[idx_arr + expiry_candles]
        
        entry_prices = np.where(sig_type == 1, entry_raw * (1.0 + slippage_pct), entry_raw * (1.0 - slippage_pct))
        price_diff = exit_raw - entry_prices
        
        is_win = np.where(sig_type == 1, price_diff > _PRICE_EPS, price_diff < -_PRICE_EPS)
        is_tie = np.abs(price_diff) <= _PRICE_EPS
        is_loss = ~is_win & ~is_tie

        equity = self.initial_capital
        equity_curve = [equity]
        trade_pnls = []
        trade_returns = []
        reached_target = False
        reached_ruin = False
        trades_to_double = None
        
        # Paroli state
        current_streak = 0
        base_bullet = (self.initial_capital * committed_risk_pct) / n_bullets
        current_bet = base_bullet
        
        for i in range(len(idx_arr)):
            if is_win[i]:
                current_streak += 1
                if current_streak == streak_target:
                    # Completed streak: Net profit = base_bullet * ((1+payout)^streak - 1)
                    pnl = current_bet * payout
                    equity += pnl
                    trade_pnls.append(pnl)
                    trade_returns.append(pnl / equity)
                    # Reset streak
                    current_streak = 0
                    base_bullet = (equity * committed_risk_pct) / n_bullets
                    current_bet = base_bullet
                else:
                    # Reinvest profit + stake
                    pnl = current_bet * payout
                    trade_pnls.append(pnl)
                    trade_returns.append(pnl / equity)
                    current_bet = current_bet * (1.0 + payout)
            elif is_tie[i]:
                trade_pnls.append(0.0)
                trade_returns.append(0.0)
            else:
                # Lost bullet: loss is exactly the base_bullet
                pnl = -base_bullet if current_streak == 0 else -(current_bet / (1.0 + payout))
                equity -= base_bullet  # Only the original bullet is lost from equity
                trade_pnls.append(-base_bullet)
                trade_returns.append(-base_bullet / equity)
                current_streak = 0
                base_bullet = (equity * committed_risk_pct) / n_bullets
                current_bet = base_bullet
                
            equity_curve.append(equity)
            if equity >= self.target_capital and not reached_target:
                reached_target = True
                trades_to_double = i + 1
            if equity <= self.ruin_capital:
                reached_ruin = True
                break

        return self._compute_performance_metrics(
            name=f"Binarias Paroli ({streak_target} Rachas/6 Balas)",
            trade_pnls=trade_pnls,
            trade_returns=trade_returns,
            equity_curve=equity_curve,
            is_win=is_win[:len(trade_pnls)],
            is_loss=is_loss[:len(trade_pnls)],
            is_tie=is_tie[:len(trade_pnls)],
            reached_target=reached_target,
            reached_ruin=reached_ruin,
            trades_to_double=trades_to_double
        )

    def simulate_classic_leveraged_fixed_risk(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        leverage: float = 1.0,
        risk_pct_per_trade: float = 0.02, # 2% de cuenta en Stop Loss
        rr_ratio: float = 1.5,             # Take Profit = 1.5 * Risk
        atr_multiplier_sl: float = 1.5,   # SL en 1.5 * ATR
        fee_pct: float = 0.0005,          # Comisiones Taker 0.05% por entrada y salida
        slippage_pct: float = 0.0002
    ) -> Dict[str, Any]:
        """
        Trading Clásico con RIESGO DE CAPITAL NORMALIZADO (Fair Comparison):
        Arriesga el mismo 2% que en binarias por trade. El apalancamiento (leverage)
        permite financiar el tamaño de posición nominal necesario sin exceder el margen.
        Si la posición requerida supera el apalancamiento máximo permitido por el broker, se acota.
        """
        n = len(df)
        open_prices = df['open'].to_numpy(dtype=np.float64)
        high_prices = df['high'].to_numpy(dtype=np.float64)
        low_prices = df['low'].to_numpy(dtype=np.float64)
        close_prices = df['close'].to_numpy(dtype=np.float64)
        atr = self.calculate_atr(df, 14)
        
        sig_arr = np.zeros(n, dtype=np.int8)
        if hasattr(signals, 'reindex'):
            sig_series = signals.reindex(df.index)
        else:
            sig_series = pd.Series(signals, index=df.index)
        sig_arr[sig_series == 'CALL'] = 1
        sig_arr[sig_series == 'PUT'] = -1
        
        signal_indices = np.flatnonzero(sig_arr != 0)
        
        equity = self.initial_capital
        equity_curve = [equity]
        trade_pnls = []
        trade_returns = []
        wins_list = []
        losses_list = []
        ties_list = []
        reached_target = False
        reached_ruin = False
        trades_to_double = None
        
        i = 0
        while i < len(signal_indices):
            idx = signal_indices[i]
            if idx + 1 >= n or atr[idx] <= 0:
                i += 1
                continue
                
            sig = sig_arr[idx]
            entry_raw = open_prices[idx + 1]
            entry_price = entry_raw * (1.0 + slippage_pct) if sig == 1 else entry_raw * (1.0 - slippage_pct)
            
            sl_distance = atr[idx] * atr_multiplier_sl
            sl_pct = sl_distance / entry_price
            if sl_pct <= 0:
                i += 1
                continue
                
            # Risk sizing: Max loss = equity * risk_pct_per_trade
            target_risk_dollars = equity * risk_pct_per_trade
            ideal_position_size = target_risk_dollars / sl_pct
            
            # Position size capped by leverage
            max_allowed_position = equity * leverage
            actual_position_size = min(ideal_position_size, max_allowed_position)
            
            sl_price = entry_price - sl_distance if sig == 1 else entry_price + sl_distance
            tp_price = entry_price + (sl_distance * rr_ratio) if sig == 1 else entry_price - (sl_distance * rr_ratio)
            
            # Walk forward through candles until SL, TP or max holding (e.g. 50 candles)
            trade_closed = False
            trade_pnl = 0.0
            trade_result = 'LOSS'
            exit_idx = idx + 1
            max_hold = min(idx + 50, n - 1)
            
            for k in range(idx + 1, max_hold + 1):
                cur_high = high_prices[k]
                cur_low = low_prices[k]
                
                if sig == 1: # LONG
                    if cur_low <= sl_price:
                        # SL hit
                        loss_pct = (sl_price - entry_price) / entry_price
                        trade_pnl = actual_position_size * loss_pct - (actual_position_size * 2 * fee_pct)
                        trade_result = 'LOSS'
                        trade_closed = True
                        exit_idx = k
                        break
                    elif cur_high >= tp_price:
                        # TP hit
                        gain_pct = (tp_price - entry_price) / entry_price
                        trade_pnl = actual_position_size * gain_pct - (actual_position_size * 2 * fee_pct)
                        trade_result = 'WIN'
                        trade_closed = True
                        exit_idx = k
                        break
                else: # SHORT
                    if cur_high >= sl_price:
                        # SL hit
                        loss_pct = (entry_price - sl_price) / entry_price
                        trade_pnl = actual_position_size * loss_pct - (actual_position_size * 2 * fee_pct)
                        trade_result = 'LOSS'
                        trade_closed = True
                        exit_idx = k
                        break
                    elif cur_low <= tp_price:
                        # TP hit
                        gain_pct = (entry_price - tp_price) / entry_price
                        trade_pnl = actual_position_size * gain_pct - (actual_position_size * 2 * fee_pct)
                        trade_result = 'WIN'
                        trade_closed = True
                        exit_idx = k
                        break
                        
            if not trade_closed:
                # Close at market at end of window
                cur_close = close_prices[max_hold]
                pct_diff = (cur_close - entry_price)/entry_price if sig == 1 else (entry_price - cur_close)/entry_price
                trade_pnl = actual_position_size * pct_diff - (actual_position_size * 2 * fee_pct)
                trade_result = 'WIN' if trade_pnl > 0 else 'LOSS'
                exit_idx = max_hold

            equity += trade_pnl
            equity_curve.append(equity)
            trade_pnls.append(trade_pnl)
            trade_returns.append(trade_pnl / (equity - trade_pnl) if (equity - trade_pnl) > 0 else -1.0)
            
            wins_list.append(1 if trade_result == 'WIN' else 0)
            losses_list.append(1 if trade_result == 'LOSS' else 0)
            ties_list.append(0)
            
            if equity >= self.target_capital and not reached_target:
                reached_target = True
                trades_to_double = len(trade_pnls)
            if equity <= self.ruin_capital:
                reached_ruin = True
                break
                
            # Advance to next trade after exit_idx
            while i < len(signal_indices) and signal_indices[i] <= exit_idx:
                i += 1

        return self._compute_performance_metrics(
            name=f"Clásico Risk-Norm ({leverage:.0f}x, R:R 1:{rr_ratio:.1f})",
            trade_pnls=trade_pnls,
            trade_returns=trade_returns,
            equity_curve=equity_curve,
            is_win=np.array(wins_list, dtype=bool),
            is_loss=np.array(losses_list, dtype=bool),
            is_tie=np.array(ties_list, dtype=bool),
            reached_target=reached_target,
            reached_ruin=reached_ruin,
            trades_to_double=trades_to_double
        )

    def simulate_classic_fixed_notional_leverage(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        leverage: float = 10.0,
        expiry_candles: int = 1,
        fee_pct: float = 0.0005,
        slippage_pct: float = 0.0002
    ) -> Dict[str, Any]:
        """
        Trading Clásico con APALANCAMIENTO NOMINAL FIJO y Salida por Tiempo (Idéntico horizonte N velas que binarias).
        El PnL es = Notional * Return - Fees.
        Permite comparar el efecto del Volatility Drag en apalancamiento 1x, 2x, 5x, 10x, 20x, 50x.
        """
        n = len(df)
        open_prices = df['open'].to_numpy(dtype=np.float64)
        close_prices = df['close'].to_numpy(dtype=np.float64)
        
        sig_arr = np.zeros(n, dtype=np.int8)
        if hasattr(signals, 'reindex'):
            sig_series = signals.reindex(df.index)
        else:
            sig_series = pd.Series(signals, index=df.index)
        sig_arr[sig_series == 'CALL'] = 1
        sig_arr[sig_series == 'PUT'] = -1
        
        signal_indices = np.flatnonzero(sig_arr != 0)
        valid_indices = []
        next_allowed = 0
        for idx in signal_indices:
            if idx >= next_allowed and (idx + expiry_candles) < n:
                valid_indices.append(idx)
                next_allowed = idx + expiry_candles
                
        if not valid_indices:
            return self._empty_result(f"Clásico Notional {leverage}x")

        idx_arr = np.array(valid_indices, dtype=np.int64)
        sig_type = sig_arr[idx_arr]
        
        entry_raw = open_prices[idx_arr + 1]
        exit_raw = close_prices[idx_arr + expiry_candles]
        
        entry_prices = np.where(sig_type == 1, entry_raw * (1.0 + slippage_pct), entry_raw * (1.0 - slippage_pct))
        price_diff = exit_raw - entry_prices
        raw_pct_return = np.where(sig_type == 1, (exit_raw - entry_prices)/entry_prices, (entry_prices - exit_raw)/entry_prices)
        
        equity = self.initial_capital
        equity_curve = [equity]
        trade_pnls = []
        trade_returns = []
        wins_list = []
        losses_list = []
        ties_list = []
        reached_target = False
        reached_ruin = False
        trades_to_double = None
        
        for i in range(len(idx_arr)):
            position_size = equity * leverage
            fees = position_size * 2 * fee_pct
            pnl = (position_size * raw_pct_return[i]) - fees
            
            # Evitar equity negativa por liquidación
            if equity + pnl <= 0:
                pnl = -equity
                equity = 0.0
                trade_pnls.append(pnl)
                trade_returns.append(-1.0)
                equity_curve.append(equity)
                reached_ruin = True
                losses_list.append(1)
                wins_list.append(0)
                ties_list.append(0)
                break
                
            equity += pnl
            equity_curve.append(equity)
            trade_pnls.append(pnl)
            trade_returns.append(pnl / (equity - pnl) if (equity - pnl) > 0 else 0.0)
            
            if pnl > 0:
                wins_list.append(1)
                losses_list.append(0)
                ties_list.append(0)
            elif pnl < 0:
                wins_list.append(0)
                losses_list.append(1)
                ties_list.append(0)
            else:
                wins_list.append(0)
                losses_list.append(0)
                ties_list.append(1)
                
            if equity >= self.target_capital and not reached_target:
                reached_target = True
                trades_to_double = i + 1
            if equity <= self.ruin_capital:
                reached_ruin = True
                break

        return self._compute_performance_metrics(
            name=f"Clásico Time-Exit ({leverage:.0f}x Apalancado)",
            trade_pnls=trade_pnls,
            trade_returns=trade_returns,
            equity_curve=equity_curve,
            is_win=np.array(wins_list, dtype=bool),
            is_loss=np.array(losses_list, dtype=bool),
            is_tie=np.array(ties_list, dtype=bool),
            reached_target=reached_target,
            reached_ruin=reached_ruin,
            trades_to_double=trades_to_double
        )

    def run_monte_carlo_duplication(
        self,
        strategy_result: Dict[str, Any],
        n_simulations: int = 10000,
        max_trades_per_path: int = 500
    ) -> Dict[str, Any]:
        """
        Simulación Monte Carlo Vectorizada de 10,000 caminos para estimar:
        - P(Duplicar Patrimonio antes de Ruina)
        - P(Ruina antes de Duplicar)
        - Número medio de trades para duplicar
        - Distribución de saldo final
        """
        trade_returns = strategy_result.get("trade_returns", [])
        if len(trade_returns) < 5:
            return {
                "prob_double": 0.0,
                "prob_ruin": 0.0,
                "prob_undecided": 1.0,
                "avg_trades_to_double": None,
                "median_final_equity": self.initial_capital,
                "p5_final_equity": self.initial_capital,
                "p95_final_equity": self.initial_capital
            }

        returns_arr = np.array(trade_returns, dtype=np.float64)
        returns_arr = np.clip(returns_arr, -0.999, 10.0)
        # --- AUDIT GUARANTEE: MONTE CARLO BLOCK BOOTSTRAP ---
        # El remuestreo simple IID (np.random.choice sin memoria) destruye las rachas de ganancias/pérdidas
        # necesarias para evaluar esquemas secuenciales (Paroli, antimartingala, streak betting).
        # El Block Bootstrap muestrea bloques contiguos de operaciones consecutivas, preservando
        # la autocorrelación serial y las propiedades de Markov reales del historial.
        n_samples = len(returns_arr)
        block_size = max(2, min(10, n_samples // 4)) if n_samples >= 8 else 1
        if block_size > 1 and n_samples > block_size:
            n_blocks = int(np.ceil(max_trades_per_path / block_size))
            start_indices = np.random.randint(0, n_samples - block_size + 1, size=(n_simulations, n_blocks))
            sampled_indices = np.zeros((n_simulations, n_blocks * block_size), dtype=int)
            for b in range(block_size):
                sampled_indices[:, b::block_size] = start_indices + b
            sampled_indices = sampled_indices[:, :max_trades_per_path]
            sampled_growth = 1.0 + returns_arr[sampled_indices]
        else:
            sampled_growth = 1.0 + np.random.choice(returns_arr, size=(n_simulations, max_trades_per_path), replace=True)
        # Compute equity trajectories vectorially
        equity_paths = self.initial_capital * np.cumprod(sampled_growth, axis=1)
        
        hit_target = equity_paths >= self.target_capital
        hit_ruin = equity_paths <= self.ruin_capital
        
        has_target = np.any(hit_target, axis=1)
        has_ruin = np.any(hit_ruin, axis=1)
        
        target_step = np.where(has_target, np.argmax(hit_target, axis=1) + 1, max_trades_per_path + 1)
        ruin_step = np.where(has_ruin, np.argmax(hit_ruin, axis=1) + 1, max_trades_per_path + 1)
        
        doubled_mask = (has_target) & (target_step < ruin_step)
        ruined_mask = (has_ruin) & (ruin_step <= target_step)
        
        prob_double = float(np.sum(doubled_mask) / n_simulations)
        prob_ruin = float(np.sum(ruined_mask) / n_simulations)
        prob_undecided = float(1.0 - (prob_double + prob_ruin))
        
        steps_to_double = target_step[doubled_mask]
        avg_trades_double = float(np.mean(steps_to_double)) if len(steps_to_double) > 0 else None
        
        final_eq = equity_paths[:, -1]
        
        return {
            "prob_double": prob_double,
            "prob_ruin": prob_ruin,
            "prob_undecided": prob_undecided,
            "avg_trades_to_double": avg_trades_double,
            "median_final_equity": float(np.median(final_eq)),
            "p5_final_equity": float(np.percentile(final_eq, 5)),
            "p95_final_equity": float(np.percentile(final_eq, 95))
        }

    def evaluate_strategy_profile(self, name: str, trade_pnls: list[float], trade_returns: list[float], equity_curve: list[float]) -> dict:
        total_trades = len(trade_pnls)
        if total_trades == 0:
            return {
                "name": name,
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "ev_per_trade": 0.0,
                "ev_percent": 0.0,
                "net_pnl": 0.0,
                "final_equity": self.initial_capital
            }
        
        wins = sum(1 for p in trade_pnls if p > 1e-4)
        losses = sum(1 for p in trade_pnls if p < -1e-4)
        ties = total_trades - (wins + losses)
        win_rate = (wins / total_trades) if total_trades > 0 else 0.0
        
        gross_profit = sum(p for p in trade_pnls if p > 0)
        gross_loss = abs(sum(p for p in trade_pnls if p < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
        
        # Max Drawdown
        eq_arr = np.array(equity_curve)
        peaks = np.maximum.accumulate(eq_arr)
        drawdowns = np.where(peaks > 0, (peaks - eq_arr) / peaks, 0.0)
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
        
        # Sharpe & Sortino (per trade normalized returns)
        ret_arr = np.array(trade_returns)
        mean_ret = float(np.mean(ret_arr)) if len(ret_arr) > 0 else 0.0
        std_ret = float(np.std(ret_arr)) if len(ret_arr) > 1 else 1.0
        downside_diffs = np.minimum(0.0, ret_arr)
        downside_dev = float(np.sqrt(np.mean(downside_diffs ** 2))) if len(downside_diffs) > 0 else 1e-6
        
        sharpe = (mean_ret / (std_ret + 1e-8) * np.sqrt(252)) if std_ret > 1e-8 else 0.0
        sortino = (mean_ret / (downside_dev + 1e-8) * np.sqrt(252)) if downside_dev > 1e-8 else 0.0
        
        # Expected Value per trade ($ and %)
        ev_dollar = float(np.mean(trade_pnls)) if total_trades > 0 else 0.0
        ev_pct = mean_ret * 100.0
        
        return {
            "name": name,
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "ev_per_trade": ev_dollar,
            "ev_percent": ev_pct,
            "net_pnl": sum(trade_pnls),
            "final_equity": equity_curve[-1]
        }

    def _compute_performance_metrics(
        self,
        name: str,
        trade_pnls: List[float],
        trade_returns: List[float],
        equity_curve: List[float],
        is_win: np.ndarray,
        is_loss: np.ndarray,
        is_tie: np.ndarray,
        reached_target: bool,
        reached_ruin: bool,
        trades_to_double: Any
    ) -> Dict[str, Any]:
        total_trades = len(trade_pnls)
        if total_trades == 0:
            return self._empty_result(name)
            
        wins = int(np.sum(is_win))
        losses = int(np.sum(is_loss))
        ties = int(np.sum(is_tie))
        decisive = wins + losses
        
        win_rate = (wins / total_trades) if total_trades > 0 else 0.0
        win_rate_eff = (wins / decisive) if decisive > 0 else 0.0
        
        gross_profit = sum(p for p in trade_pnls if p > 0)
        gross_loss = abs(sum(p for p in trade_pnls if p < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        
        net_pnl = sum(trade_pnls)
        final_equity = equity_curve[-1]
        
        # Max Drawdown
        eq_arr = np.array(equity_curve)
        peaks = np.maximum.accumulate(eq_arr)
        drawdowns = np.where(peaks > 0, (peaks - eq_arr) / peaks, 0.0)
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
        
        # Sharpe & Sortino (per trade)
        ret_arr = np.array(trade_returns)
        mean_ret = float(np.mean(ret_arr)) if len(ret_arr) > 0 else 0.0
        std_ret = float(np.std(ret_arr)) if len(ret_arr) > 0 else 1.0
        neg_returns = ret_arr[ret_arr < 0]
        downside_std = float(np.std(neg_returns)) if len(neg_returns) > 0 else 1e-6
        
        sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 1e-8 else 0.0
        sortino = (mean_ret / downside_std * np.sqrt(252)) if downside_std > 1e-8 else 0.0
        
        # Expected Value per trade ($ and %)
        ev_dollar = float(np.mean(trade_pnls)) if total_trades > 0 else 0.0
        ev_pct = mean_ret * 100.0
        
        return {
            "name": name,
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_rate": win_rate,
            "win_rate_effective": win_rate_eff,
            "profit_factor": profit_factor,
            "net_pnl": net_pnl,
            "final_equity": final_equity,
            "roi_pct": ((final_equity - self.initial_capital) / self.initial_capital) * 100.0,
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "ev_dollar": ev_dollar,
            "ev_pct": ev_pct,
            "reached_target": reached_target,
            "reached_ruin": reached_ruin,
            "trades_to_double": trades_to_double,
            "trade_returns": trade_returns,
            "equity_curve": equity_curve
        }

    def _empty_result(self, name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "win_rate": 0.0,
            "win_rate_effective": 0.0,
            "profit_factor": 0.0,
            "net_pnl": 0.0,
            "final_equity": self.initial_capital,
            "roi_pct": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "ev_dollar": 0.0,
            "ev_pct": 0.0,
            "reached_target": False,
            "reached_ruin": False,
            "trades_to_double": None,
            "trade_returns": [],
            "equity_curve": [self.initial_capital]
        }
