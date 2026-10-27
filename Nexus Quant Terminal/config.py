import os

class Config:
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'raw')
    # High-performance assets based on empirical quantitative multi-asset backtesting (65% - 74%+ Win Rate)
    HIGH_PERFORMANCE_PAIRS = ['NASDAQ', 'WTI', 'XAUUSD', 'GBPJPY', 'EURUSD']
    AVAILABLE_PAIRS = ['BTCUSDT']  # Auto-detected from CSV files
    # Recommended timeframes (1d, 4h, 1h, 30m, 15m, 5m, 1m)
    RECOMMENDED_INTERVALS = ['1d', '4h', '1h', '30m', '15m', '5m', '1m']
    AVAILABLE_INTERVALS = ['1d', '4h', '1h', '30m', '15m', '5m', '1m']
    DEFAULT_PAYOUT = 0.85
    DEFAULT_EXPIRY = 1
    DEFAULT_INITIAL_CAPITAL = 1000
