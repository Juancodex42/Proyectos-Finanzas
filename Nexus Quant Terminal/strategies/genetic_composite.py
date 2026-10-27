import pandas as pd
import numpy as np
from .base import BaseStrategy

class GeneticCompositeStrategy(BaseStrategy):
    name = "Estrategia Genetica Combinada"
    description = "Estrategia combinada multi-indicador optimizada por el motor genetico en Rust."

    def get_params_schema(self) -> list[dict]:
        return [
            {"name": "rsi_period", "type": "int", "default": 14, "min": 2, "max": 100, "step": 1, "description": "RSI Period"},
            {"name": "rsi_oversold", "type": "float", "default": 30.0, "min": 5.0, "max": 50.0, "step": 0.5, "description": "RSI Oversold"},
            {"name": "rsi_overbought", "type": "float", "default": 70.0, "min": 50.0, "max": 95.0, "step": 0.5, "description": "RSI Overbought"},
            {"name": "rsi_enabled", "type": "bool", "default": True, "description": "RSI Habilitado"},
            
            {"name": "bb_period", "type": "int", "default": 20, "min": 5, "max": 150, "step": 1, "description": "Bollinger Period"},
            {"name": "bb_std", "type": "float", "default": 2.0, "min": 0.5, "max": 5.0, "step": 0.1, "description": "Bollinger Std Dev"},
            {"name": "bb_enabled", "type": "bool", "default": True, "description": "Bollinger Habilitado"},
            
            {"name": "ema_fast_period", "type": "int", "default": 9, "min": 2, "max": 50, "step": 1, "description": "EMA Fast Period"},
            {"name": "ema_slow_period", "type": "int", "default": 21, "min": 5, "max": 200, "step": 1, "description": "EMA Slow Period"},
            {"name": "ema_enabled", "type": "bool", "default": False, "description": "EMA Cross Habilitado"},

            {"name": "htf_ema_period", "type": "int", "default": 100, "min": 20, "max": 250, "step": 1, "description": "HTF EMA Period"},
            {"name": "htf_ema_enabled", "type": "bool", "default": False, "description": "HTF Trend Filter Habilitado"}
        ]

    def prepare_data(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty or 'close' not in df.columns:
            return {}
        from engine.indicators import compute_ema, compute_wilders_rsi
        close = df['close']
        high = df['high'] if 'high' in df.columns else close
        low = df['low'] if 'low' in df.columns else close
        open_p = df['open'] if 'open' in df.columns else close
        has_vol = ('volume' in df.columns) and (df['volume'].fillna(0).sum() > 0)
        
        eff_bb = min(max(1, len(close)), 20)
        rsi_14 = compute_wilders_rsi(close, 14)
        bb_sma = close.rolling(window=eff_bb, min_periods=1).mean()
        bb_std = close.rolling(window=eff_bb, min_periods=1).std(ddof=0).fillna(0.0)
        ema_9 = compute_ema(close, 9)
        ema_21 = compute_ema(close, 21)
        ema_100 = compute_ema(close, 100)
        
        return {
            'close': close,
            'high': high,
            'low': low,
            'open': open_p,
            'rsi_14': rsi_14,
            'bb_sma': bb_sma,
            'bb_std': bb_std,
            'ema_9': ema_9,
            'ema_21': ema_21,
            'ema_100': ema_100,
            'has_vol': has_vol,
            'orig_indices': df.index
        }

    def generate_signals(self, df: pd.DataFrame = None, params: dict = None, precomputed: dict = None, as_list: bool = False, **kwargs) -> pd.Series:
        if precomputed is None and isinstance(df, dict):
            precomputed = df
            df = None


        if df is not None and (df.empty or len(df) == 0 or 'close' not in df.columns):
            return pd.Series(dtype=object, index=df.index)

        p = params or {}
        try:
            rsi_period = max(1, int(float(p.get("rsi_period", 14))))
        except (ValueError, TypeError):
            rsi_period = 14
        try:
            rsi_oversold = float(p.get("rsi_oversold", 30.0))
        except (ValueError, TypeError):
            rsi_oversold = 30.0
        try:
            rsi_overbought = float(p.get("rsi_overbought", 70.0))
        except (ValueError, TypeError):
            rsi_overbought = 70.0
        rsi_enabled = bool(p.get("rsi_enabled", True))
        
        try:
            bb_period = max(1, int(float(p.get("bb_period", 20))))
        except (ValueError, TypeError):
            bb_period = 20
        try:
            bb_std = float(p.get("bb_std", 2.0))
        except (ValueError, TypeError):
            bb_std = 2.0
        bb_enabled = bool(p.get("bb_enabled", True))
        
        try:
            ema_fast_period = max(1, int(float(p.get("ema_fast_period", 9))))
        except (ValueError, TypeError):
            ema_fast_period = 9
        try:
            ema_slow_period = max(1, int(float(p.get("ema_slow_period", 21))))
        except (ValueError, TypeError):
            ema_slow_period = 21
        ema_enabled = bool(p.get("ema_enabled", False))

        try:
            htf_ema_period = max(1, int(float(p.get("htf_ema_period", 100))))
        except (ValueError, TypeError):
            htf_ema_period = 100
        htf_ema_enabled = bool(p.get("htf_ema_enabled", False))
        
        if df is not None:
            close = df['close']
            high = df['high'] if 'high' in df.columns else close
            low = df['low'] if 'low' in df.columns else close
            open_p = df['open'] if 'open' in df.columns else close
            orig_indices = df.index
        elif isinstance(precomputed, dict) and len(precomputed) > 0 and ('orig_indices' in precomputed or 'close' in precomputed):
            orig_indices = precomputed.get('orig_indices', precomputed.get('close', pd.Series(dtype=float)).index)
            close = precomputed.get('close', pd.Series(dtype=float))
            high = precomputed.get('high', close)
            low = precomputed.get('low', close)
            open_p = precomputed.get('open', close)
        else:
            return pd.Series(dtype=object)

        if len(close) == 0:
            return pd.Series(dtype=object, index=orig_indices)
            
        from engine.indicators import compute_ema, compute_wilders_rsi

        # 1. RSI
        rsi_call = pd.Series(True, index=orig_indices)
        rsi_put = pd.Series(True, index=orig_indices)
        if rsi_enabled:
            rsi = precomputed['rsi_14'] if (rsi_period == 14 and isinstance(precomputed, dict) and 'rsi_14' in precomputed) else compute_wilders_rsi(close, rsi_period)
            prev_rsi = rsi.shift(1)
            if not bb_enabled and not ema_enabled:
                rsi_call = (prev_rsi <= rsi_oversold) & (rsi > prev_rsi)
                rsi_put = (prev_rsi >= rsi_overbought) & (rsi < prev_rsi)
            else:
                rsi_call = rsi <= rsi_oversold
                rsi_put = rsi >= rsi_overbought
            
        # 2. Bollinger Bands
        bb_call = pd.Series(True, index=orig_indices)
        bb_put = pd.Series(True, index=orig_indices)
        eff_bb = min(len(close), bb_period)
        if bb_enabled:
            if bb_period == 20 and isinstance(precomputed, dict) and 'bb_sma' in precomputed and 'bb_std' in precomputed:
                sma = precomputed['bb_sma']
                std = precomputed['bb_std']
            else:
                sma = close.rolling(window=eff_bb, min_periods=1).mean()
                std = close.rolling(window=eff_bb, min_periods=1).std(ddof=0).fillna(0.0)
            upper_band = sma + (std * bb_std)
            lower_band = sma - (std * bb_std)
            
            prev_close = close.shift(1)
            prev_lower = lower_band.shift(1)
            prev_upper = upper_band.shift(1)
            
            bb_call = (prev_close <= prev_lower) & (close > lower_band)
            bb_put = (prev_close >= prev_upper) & (close < upper_band)
            
        # 3. EMA Cross
        ema_call = pd.Series(True, index=orig_indices)
        ema_put = pd.Series(True, index=orig_indices)
        if ema_enabled:
            fast_ema = precomputed['ema_9'] if (ema_fast_period == 9 and isinstance(precomputed, dict) and 'ema_9' in precomputed) else compute_ema(close, ema_fast_period)
            slow_ema = precomputed['ema_21'] if (ema_slow_period == 21 and isinstance(precomputed, dict) and 'ema_21' in precomputed) else compute_ema(close, ema_slow_period)
            
            prev_fast = fast_ema.shift(1)
            prev_slow = slow_ema.shift(1)
            
            ema_call = (prev_fast <= prev_slow) & (fast_ema > slow_ema)
            ema_put = (prev_fast >= prev_slow) & (fast_ema < slow_ema)
            
        # 4. HTF Trend Filter
        htf_call = pd.Series(True, index=orig_indices)
        htf_put = pd.Series(True, index=orig_indices)
        if htf_ema_enabled:
            htf_ema = precomputed['ema_100'] if (htf_ema_period == 100 and isinstance(precomputed, dict) and 'ema_100' in precomputed) else compute_ema(close, htf_ema_period)
            htf_call = close > htf_ema
            htf_put = close < htf_ema
            
        signals = pd.Series(index=orig_indices, data=None, dtype=object)
        
        call_cond = rsi_call & bb_call & ema_call & htf_call
        put_cond = rsi_put & bb_put & ema_put & htf_put
        
        conflict = call_cond & put_cond
        call_cond = call_cond & (~conflict)
        put_cond = put_cond & (~conflict)
        
        signals.loc[call_cond] = 'CALL'
        signals.loc[put_cond] = 'PUT'

        if as_list or kwargs.get('as_list', False):
            sig_list = []
            time_col = df['open_time'] if (df is not None and 'open_time' in df.columns) else (df['time'] if (df is not None and 'time' in df.columns) else None)
            active_idx = orig_indices[call_cond | put_cond]
            for idx in active_idx:
                d = 'CALL' if call_cond.loc[idx] else 'PUT'
                t_val = int(time_col.loc[idx]) if time_col is not None else 0
                if t_val > 1e11:
                    t_val = int(t_val // 1000)
                p_val = float(close.loc[idx])
                sig_list.append({
                    "time": t_val,
                    "direction": d,
                    "price": p_val,
                    "index": idx
                })
            return sig_list
        
        return signals

    def generate_signals_list(self, df: pd.DataFrame = None, params: dict = None, precomputed: dict = None, **kwargs) -> list[dict]:
        return self.generate_signals(df=df, params=params, precomputed=precomputed, as_list=True, **kwargs)

