import pandas as pd
import numpy as np
from .base import BaseStrategy

class VolatilitySqueezeStrategy(BaseStrategy):
    name = "Volatility Squeeze"
    description = "Deteccion de compresion de volatilidad (Bollinger dentro de Keltner)."

    def get_params_schema(self) -> list[dict]:
        return [
            {"name": "bb_period", "type": "int", "default": 20, "min": 2, "max": 200, "step": 1, "description": "Periodo Bollinger"},
            {"name": "bb_mult", "type": "float", "default": 1.5, "min": 0.5, "max": 5.0, "step": 0.1, "description": "Multiplicador Bollinger"},
            {"name": "kc_period", "type": "int", "default": 20, "min": 2, "max": 200, "step": 1, "description": "Periodo Keltner"},
            {"name": "kc_mult", "type": "float", "default": 2.0, "min": 0.5, "max": 5.0, "step": 0.1, "description": "Multiplicador Keltner"}
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
        bb_sma = close.rolling(window=eff_period, min_periods=1).mean()
        bb_std = close.rolling(window=eff_period, min_periods=1).std(ddof=0).fillna(0.0)
        
        from engine.indicators import compute_ema
        kc_ema = compute_ema(close, 20)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_20 = tr.rolling(window=eff_period, min_periods=1).mean()
        
        return {
            'close': close,
            'high': high,
            'low': low,
            'open': open_p,
            'volume': volume,
            'bb_sma_20': bb_sma,
            'bb_std_20': bb_std,
            'kc_ema_20': kc_ema,
            'atr_20': atr_20,
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
            bb_mult = float(p.get("bb_mult", 1.5))
        except (ValueError, TypeError):
            bb_mult = 1.5
        try:
            kc_period = max(1, int(float(p.get("kc_period", 20))))
        except (ValueError, TypeError):
            kc_period = 20
        try:
            kc_mult = float(p.get("kc_mult", 2.0))
        except (ValueError, TypeError):
            kc_mult = 2.0
        
        if df is not None:
            close = df['close']
            high = df['high'] if 'high' in df.columns else close
            low = df['low'] if 'low' in df.columns else close
            orig_indices = df.index
        elif isinstance(precomputed, dict) and len(precomputed) > 0 and ('orig_indices' in precomputed or 'close' in precomputed or 'bb_sma_20' in precomputed):
            orig_indices = precomputed.get('orig_indices', precomputed.get('bb_sma_20', pd.Series(dtype=float)).index)
            close = precomputed.get('close', precomputed.get('bb_sma_20', pd.Series(dtype=float)))
            high = precomputed.get('high', close)
            low = precomputed.get('low', close)
        else:
            return pd.Series(dtype=object)

        if len(close) == 0:
            return pd.Series(dtype=object, index=orig_indices)

        eff_bb = min(len(close), bb_period)
        if bb_period == 20 and isinstance(precomputed, dict) and 'bb_sma_20' in precomputed:
            bb_sma = precomputed['bb_sma_20']
            bb_std = precomputed['bb_std_20']
        else:
            bb_sma = close.rolling(window=eff_bb, min_periods=1).mean()
            bb_std = close.rolling(window=eff_bb, min_periods=1).std(ddof=0).fillna(0.0)
            
        bb_upper = bb_sma + (bb_mult * bb_std)
        bb_lower = bb_sma - (bb_mult * bb_std)
        
        from engine.indicators import compute_ema
        eff_kc = min(len(close), kc_period)
        if kc_period == 20 and isinstance(precomputed, dict) and 'kc_ema_20' in precomputed:
            kc_ema = precomputed['kc_ema_20']
            atr = precomputed['atr_20']
        else:
            kc_ema = compute_ema(close, eff_kc)
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=eff_kc, min_periods=1).mean()
            
        kc_upper = kc_ema + (kc_mult * atr)
        kc_lower = kc_ema - (kc_mult * atr)
        
        momentum = close - bb_sma
        
        valid_mask = bb_lower.notna() & bb_upper.notna() & kc_lower.notna() & kc_upper.notna() & momentum.notna()
        
        squeeze_on = (bb_lower > kc_lower) & (bb_upper < kc_upper) & valid_mask
        squeeze_off = (~squeeze_on) & valid_mask
        prev_squeeze_on = squeeze_on.shift(1).fillna(False)
        
        signals = pd.Series(index=orig_indices, data=None, dtype=object)
        
        call_cond = prev_squeeze_on & squeeze_off & (momentum > 0) & valid_mask
        put_cond = prev_squeeze_on & squeeze_off & (momentum < 0) & valid_mask
        
        conflict = call_cond & put_cond
        call_cond = call_cond & (~conflict)
        put_cond = put_cond & (~conflict)
        
        signals.loc[call_cond] = 'CALL'
        signals.loc[put_cond] = 'PUT'
        
        return signals
