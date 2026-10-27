import pandas as pd
import numpy as np
from .base import BaseStrategy

class EmaCrossStrategy(BaseStrategy):
    name = "EMA Cross"
    description = "Cruce de medias moviles exponenciales."

    def get_params_schema(self) -> list[dict]:
        return [
            {"name": "fast_period", "type": "int", "default": 9, "min": 2, "max": 100, "step": 1, "description": "Periodo EMA rapida"},
            {"name": "slow_period", "type": "int", "default": 21, "min": 5, "max": 200, "step": 1, "description": "Periodo EMA lenta"}
        ]

    def prepare_data(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty or 'close' not in df.columns:
            return {}
        from engine.indicators import compute_ema
        close = df['close']
        fast_ema = compute_ema(close, 9)
        slow_ema = compute_ema(close, 21)
        return {
            'fast_ema_9': fast_ema,
            'slow_ema_21': slow_ema,
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
            fast_period = max(1, int(float(p.get("fast_period", 9))))
        except (ValueError, TypeError):
            fast_period = 9
        try:
            slow_period = max(1, int(float(p.get("slow_period", 21))))
        except (ValueError, TypeError):
            slow_period = 21
        
        from engine.indicators import compute_ema
        if df is not None:
            close = df['close']
            orig_indices = df.index
            fast_ema = precomputed['fast_ema_9'] if (fast_period == 9 and isinstance(precomputed, dict) and 'fast_ema_9' in precomputed) else compute_ema(close, fast_period)
            slow_ema = precomputed['slow_ema_21'] if (slow_period == 21 and isinstance(precomputed, dict) and 'slow_ema_21' in precomputed) else compute_ema(close, slow_period)
        elif isinstance(precomputed, dict) and len(precomputed) > 0 and 'fast_ema_9' in precomputed and 'slow_ema_21' in precomputed:
            fast_ema = precomputed['fast_ema_9']
            slow_ema = precomputed['slow_ema_21']
            orig_indices = precomputed.get('orig_indices', fast_ema.index)
        else:
            return pd.Series(dtype=object)

        if len(fast_ema) == 0:
            return pd.Series(dtype=object, index=orig_indices)
        
        prev_fast = fast_ema.shift(1)
        prev_slow = slow_ema.shift(1)
        
        signals = pd.Series(index=orig_indices, data=None, dtype=object)
        
        call_cond = (prev_fast <= prev_slow) & (fast_ema > slow_ema)
        put_cond = (prev_fast >= prev_slow) & (fast_ema < slow_ema)
        
        conflict = call_cond & put_cond
        call_cond = call_cond & (~conflict)
        put_cond = put_cond & (~conflict)
        
        signals.loc[call_cond] = 'CALL'
        signals.loc[put_cond] = 'PUT'
        
        return signals
