import pandas as pd
import numpy as np
from .base import BaseStrategy

class SupportResistanceStrategy(BaseStrategy):
    name = "Support/Resistance"
    description = "Estrategia de rebote en soportes y resistencias."

    def get_params_schema(self) -> list[dict]:
        return [
            {"name": "lookback", "type": "int", "default": 50, "min": 10, "max": 500, "step": 5, "description": "Periodo de busqueda de S/R"},
            {"name": "proximity", "type": "float", "default": 0.003, "min": 0.0001, "max": 0.05, "step": 0.0001, "description": "Proximidad (0.3% = 0.003)"}
        ]

    def prepare_data(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty or 'high' not in df.columns or 'low' not in df.columns:
            return {}
        close = df['close'] if 'close' in df.columns else df['high']
        high = df['high']
        low = df['low']
        open_p = df['open'] if 'open' in df.columns else close
        volume = df['volume'] if 'volume' in df.columns else pd.Series(1.0, index=df.index)
        
        eff_lookback = min(max(1, len(high)), 50)
        rolling_high = high.rolling(window=eff_lookback, min_periods=1).max().shift(1)
        rolling_low = low.rolling(window=eff_lookback, min_periods=1).min().shift(1)
        return {
            'close': close,
            'high': high,
            'low': low,
            'open': open_p,
            'volume': volume,
            'rolling_high_50': rolling_high,
            'rolling_low_50': rolling_low,
            'orig_indices': df.index
        }

    def generate_signals(self, df: pd.DataFrame = None, params: dict = None, precomputed: dict = None, **kwargs) -> pd.Series:
        if precomputed is None and isinstance(df, dict):
            precomputed = df
            df = None

        if df is not None and (df.empty or len(df) == 0 or 'high' not in df.columns or 'low' not in df.columns):
            return pd.Series(dtype=object, index=df.index)

        p = params or {}
        try:
            lookback = max(1, int(float(p.get("lookback", p.get("sr_lookback", 50)))))
        except (ValueError, TypeError):
            lookback = 50
        try:
            proximity = float(p.get("proximity", p.get("touch_threshold", 0.003)))
        except (ValueError, TypeError):
            proximity = 0.003
        try:
            wick_ratio = float(p.get("bounce_wick_ratio", 0.0))
        except (ValueError, TypeError):
            wick_ratio = 0.0
        
        if df is not None:
            high = df['high']
            low = df['low']
            close = df['close'] if 'close' in df.columns else df['high']
            open_p = df['open'] if 'open' in df.columns else close
            orig_indices = df.index
            eff_lookback = min(len(high), lookback)
            if lookback == 50 and isinstance(precomputed, dict) and 'rolling_high_50' in precomputed:
                rolling_high = precomputed['rolling_high_50']
                rolling_low = precomputed['rolling_low_50']
            else:
                rolling_high = high.rolling(window=eff_lookback, min_periods=1).max().shift(1)
                rolling_low = low.rolling(window=eff_lookback, min_periods=1).min().shift(1)
        elif isinstance(precomputed, dict) and len(precomputed) > 0 and ('rolling_high_50' in precomputed or 'close' in precomputed):
            close = precomputed.get('close', pd.Series(dtype=float))
            high = precomputed.get('high', close)
            low = precomputed.get('low', close)
            open_p = precomputed.get('open', close)
            orig_indices = precomputed.get('orig_indices', close.index)
            eff_lookback = min(len(high), lookback)
            if lookback == 50 and 'rolling_high_50' in precomputed and 'rolling_low_50' in precomputed:
                rolling_high = precomputed['rolling_high_50']
                rolling_low = precomputed['rolling_low_50']
            else:
                rolling_high = high.rolling(window=eff_lookback, min_periods=1).max().shift(1)
                rolling_low = low.rolling(window=eff_lookback, min_periods=1).min().shift(1)
        else:
            return pd.Series(dtype=object)

        if len(close) == 0:
            return pd.Series(dtype=object, index=orig_indices)
        
        signals = pd.Series(index=orig_indices, data=None, dtype=object)
        
        candle_range = (high - low).replace(0, 1e-8)
        lower_wick = (np.minimum(open_p, close) - low) / candle_range
        upper_wick = (high - np.maximum(open_p, close)) / candle_range
        
        call_cond = (low <= rolling_low * (1 + proximity)) & (close > rolling_low) & (close.diff() > 0)
        put_cond = (high >= rolling_high * (1 - proximity)) & (close < rolling_high) & (close.diff() < 0)
        
        if wick_ratio > 0:
            call_cond = call_cond & (lower_wick >= wick_ratio)
            put_cond = put_cond & (upper_wick >= wick_ratio)
        
        conflict = call_cond & put_cond
        call_cond = call_cond & (~conflict)
        put_cond = put_cond & (~conflict)
        
        signals.loc[call_cond] = 'CALL'
        signals.loc[put_cond] = 'PUT'
        
        return signals
