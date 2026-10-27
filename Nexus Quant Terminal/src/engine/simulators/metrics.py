import math
import numpy as np
import pandas as pd

# Tolerancia para comparaciones de precios flotantes (evita falsos TIE/WIN por errores IEEE754)
_PRICE_EPS = 1e-8

__all__ = ["_PRICE_EPS", "compute_atr", "compute_sharpe_sortino"]



def compute_atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    """
    Calcula el Average True Range (ATR) de Wilder de forma vectorizada.
    """
    if df is None or len(df) == 0:
        return np.array([], dtype=np.float64)
    n = len(df)
    if n < period:
        return np.full(n, 1e-4, dtype=np.float64)

    high = df['high'].to_numpy(dtype=np.float64)
    low = df['low'].to_numpy(dtype=np.float64)
    close = df['close'].to_numpy(dtype=np.float64)

    tr = np.zeros(n, dtype=np.float64)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))

    atr = np.zeros(n, dtype=np.float64)
    # Causal expanding mean for initial warm-up period (zero lookahead bias)
    for i in range(min(period - 1, n)):
        atr[i] = np.mean(tr[:i + 1])
    if n >= period:
        atr[period - 1] = np.mean(tr[:period])
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def compute_sharpe_sortino(pnl_arr: np.ndarray, initial_capital: float, total_trades: int) -> tuple[float, float]:
    """
    Computes mathematically sound Sharpe and Sortino ratios based on normalized percentage returns.
    - Sharpe: (Mean Return - Rf) / Std(Return) * sqrt(252)
    - Sortino: Mean Return / Downside Deviation * sqrt(252) where Downside Dev is calculated
      relative to MAR=0 across the full return distribution.
    """
    if len(pnl_arr) < 2 or initial_capital <= 0 or total_trades < 2:
        return 0.0, 0.0
    returns_pct = pnl_arr / float(initial_capital)
    mean_ret = float(np.mean(returns_pct))
    std_ret = float(np.std(returns_pct))
    sharpe = float((mean_ret / (std_ret + 1e-8)) * np.sqrt(252)) if std_ret > 1e-8 else 0.0

    # Downside deviation relative to MAR=0 across the entire distribution
    downside_diffs = np.minimum(0.0, returns_pct)
    downside_dev = float(np.sqrt(np.mean(downside_diffs ** 2)))
    sortino = float((mean_ret / (downside_dev + 1e-8)) * np.sqrt(252)) if downside_dev > 1e-8 else 0.0
    return sharpe, sortino
