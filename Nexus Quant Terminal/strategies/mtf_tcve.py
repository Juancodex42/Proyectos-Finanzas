import pandas as pd
import numpy as np
from .base import BaseStrategy

class MtfTcveStrategy(BaseStrategy):
    name = "MTF Trend Volume Exhaustion"
    description = "Confluencia MTF, rechazo de mecha y agotamiento de volumen."

    def get_params_schema(self) -> list[dict]:
        return [
            {"name": "bb_period", "type": "int", "default": 20, "min": 10, "max": 50, "description": "Bollinger Period"},
            {"name": "bb_std", "type": "float", "default": 2.0, "min": 1.5, "max": 3.5, "description": "Bollinger Std Dev"},
            {"name": "wick_ratio", "type": "float", "default": 0.35, "min": 0.20, "max": 0.75, "description": "Min Wick Rejection Ratio"},
            {"name": "vol_mult", "type": "float", "default": 1.3, "min": 1.0, "max": 3.0, "description": "Volume Spike Multiplier"},
            {"name": "rsi_period", "type": "int", "default": 7, "min": 3, "max": 14, "description": "RSI Period"},
            {"name": "rsi_oversold", "type": "float", "default": 25.0, "min": 10.0, "max": 35.0, "description": "RSI Oversold"},
            {"name": "rsi_overbought", "type": "float", "default": 75.0, "min": 65.0, "max": 90.0, "description": "RSI Overbought"}
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
        
        from engine.indicators import compute_ema, compute_wilders_rsi
        ema_20 = compute_ema(close, min(len(close), 20)).ffill().fillna(close)
        ema_50 = compute_ema(close, min(len(close), 50)).ffill().fillna(close)
        rsi = compute_wilders_rsi(close, min(len(close) - 1, 7)).fillna(50.0)
        vol_sma = volume.rolling(window=min(len(volume), 20), min_periods=1).mean() if has_vol else pd.Series(0, index=df.index)
        
        return {
            'close': close,
            'high': high,
            'low': low,
            'open': open_p,
            'volume': volume,
            'ema_20': ema_20,
            'ema_50': ema_50,
            'rsi_7': rsi,
            'vol_sma': vol_sma,
            'has_vol': has_vol,
            'orig_indices': df.index
        }

    def generate_signals(self, df: pd.DataFrame = None, params: dict = None, precomputed: dict = None, **kwargs) -> pd.Series:
        if precomputed is None and isinstance(df, dict):
            precomputed = df
            df = None

        if df is not None and (df.empty or len(df) == 0 or 'close' not in df.columns):
            return pd.Series(dtype=object, index=df.index)

        if not isinstance(precomputed, dict) or 'ema_20' not in precomputed:
            if df is None:
                return pd.Series(dtype=object)
            precomputed = self.prepare_data(df)

        orig_indices = df.index if df is not None else precomputed.get('orig_indices', pd.Index([]))
        close = df['close'] if df is not None and 'close' in df else precomputed.get('close', pd.Series(dtype=float))
        high = df['high'] if df is not None and 'high' in df else precomputed.get('high', close)
        low = df['low'] if df is not None and 'low' in df else precomputed.get('low', close)
        open_p = df['open'] if df is not None and 'open' in df else precomputed.get('open', close)
        volume = df['volume'] if df is not None and 'volume' in df.columns else precomputed.get('volume', pd.Series(0, index=orig_indices))

        if len(close) == 0:
            return pd.Series(dtype=object, index=orig_indices)

        p = params or {}
        try:
            bb_period = max(1, int(float(p.get("bb_period", 20))))
        except (ValueError, TypeError):
            bb_period = 20
        try:
            bb_std = float(p.get("bb_std", 2.0))
        except (ValueError, TypeError):
            bb_std = 2.0
        try:
            wick_ratio = float(p.get("wick_ratio", p.get("min_wick_ratio", 0.35)))
        except (ValueError, TypeError):
            wick_ratio = 0.35
        try:
            vol_mult = float(p.get("vol_mult", p.get("volume_mult", 1.3)))
        except (ValueError, TypeError):
            vol_mult = 1.3
        try:
            rsi_period = max(1, int(float(p.get("rsi_period", 7))))
        except (ValueError, TypeError):
            rsi_period = 7
        try:
            rsi_oversold = float(p.get("rsi_oversold", p.get("rsi_extreme", 25.0)))
        except (ValueError, TypeError):
            rsi_oversold = 25.0
        try:
            rsi_overbought = float(p.get("rsi_overbought", 100.0 - rsi_oversold if "rsi_extreme" in p else 75.0))
        except (ValueError, TypeError):
            rsi_overbought = 75.0
        
        from engine.indicators import compute_ema, compute_wilders_rsi
        ema_20 = precomputed.get('ema_20')
        ema_50 = precomputed.get('ema_50')
        if ema_20 is None:
            ema_20 = compute_ema(close, min(len(close), 20)).ffill().fillna(close)
        if ema_50 is None:
            ema_50 = compute_ema(close, min(len(close), 50)).ffill().fillna(close)
        
        ema_trend_call = (ema_20 >= ema_50) | (close >= ema_50)
        ema_trend_put = (ema_20 <= ema_50) | (close <= ema_50)
        
        eff_bb = min(len(close), bb_period)
        bb_sma = close.rolling(window=eff_bb, min_periods=1).mean()
        bb_sigma = close.rolling(window=eff_bb, min_periods=1).std(ddof=0).fillna(0.0)
        bb_lower = bb_sma - (bb_std * bb_sigma)
        bb_upper = bb_sma + (bb_std * bb_sigma)
        
        rsi = precomputed['rsi_7'] if (rsi_period == 7 and 'rsi_7' in precomputed) else compute_wilders_rsi(close, min(len(close) - 1, rsi_period)).fillna(50.0)
        
        has_vol = precomputed.get('has_vol', False)
        if has_vol:
            eff_vol = min(len(volume), 20)
            vol_sma = precomputed.get('vol_sma', volume.rolling(window=eff_vol, min_periods=1).mean())
            vol_climax = (vol_sma == 0) | (volume >= (vol_sma * vol_mult))
        else:
            vol_climax = pd.Series(True, index=orig_indices)
        
        candle_range = high - low
        lower_wick = np.minimum(open_p, close) - low
        upper_wick = high - np.maximum(open_p, close)
        
        valid_range = candle_range > 0
        lower_wick_ratio = np.where(valid_range, lower_wick / candle_range.replace(0, 1e-8), 0.0)
        upper_wick_ratio = np.where(valid_range, upper_wick / candle_range.replace(0, 1e-8), 0.0)
        
        call_cond = ema_trend_call & (low <= bb_lower) & (rsi <= rsi_oversold) & (lower_wick_ratio >= wick_ratio) & vol_climax
        put_cond = ema_trend_put & (high >= bb_upper) & (rsi >= rsi_overbought) & (upper_wick_ratio >= wick_ratio) & vol_climax
        
        conflict = call_cond & put_cond
        call_cond = call_cond & (~conflict)
        put_cond = put_cond & (~conflict)
        
        signals = pd.Series(index=orig_indices, data=None, dtype=object)
        signals.loc[call_cond] = 'CALL'
        signals.loc[put_cond] = 'PUT'
        
        return signals
