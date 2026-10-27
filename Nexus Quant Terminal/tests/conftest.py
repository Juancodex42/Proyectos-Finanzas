import pytest
import numpy as np
import pandas as pd


def generate_synthetic_ohlcv(
    n_rows: int = 500,
    start_price: float = 100.0,
    volatility: float = 0.5,
    seed: int = 42,
    freq: str = '1min',
    start_date: str = '2024-01-01 00:00:00',
    zero_volume: bool = False,
    flat_price: bool = False,
    nan_ratio: float = 0.0,
    nan_cols: list = None
) -> pd.DataFrame:
    """
    Helper function to generate deterministic, realistic OHLCV pandas DataFrames
    with boundary testing capabilities.
    """
    np.random.seed(seed)
    timestamps = pd.date_range(start=start_date, periods=n_rows, freq=freq)
    open_time_ms = (timestamps.astype('int64') // 10**6).astype('int64')

    if flat_price:
        close_prices = np.full(n_rows, start_price)
        open_prices = np.full(n_rows, start_price)
        high_prices = np.full(n_rows, start_price)
        low_prices = np.full(n_rows, start_price)
    else:
        returns = np.random.normal(loc=0.0001, scale=volatility / 100.0, size=n_rows)
        price_series = start_price * np.exp(np.cumsum(returns))
        
        noise_open = np.random.normal(0, 0.05, n_rows)
        open_prices = np.maximum(0.01, price_series + noise_open)
        close_prices = price_series
        
        spread = np.abs(np.random.normal(0.1, 0.05, n_rows))
        high_prices = np.maximum(open_prices, close_prices) + spread
        low_prices = np.minimum(open_prices, close_prices) - spread
        low_prices = np.maximum(0.001, low_prices)

    if zero_volume:
        volume = np.zeros(n_rows, dtype=float)
    else:
        volume = np.random.randint(100, 5000, size=n_rows).astype(float)

    df = pd.DataFrame({
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volume,
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volume,
        'open_time': open_time_ms
    }, index=timestamps)

    if nan_ratio > 0.0 and nan_cols:
        nan_indices = np.random.choice(n_rows, size=int(n_rows * nan_ratio), replace=False)
        for col in nan_cols:
            if col in df.columns:
                df.iloc[nan_indices, df.columns.get_loc(col)] = np.nan

    return df


@pytest.fixture
def synthetic_ohlcv_df() -> pd.DataFrame:
    """
    Returns a deterministic, realistic OHLCV pandas DataFrame (500 rows).
    """
    return generate_synthetic_ohlcv(n_rows=500, seed=42)


@pytest.fixture
def multi_asset_ohlcv_dict() -> dict:
    """
    Returns a dictionary mapping asset names ('EURUSD', 'GBPUSD', 'USDJPY')
    to synthetic OHLCV DataFrames.
    """
    assets = {
        'EURUSD': generate_synthetic_ohlcv(n_rows=500, start_price=1.0850, seed=101),
        'GBPUSD': generate_synthetic_ohlcv(n_rows=500, start_price=1.2650, seed=102),
        'USDJPY': generate_synthetic_ohlcv(n_rows=500, start_price=150.25, seed=103)
    }
    return assets


@pytest.fixture
def base_signals_series(synthetic_ohlcv_df) -> pd.Series:
    """
    Returns a deterministic Series of base trading signals ('CALL', 'PUT', 'HOLD' / 1, -1, 0).
    """
    np.random.seed(42)
    n_rows = len(synthetic_ohlcv_df)
    choices = ['CALL', 'PUT', 'HOLD']
    probs = [0.2, 0.2, 0.6]
    signals = np.random.choice(choices, size=n_rows, p=probs)
    return pd.Series(signals, index=synthetic_ohlcv_df.index, name='signal')


# Helper functions for boundary tests

def generate_custom_length_ohlcv(n_rows: int, seed: int = 42) -> pd.DataFrame:
    """Helper to generate OHLCV data with custom length."""
    return generate_synthetic_ohlcv(n_rows=n_rows, seed=seed)


def generate_zero_volume_ohlcv(n_rows: int = 200, seed: int = 42) -> pd.DataFrame:
    """Helper to generate OHLCV data with zero volume."""
    return generate_synthetic_ohlcv(n_rows=n_rows, zero_volume=True, seed=seed)


def generate_flat_price_ohlcv(n_rows: int = 200, start_price: float = 100.0) -> pd.DataFrame:
    """Helper to generate OHLCV data with flat (constant) price."""
    return generate_synthetic_ohlcv(n_rows=n_rows, start_price=start_price, flat_price=True)


def generate_nan_ohlcv(n_rows: int = 200, nan_ratio: float = 0.1, cols: list = None) -> pd.DataFrame:
    """Helper to generate OHLCV data containing NaN values for boundary testing."""
    if cols is None:
        cols = ['open', 'high', 'low', 'close', 'volume', 'Open', 'High', 'Low', 'Close', 'Volume']
    return generate_synthetic_ohlcv(n_rows=n_rows, nan_ratio=nan_ratio, nan_cols=cols, seed=42)
