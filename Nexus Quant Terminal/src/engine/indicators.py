import numpy as np
import pandas as pd

def compute_wilders_rsi(close: pd.Series, period: int) -> pd.Series:
    """
    Computes Wilder's Smoothing RSI matching the Rust implementation exactly.
    Safely handles empty series, period <= 0, and non-finite series.
    """
    if close is None or len(close) == 0:
        return pd.Series(dtype=float, index=close.index if close is not None else None)
        
    try:
        period = max(1, int(period))
    except (TypeError, ValueError):
        period = 14

    closes_val = close.values
    n = len(closes_val)
    rsi_vals = np.full(n, np.nan, dtype=float)
    
    if n <= period:
        return pd.Series(rsi_vals, index=close.index)
        
    gains = np.zeros(n)
    losses = np.zeros(n)
    
    for i in range(1, n):
        diff = closes_val[i] - closes_val[i - 1]
        if np.isnan(diff):
            continue
        if diff > 0:
            gains[i] = diff
        else:
            losses[i] = -diff
            
    # First Average Gain & Loss (SMA of first 'period' diffs)
    sum_gain = np.nansum(gains[1:period + 1])
    sum_loss = np.nansum(losses[1:period + 1])
    avg_gain = sum_gain / period
    avg_loss = sum_loss / period
    
    if avg_loss == 0.0:
        rsi_vals[period] = 50.0 if avg_gain == 0.0 else 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_vals[period] = 100.0 - (100.0 / (1.0 + rs))
        
    for i in range(period + 1, n):
        g = 0.0 if np.isnan(gains[i]) else gains[i]
        l = 0.0 if np.isnan(losses[i]) else losses[i]
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
        
        if avg_loss == 0.0:
            rsi_vals[i] = 50.0 if avg_gain == 0.0 else 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_vals[i] = 100.0 - (100.0 / (1.0 + rs))
            
    return pd.Series(rsi_vals, index=close.index)


def compute_ema(close: pd.Series, period: int) -> pd.Series:
    """
    Computes EMA with SMA initialization matching the Rust implementation exactly.
    Safely handles empty series, period <= 0, and non-finite series.
    """
    if close is None or len(close) == 0:
        return pd.Series(dtype=float, index=close.index if close is not None else None)

    try:
        period = max(1, int(period))
    except (TypeError, ValueError):
        period = 20

    closes_val = close.values
    n = len(closes_val)
    ema_vals = np.full(n, np.nan, dtype=float)
    
    if n < period:
        return pd.Series(ema_vals, index=close.index)
        
    k = 2.0 / (period + 1)
    
    # First SMA
    sma = np.nanmean(closes_val[:period])
    ema_vals[period - 1] = sma
    
    for i in range(period, n):
        val = closes_val[i]
        prev = ema_vals[i - 1]
        if np.isnan(val):
            ema_vals[i] = prev
        elif np.isnan(prev):
            ema_vals[i] = val
        else:
            ema_vals[i] = val * k + prev * (1.0 - k)
        
    return pd.Series(ema_vals, index=close.index)
