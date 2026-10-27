import pandas as pd
import numpy as np
from .base import BaseStrategy

class BollingerBounceStrategy(BaseStrategy):
    name = "Bollinger Bounce"
    description = "Estrategia de rebote en bandas de Bollinger."

    def get_params_schema(self) -> list[dict]:
        return [
            {"name": "bb_period", "type": "int", "default": 20, "min": 2, "max": 200, "step": 1, "description": "Periodo de Bollinger"},
            {"name": "bb_std", "type": "float", "default": 2.2, "min": 0.5, "max": 5.0, "step": 0.1, "description": "Desviacion Estandar"},
            {"name": "wick_ratio", "type": "float", "default": 0.35, "min": 0.0, "max": 0.8, "step": 0.05, "description": "Min Wick Rejection Ratio"},
            {"name": "vol_mult", "type": "float", "default": 1.3, "min": 0.0, "max": 3.0, "step": 0.1, "description": "Min Volume Multiplier"}
        ]

    def prepare_data(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty or 'close' not in df.columns:
            return {}
        close = df['close']
        high = df['high'] if 'high' in df.columns else close
        low = df['low'] if 'low' in df.columns else close
        open_p = df['open'] if 'open' in df.columns else close
        volume = df['volume'] if 'volume' in df.columns else pd.Series(1.0, index=df.index)

        eff_period = min(max(1, len(close)), 20)
        sma = close.rolling(window=eff_period, min_periods=1).mean()
        std = close.rolling(window=eff_period, min_periods=1).std(ddof=0).fillna(0.0)
        vol_sma = volume.rolling(window=eff_period, min_periods=1).mean()

        candle_range = (high - low).replace(0, 1e-8)
        lower_wick_ratio = (np.minimum(open_p, close) - low) / candle_range
        upper_wick_ratio = (high - np.maximum(open_p, close)) / candle_range

        return {
            'close': close,
            'high': high,
            'low': low,
            'open': open_p,
            'volume': volume,
            'sma_20': sma,
            'std_20': std,
            'vol_sma_20': vol_sma,
            'lower_wick_ratio': lower_wick_ratio,
            'upper_wick_ratio': upper_wick_ratio,
            'orig_indices': df.index
        }

    def generate_signals(self, df: pd.DataFrame = None, params: dict = None, precomputed: dict = None, **kwargs) -> pd.Series:
        if precomputed is None and isinstance(df, dict):
            precomputed = df
            df = None

        if df is not None and (df.empty or len(df) == 0 or 'close' not in df.columns):
            return pd.Series(dtype=object, index=df.index)

        p = params or {}
        try:
            bb_period = max(1, int(float(p.get("bb_period", 20))))
        except (ValueError, TypeError):
            bb_period = 20
        try:
            bb_std = float(p.get("bb_std", 2.2))
        except (ValueError, TypeError):
            bb_std = 2.2
        try:
            wick_ratio = float(p.get("wick_ratio", 0.35))
        except (ValueError, TypeError):
            wick_ratio = 0.35
        try:
            vol_mult = float(p.get("vol_mult", 1.3))
        except (ValueError, TypeError):
            vol_mult = 1.3
        
        if df is not None:
            close = df['close']
            high = df['high'] if 'high' in df.columns else close
            low = df['low'] if 'low' in df.columns else close
            open_p = df['open'] if 'open' in df.columns else close
            volume = df['volume'] if 'volume' in df.columns else pd.Series(1.0, index=df.index)

            eff_period = min(len(close), bb_period)
            sma = close.rolling(window=eff_period, min_periods=1).mean() if (bb_period != 20 or not isinstance(precomputed, dict) or 'sma_20' not in precomputed) else precomputed['sma_20']
            std = close.rolling(window=eff_period, min_periods=1).std(ddof=0).fillna(0.0) if (bb_period != 20 or not isinstance(precomputed, dict) or 'std_20' not in precomputed) else precomputed['std_20']
            
            eff_vol = min(max(1, len(volume)), 20)
            vol_sma = precomputed['vol_sma_20'] if (isinstance(precomputed, dict) and 'vol_sma_20' in precomputed) else volume.rolling(window=eff_vol, min_periods=1).mean()
            
            candle_range = (high - low).replace(0, 1e-8)
            lower_wick_ratio = (np.minimum(open_p, close) - low) / candle_range
            upper_wick_ratio = (high - np.maximum(open_p, close)) / candle_range
            orig_indices = df.index
        elif isinstance(precomputed, dict) and len(precomputed) > 0 and ('sma_20' in precomputed or 'close' in precomputed):
            close = precomputed.get('close', precomputed.get('sma_20'))
            high = precomputed.get('high', close)
            low = precomputed.get('low', close)
            open_p = precomputed.get('open', close)
            volume = precomputed.get('volume', precomputed.get('vol_sma_20', pd.Series(1.0, index=close.index)))
            orig_indices = precomputed.get('orig_indices', close.index)

            eff_period = min(len(close), bb_period)
            if bb_period == 20 and 'sma_20' in precomputed and 'std_20' in precomputed:
                sma = precomputed['sma_20']
                std = precomputed['std_20']
            else:
                sma = close.rolling(window=eff_period, min_periods=1).mean()
                std = close.rolling(window=eff_period, min_periods=1).std(ddof=0).fillna(0.0)

            eff_vol = min(max(1, len(volume)), 20)
            vol_sma = precomputed.get('vol_sma_20', volume.rolling(window=eff_vol, min_periods=1).mean())
            if 'lower_wick_ratio' in precomputed and 'upper_wick_ratio' in precomputed:
                lower_wick_ratio = precomputed['lower_wick_ratio']
                upper_wick_ratio = precomputed['upper_wick_ratio']
            else:
                candle_range = (high - low).replace(0, 1e-8)
                lower_wick_ratio = (np.minimum(open_p, close) - low) / candle_range
                upper_wick_ratio = (high - np.maximum(open_p, close)) / candle_range
        else:
            return pd.Series(dtype=object)

        if len(close) == 0:
            return pd.Series(dtype=object, index=orig_indices)
        
        upper_band = sma + (std * bb_std)
        lower_band = sma - (std * bb_std)
        
        prev_close = close.shift(1)
        prev_lower = lower_band.shift(1)
        prev_upper = upper_band.shift(1)
        
        signals = pd.Series(index=orig_indices, data=None, dtype=object)
        
        vol_filter = (vol_mult <= 0.0) | (volume >= (vol_sma * vol_mult))
        wick_call_filter = (wick_ratio <= 0.0) | (lower_wick_ratio >= wick_ratio)
        wick_put_filter = (wick_ratio <= 0.0) | (upper_wick_ratio >= wick_ratio)

        call_cond = (prev_close <= prev_lower) & (close > lower_band) & wick_call_filter & vol_filter
        put_cond = (prev_close >= prev_upper) & (close < upper_band) & wick_put_filter & vol_filter
        
        conflict = call_cond & put_cond
        call_cond = call_cond & (~conflict)
        put_cond = put_cond & (~conflict)
        
        signals.loc[call_cond] = 'CALL'
        signals.loc[put_cond] = 'PUT'
        
        return signals
