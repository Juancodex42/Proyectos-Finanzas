import pandas as pd
import numpy as np
from .base import BaseStrategy

class IslgRsStrategy(BaseStrategy):
    name = "Institutional Swing Liquidity Grab Sweep"
    description = "Barrido de liquidez institucional en swing highs/lows con rechazo mecha y volumen."

    def get_params_schema(self) -> list[dict]:
        return [
            {"name": "lookback_period", "type": "int", "default": 25, "min": 10, "max": 60, "description": "Swing Lookback Period"},
            {"name": "min_sweep_atr_ratio", "type": "float", "default": 0.10, "min": 0.05, "max": 0.50, "step": 0.05, "description": "Min Sweep Depth in ATR"},
            {"name": "wick_ratio", "type": "float", "default": 0.35, "min": 0.20, "max": 0.70, "description": "Min Wick Ratio"},
            {"name": "vol_mult", "type": "float", "default": 1.3, "min": 0.8, "max": 3.0, "description": "Volume Spike Multiplier"},
            {"name": "rsi_period", "type": "int", "default": 7, "min": 3, "max": 14, "description": "RSI Period"},
            {"name": "rsi_upper", "type": "float", "default": 60.0, "min": 50.0, "max": 85.0, "description": "RSI Upper Overbought Threshold"},
            {"name": "rsi_lower", "type": "float", "default": 40.0, "min": 15.0, "max": 50.0, "description": "RSI Lower Oversold Threshold"},
            {"name": "use_session_filter", "type": "bool", "default": False, "description": "Filter Active Trading Hours (7-20 UTC)"}
        ]

    def prepare_data(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty or 'close' not in df.columns:
            return {}
        close = df['close']
        high = df['high'] if 'high' in df.columns else close
        low = df['low'] if 'low' in df.columns else close
        open_p = df['open'] if 'open' in df.columns else close
        has_vol = ('volume' in df.columns) and (df['volume'].fillna(0).sum() > 0)
        volume = df['volume'] if 'volume' in df.columns else pd.Series(0, index=df.index)
        
        # ATR 14
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=min(len(df), 14), min_periods=1).mean().ffill().fillna(0.0)
        
        from engine.indicators import compute_wilders_rsi
        rsi_7 = compute_wilders_rsi(close, min(len(close) - 1, 7)).fillna(50.0)
        rsi_14 = compute_wilders_rsi(close, min(len(close) - 1, 14)).fillna(50.0)
        vol_sma = volume.rolling(window=min(len(volume), 20), min_periods=1).mean() if has_vol else pd.Series(0, index=df.index)
        
        # Datetime for session filter: detect ms vs s
        hours = None
        if 'open_time' in df.columns:
            try:
                is_ms = bool(df['open_time'].max() > 1e11)
                unit = 'ms' if is_ms else 's'
                dt_series = pd.to_datetime(df['open_time'], unit=unit, errors='coerce')
                hours = dt_series.dt.hour
            except Exception:
                pass
        elif 'datetime' in df.columns:
            try:
                dt_series = pd.to_datetime(df['datetime'], errors='coerce')
                hours = dt_series.dt.hour
            except Exception:
                pass
        elif isinstance(df.index, pd.DatetimeIndex):
            hours = df.index.hour

        return {
            'close': close,
            'high': high,
            'low': low,
            'open': open_p,
            'volume': volume,
            'atr_14': atr,
            'rsi_7': rsi_7,
            'rsi_14': rsi_14,
            'vol_sma': vol_sma,
            'has_vol': has_vol,
            'hours': hours,
            'orig_indices': df.index
        }

    def generate_signals(self, df: pd.DataFrame = None, params: dict = None, precomputed: dict = None, **kwargs) -> pd.Series:
        if precomputed is None and isinstance(df, dict):
            precomputed = df
            df = None

        if df is not None and (df.empty or len(df) == 0 or 'close' not in df.columns):
            return pd.Series(dtype=object, index=df.index)

        if not isinstance(precomputed, dict) or 'close' not in precomputed:
            if df is None:
                return pd.Series(dtype=object)
            precomputed = self.prepare_data(df)

        orig_indices = df.index if df is not None else precomputed.get('orig_indices', pd.Index([]))
        close = df['close'] if df is not None and 'close' in df else precomputed.get('close', pd.Series(dtype=float))
        high = df['high'] if df is not None and 'high' in df else precomputed.get('high', close)
        low = df['low'] if df is not None and 'low' in df else precomputed.get('low', close)
        open_p = df['open'] if df is not None and 'open' in df else precomputed.get('open', close)
        volume = df['volume'] if (df is not None and 'volume' in df.columns) else precomputed.get('volume', pd.Series(0, index=orig_indices))

        if len(close) == 0:
            return pd.Series(dtype=object, index=orig_indices)

        p = params or {}
        try:
            lookback = max(1, int(float(p.get("lookback_period", 25))))
        except (ValueError, TypeError):
            lookback = 25
        try:
            sweep_ratio = float(p.get("min_sweep_atr_ratio", 0.10))
        except (ValueError, TypeError):
            sweep_ratio = 0.10
        try:
            wick_ratio = float(p.get("wick_ratio", 0.35))
        except (ValueError, TypeError):
            wick_ratio = 0.35
        try:
            vol_mult = float(p.get("vol_mult", 1.3))
        except (ValueError, TypeError):
            vol_mult = 1.3
        try:
            rsi_period = max(1, int(float(p.get("rsi_period", 7))))
        except (ValueError, TypeError):
            rsi_period = 7
        try:
            rsi_upper = float(p.get("rsi_upper", 60.0))
        except (ValueError, TypeError):
            rsi_upper = 60.0
        try:
            rsi_lower = float(p.get("rsi_lower", 40.0))
        except (ValueError, TypeError):
            rsi_lower = 40.0
        use_session_filter = bool(p.get("use_session_filter", False))
        
        atr = precomputed.get('atr_14')
        if atr is None:
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=min(len(close), 14), min_periods=1).mean().ffill().fillna(0.0)
            
        eff_lookback = min(len(high), lookback)
        swing_high = high.rolling(window=eff_lookback, min_periods=1).max().shift(1)
        swing_low = low.rolling(window=eff_lookback, min_periods=1).min().shift(1)
        
        candle_range = high - low
        body = (close - open_p).abs()
        lower_wick = np.minimum(open_p, close) - low
        upper_wick = high - np.maximum(open_p, close)
        
        valid_range = candle_range > 0
        lower_wick_ratio = np.where(valid_range, lower_wick / candle_range.replace(0, 1e-8), 0.0)
        upper_wick_ratio = np.where(valid_range, upper_wick / candle_range.replace(0, 1e-8), 0.0)
        
        from engine.indicators import compute_wilders_rsi
        if rsi_period == 7 and 'rsi_7' in precomputed:
            rsi = precomputed['rsi_7']
        elif rsi_period == 14 and 'rsi_14' in precomputed:
            rsi = precomputed['rsi_14']
        else:
            rsi = compute_wilders_rsi(close, min(len(close) - 1, rsi_period)).fillna(50.0)
            
        has_vol = precomputed.get('has_vol', False)
        if has_vol:
            eff_vol = min(len(volume), 20)
            vol_sma = precomputed.get('vol_sma', volume.rolling(window=eff_vol, min_periods=1).mean())
            vol_spike = (vol_sma == 0) | (volume >= (vol_sma * vol_mult))
        else:
            vol_spike = pd.Series(True, index=orig_indices)
            
        if use_session_filter:
            hours = precomputed.get('hours')
            if hours is not None:
                session_ok = (hours >= 7) & (hours <= 20)
            else:
                session_ok = pd.Series(True, index=orig_indices)
        else:
            session_ok = pd.Series(True, index=orig_indices)
            
        call_cond = (
            (low <= (swing_low - sweep_ratio * atr)) &
            (close > swing_low) &
            (close > open_p) &
            (lower_wick_ratio >= wick_ratio) &
            (rsi <= rsi_lower) &
            vol_spike &
            session_ok
        )
        
        put_cond = (
            (high >= (swing_high + sweep_ratio * atr)) &
            (close < swing_high) &
            (close < open_p) &
            (upper_wick_ratio >= wick_ratio) &
            (rsi >= rsi_upper) &
            vol_spike &
            session_ok
        )
        
        conflict = call_cond & put_cond
        call_cond = call_cond & (~conflict)
        put_cond = put_cond & (~conflict)
        
        signals = pd.Series(index=orig_indices, data=None, dtype=object)
        signals.loc[call_cond] = 'CALL'
        signals.loc[put_cond] = 'PUT'
        
        return signals
