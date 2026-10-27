import pytest
import pandas as pd
import numpy as np
try:
    from tests.conftest import (
        generate_custom_length_ohlcv,
        generate_zero_volume_ohlcv,
        generate_flat_price_ohlcv,
        generate_nan_ohlcv
    )
except ImportError:
    from .conftest import (
        generate_custom_length_ohlcv,
        generate_zero_volume_ohlcv,
        generate_flat_price_ohlcv,
        generate_nan_ohlcv
    )

def test_synthetic_ohlcv_df_fixture(synthetic_ohlcv_df):
    assert isinstance(synthetic_ohlcv_df, pd.DataFrame)
    assert len(synthetic_ohlcv_df) == 500
    for col in ['open', 'high', 'low', 'close', 'volume', 'Open', 'High', 'Low', 'Close', 'Volume', 'open_time']:
        assert col in synthetic_ohlcv_df.columns
    # Assert High >= Open/Close and Low <= Open/Close
    assert (synthetic_ohlcv_df['high'] >= synthetic_ohlcv_df[['open', 'close']].max(axis=1)).all()
    assert (synthetic_ohlcv_df['low'] <= synthetic_ohlcv_df[['open', 'close']].min(axis=1)).all()

def test_multi_asset_ohlcv_dict_fixture(multi_asset_ohlcv_dict):
    assert isinstance(multi_asset_ohlcv_dict, dict)
    assert set(multi_asset_ohlcv_dict.keys()) == {'EURUSD', 'GBPUSD', 'USDJPY'}
    for pair, df in multi_asset_ohlcv_dict.items():
        assert len(df) == 500

def test_base_signals_series_fixture(base_signals_series):
    assert isinstance(base_signals_series, pd.Series)
    assert len(base_signals_series) == 500
    unique_vals = set(base_signals_series.unique())
    assert unique_vals.issubset({'CALL', 'PUT', 'HOLD'})

def test_boundary_helpers():
    df_custom = generate_custom_length_ohlcv(n_rows=50)
    assert len(df_custom) == 50

    df_zero_vol = generate_zero_volume_ohlcv(n_rows=100)
    assert (df_zero_vol['volume'] == 0).all()

    df_flat = generate_flat_price_ohlcv(n_rows=100, start_price=150.0)
    assert (df_flat['close'] == 150.0).all()

    df_nan = generate_nan_ohlcv(n_rows=100, nan_ratio=0.1)
    assert df_nan.isna().sum().sum() > 0
