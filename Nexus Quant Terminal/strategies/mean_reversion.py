import pandas as pd
import numpy as np
from .base import BaseStrategy

class MeanReversionStrategy(BaseStrategy):
    name = "Mean Reversion"
    description = "Mean reversion strategy based on SMA and ATR filter."

    def get_params_schema(self) -> list[dict]:
        return [
            {"name": "sma_period", "type": "int", "default": 20, "min": 2, "max": 200, "step": 1, "description": "Periodo de la SMA"},
            {"name": "threshold", "type": "float", "default": 0.015, "min": 0.001, "max": 0.1, "step": 0.001, "description": "Umbral de desviacion (1.5% = 0.015)"},
            {"name": "atr_period", "type": "int", "default": 14, "min": 2, "max": 100, "step": 1, "description": "Periodo del ATR"},
            {"name": "atr_threshold_percentile", "type": "float", "default": 50, "min": 10, "max": 90, "step": 5, "description": "Percentil maximo de ATR permitido (para rango)"}
        ]

    def prepare_data(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty or 'close' not in df.columns:
            return {}
        close = df['close']
        high = df['high'] if 'high' in df.columns else close
        low = df['low'] if 'low' in df.columns else close
        open_p = df['open'] if 'open' in df.columns else close
        volume = df['volume'] if 'volume' in df.columns else pd.Series(1.0, index=df.index)
        
        eff_sma = min(max(1, len(close)), 20)
        eff_atr = min(max(1, len(close)), 14)
        sma_20 = close.rolling(window=eff_sma, min_periods=1).mean()
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14 = tr.rolling(window=eff_atr, min_periods=1).mean()
        return {
            'close': close,
            'high': high,
            'low': low,
            'open': open_p,
            'volume': volume,
            'sma_20': sma_20,
            'atr_14': atr_14,
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
            sma_period = max(1, int(float(p.get("sma_period", 20))))
        except (ValueError, TypeError):
            sma_period = 20
        try:
            threshold = float(p.get("threshold", 0.015))
        except (ValueError, TypeError):
            threshold = 0.015
        try:
            atr_period = max(1, int(float(p.get("atr_period", 14))))
        except (ValueError, TypeError):
            atr_period = 14
        try:
            atr_percentile = float(p.get("atr_threshold_percentile", 50))
        except (ValueError, TypeError):
            atr_percentile = 50.0
        try:
            std_devs = float(p.get("std_devs", 0.0))
        except (ValueError, TypeError):
            std_devs = 0.0
        rsi_filter = bool(p.get("rsi_filter", False))
        
        if df is not None:
            close = df['close']
            high = df['high'] if 'high' in df.columns else close
            low = df['low'] if 'low' in df.columns else close
            orig_indices = df.index
        elif isinstance(precomputed, dict) and len(precomputed) > 0 and ('orig_indices' in precomputed or 'close' in precomputed or 'sma_20' in precomputed):
            orig_indices = precomputed.get('orig_indices', precomputed.get('sma_20', pd.Series(dtype=float)).index)
            close = precomputed.get('close', precomputed.get('sma_20', pd.Series(dtype=float)))
            high = precomputed.get('high', close)
            low = precomputed.get('low', close)
        else:
            return pd.Series(dtype=object)

        if len(close) == 0:
            return pd.Series(dtype=object, index=orig_indices)

        eff_sma = min(len(close), sma_period)
        sma = precomputed['sma_20'] if (sma_period == 20 and isinstance(precomputed, dict) and 'sma_20' in precomputed) else close.rolling(window=eff_sma, min_periods=1).mean()
        
        if std_devs > 0:
            rolling_std = close.rolling(window=eff_sma, min_periods=1).std(ddof=0).fillna(0.0)
            upper_band = sma + (rolling_std * std_devs)
            lower_band = sma - (rolling_std * std_devs)
        else:
            upper_band = sma * (1 + threshold)
            lower_band = sma * (1 - threshold)
        
        if atr_period == 14 and isinstance(precomputed, dict) and 'atr_14' in precomputed:
            atr = precomputed['atr_14']
        else:
            eff_atr = min(len(close), atr_period)
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=eff_atr, min_periods=1).mean()
        
        min_p = min(max(1, len(atr)), 10)
        atr_limit = atr.rolling(window=1000, min_periods=min_p).quantile(atr_percentile / 100.0).fillna(atr)
        ranging_market = atr <= atr_limit
        
        if rsi_filter:
            from engine.indicators import compute_wilders_rsi
            rsi = compute_wilders_rsi(close, 14)
            rsi_call = rsi <= 35
            rsi_put = rsi >= 65
        else:
            rsi_call = True
            rsi_put = True
        
        signals = pd.Series(index=orig_indices, data=None, dtype=object)
        
        call_cond = (close < lower_band) & ranging_market & rsi_call
        put_cond = (close > upper_band) & ranging_market & rsi_put
        
        signals.loc[call_cond] = 'CALL'
        signals.loc[put_cond] = 'PUT'
        
        return signals
