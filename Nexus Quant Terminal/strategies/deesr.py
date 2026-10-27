import pandas as pd
import numpy as np
from .base import BaseStrategy

class DeesrStrategy(BaseStrategy):
    name = "Dual Extreme Envelope Stretch Reversal"
    description = "Doble ruptura Bollinger/Keltner, RSI extremo dual y compresion de cuerpo."

    def get_params_schema(self) -> list[dict]:
        return [
            {"name": "bb_period", "type": "int", "default": 20, "min": 10, "max": 50, "description": "Bollinger Period"},
            {"name": "bb_std", "type": "float", "default": 2.0, "min": 1.5, "max": 3.5, "description": "Bollinger Std Dev"},
            {"name": "kc_period", "type": "int", "default": 20, "min": 10, "max": 50, "description": "Keltner Period"},
            {"name": "kc_mult", "type": "float", "default": 1.5, "min": 1.0, "max": 3.0, "description": "Keltner Multiplier"},
            {"name": "rsi_fast_period", "type": "int", "default": 3, "min": 2, "max": 7, "description": "Fast RSI Period"},
            {"name": "rsi_slow_period", "type": "int", "default": 14, "min": 7, "max": 21, "description": "Slow RSI Period"},
            {"name": "max_body_ratio", "type": "float", "default": 0.55, "min": 0.20, "max": 0.75, "description": "Max Body Ratio"},
            {"name": "min_wick_ratio", "type": "float", "default": 0.30, "min": 0.15, "max": 0.75, "description": "Min Wick Ratio"}
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
        
        # Bollinger Bands
        bb_sma = close.rolling(window=min(len(close), 20), min_periods=1).mean()
        bb_sigma = close.rolling(window=min(len(close), 20), min_periods=1).std(ddof=0).fillna(0.0)
        
        # Keltner Channels
        kc_ema = compute_ema(close, min(len(close), 20)).ffill().fillna(close)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_20 = tr.rolling(window=min(len(close), 20), min_periods=1).mean().ffill().fillna(0.0)
        
        # RSIs
        rsi_fast = compute_wilders_rsi(close, min(len(close) - 1, 3)).fillna(50.0)
        rsi_slow = compute_wilders_rsi(close, min(len(close) - 1, 14)).fillna(50.0)
        
        # Geometry
        candle_range = high - low
        body = (close - open_p).abs()
        lower_wick = np.minimum(open_p, close) - low
        upper_wick = high - np.maximum(open_p, close)
        
        valid_range = candle_range > 0
        body_ratio = pd.Series(np.where(valid_range, body / candle_range.replace(0, 1e-8), 1.0), index=df.index)
        lower_wick_ratio = pd.Series(np.where(valid_range, lower_wick / candle_range.replace(0, 1e-8), 0.0), index=df.index)
        upper_wick_ratio = pd.Series(np.where(valid_range, upper_wick / candle_range.replace(0, 1e-8), 0.0), index=df.index)
        
        return {
            'close': close,
            'high': high,
            'low': low,
            'open': open_p,
            'volume': volume,
            'bb_sma': bb_sma,
            'bb_sigma': bb_sigma,
            'kc_ema': kc_ema,
            'atr_20': atr_20,
            'rsi_fast': rsi_fast,
            'rsi_slow': rsi_slow,
            'body_ratio': body_ratio,
            'lower_wick_ratio': lower_wick_ratio,
            'upper_wick_ratio': upper_wick_ratio,
            'has_vol': has_vol,
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
            kc_period = max(1, int(float(p.get("kc_period", 20))))
        except (ValueError, TypeError):
            kc_period = 20
        try:
            kc_mult = float(p.get("kc_mult", 1.5))
        except (ValueError, TypeError):
            kc_mult = 1.5
        try:
            rsi_fast_p = max(1, int(float(p.get("rsi_fast_period", 3))))
        except (ValueError, TypeError):
            rsi_fast_p = 3
        try:
            rsi_slow_p = max(1, int(float(p.get("rsi_slow_period", 14))))
        except (ValueError, TypeError):
            rsi_slow_p = 14
        try:
            max_body_ratio = float(p.get("max_body_ratio", 0.55))
        except (ValueError, TypeError):
            max_body_ratio = 0.55
        try:
            min_wick_ratio = float(p.get("min_wick_ratio", 0.30))
        except (ValueError, TypeError):
            min_wick_ratio = 0.30
        
        from engine.indicators import compute_ema, compute_wilders_rsi
        eff_bb = min(len(close), bb_period)
        if bb_period == 20 and bb_std == 2.0 and 'bb_sma' in precomputed:
            bb_sma = precomputed['bb_sma']
            bb_sigma = precomputed['bb_sigma']
            bb_lower = bb_sma - (bb_std * bb_sigma)
            bb_upper = bb_sma + (bb_std * bb_sigma)
        else:
            bb_sma = close.rolling(window=eff_bb, min_periods=1).mean()
            bb_sigma = close.rolling(window=eff_bb, min_periods=1).std(ddof=0).fillna(0.0)
            bb_lower = bb_sma - (bb_std * bb_sigma)
            bb_upper = bb_sma + (bb_std * bb_sigma)
            
        eff_kc = min(len(close), kc_period)
        if kc_period == 20 and kc_mult == 1.5 and 'kc_ema' in precomputed:
            kc_ema = precomputed['kc_ema']
            atr_20 = precomputed['atr_20']
            kc_lower = kc_ema - (kc_mult * atr_20)
            kc_upper = kc_ema + (kc_mult * atr_20)
        else:
            kc_ema = compute_ema(close, eff_kc).ffill().fillna(close)
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr_20 = tr.rolling(window=eff_kc, min_periods=1).mean().ffill().fillna(0.0)
            kc_lower = kc_ema - (kc_mult * atr_20)
            kc_upper = kc_ema + (kc_mult * atr_20)
            
        rsi_fast = precomputed['rsi_fast'] if (rsi_fast_p == 3 and 'rsi_fast' in precomputed) else compute_wilders_rsi(close, min(len(close) - 1, rsi_fast_p)).fillna(50.0)
        rsi_slow = precomputed['rsi_slow'] if (rsi_slow_p == 14 and 'rsi_slow' in precomputed) else compute_wilders_rsi(close, min(len(close) - 1, rsi_slow_p)).fillna(50.0)
        
        candle_range = high - low
        body = (close - open_p).abs()
        lower_wick = np.minimum(open_p, close) - low
        upper_wick = high - np.maximum(open_p, close)
        
        valid_range = candle_range > 0
        body_ratio = np.where(valid_range, body / candle_range.replace(0, 1e-8), 1.0)
        lower_wick_ratio = np.where(valid_range, lower_wick / candle_range.replace(0, 1e-8), 0.0)
        upper_wick_ratio = np.where(valid_range, upper_wick / candle_range.replace(0, 1e-8), 0.0)
        
        call_cond = (low <= np.minimum(bb_lower, kc_lower)) & (rsi_fast <= 15.0) & (rsi_slow <= 30.0) & (body_ratio <= max_body_ratio) & (lower_wick_ratio >= min_wick_ratio)
        put_cond = (high >= np.maximum(bb_upper, kc_upper)) & (rsi_fast >= 85.0) & (rsi_slow >= 70.0) & (body_ratio <= max_body_ratio) & (upper_wick_ratio >= min_wick_ratio)
        
        conflict = call_cond & put_cond
        call_cond = call_cond & (~conflict)
        put_cond = put_cond & (~conflict)
        
        signals = pd.Series(index=orig_indices, data=None, dtype=object)
        signals.loc[call_cond] = 'CALL'
        signals.loc[put_cond] = 'PUT'
        
        return signals
