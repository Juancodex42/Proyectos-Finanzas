"""
SQLite database schema, indices, and parsing utility functions.
"""
import json
from datetime import datetime
from typing import Optional, Any

def _safe_json_list(val: Any) -> list:
    """Parsea de forma segura una cadena JSON que debería contener una lista."""
    if not val:
        return []
    try:
        parsed = json.loads(val)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _parse_float(val: Any, default: float) -> float:
    try:
        return float(val) if val not in (None, "") else default
    except (ValueError, TypeError):
        return default


def _parse_int(val: Any, default: int) -> int:
    try:
        return int(val) if val not in (None, "") else default
    except (ValueError, TypeError):
        return default


def _parse_db_datetime(val: Any) -> Optional[datetime]:
    """Parsea de forma segura timestamps devueltos por SQLite en objetos datetime."""
    if isinstance(val, datetime):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return datetime.fromisoformat(val)
        except Exception:
            try:
                return datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None
    return None


SCHEMA = """
CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    asset TEXT NOT NULL,
    trade_type TEXT NOT NULL,
    payment_method TEXT,
    volume_filter REAL,
    snapshot_json TEXT
);

CREATE TABLE IF NOT EXISTS exchange_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    asset TEXT NOT NULL,
    payment_method TEXT,
    price_ars REAL,
    spot_price_usdt REAL,
    tc_implicito REAL,
    position INTEGER,
    advertiser_no TEXT,
    advertiser_nickname TEXT,
    advertiser_completion_rate REAL,
    advertiser_order_count INTEGER
);

CREATE TABLE IF NOT EXISTS usdt_sell_benchmark (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    payment_method TEXT NOT NULL,
    volume_filter REAL,
    avg_top10_price REAL,
    individual_prices_json TEXT
);

CREATE TABLE IF NOT EXISTS my_ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adv_no TEXT UNIQUE NOT NULL,
    asset TEXT NOT NULL,
    ad_group INTEGER NOT NULL,
    current_price REAL,
    payment_methods_json TEXT,
    status INTEGER DEFAULT 1,
    init_amount REAL DEFAULT 0.0,
    surplus_amount REAL DEFAULT 0.0,
    min_trans_amount REAL DEFAULT 0.0,
    max_trans_amount REAL DEFAULT 0.0,
    last_repositioned DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS my_sell_ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adv_no TEXT UNIQUE NOT NULL,
    asset TEXT NOT NULL,
    ad_group INTEGER NOT NULL,
    current_price REAL,
    payment_methods_json TEXT,
    status INTEGER DEFAULT 1,
    init_amount REAL DEFAULT 0.0,
    surplus_amount REAL DEFAULT 0.0,
    min_trans_amount REAL DEFAULT 0.0,
    max_trans_amount REAL DEFAULT 0.0,
    last_repositioned DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    adv_no TEXT NOT NULL,
    asset TEXT NOT NULL,
    ad_group INTEGER,
    old_price REAL,
    new_price REAL,
    reason TEXT,
    competitor_best_price REAL,
    competitor_no TEXT,
    tc_implicito REAL,
    benchmark_by_method_json TEXT,
    margin_worst REAL,
    liquidity_ars REAL
);

CREATE TABLE IF NOT EXISTS price_wars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME,
    asset TEXT,
    payment_method TEXT,
    competitor_no TEXT,
    competitor_nickname TEXT,
    escalations INTEGER,
    my_price_at_start REAL,
    competitor_price_at_start REAL,
    outcome TEXT
);

CREATE TABLE IF NOT EXISTS payment_method_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    identifier TEXT NOT NULL,
    pay_id INTEGER DEFAULT 0,
    sellers_count INTEGER,
    buyers_count INTEGER,
    spread REAL,
    score REAL,
    selected BOOLEAN DEFAULT 0,
    assigned_group INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS detected_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT UNIQUE,
    adv_no TEXT,
    timestamp DATETIME,
    asset TEXT,
    trade_type TEXT,
    amount_crypto REAL,
    amount_ars REAL,
    price REAL,
    tc_implicito REAL,
    payment_method TEXT,
    counterparty TEXT,
    status TEXT,
    detected_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS liquidity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,
    order_no TEXT,
    asset TEXT,
    amount_ars REAL,
    amount_crypto REAL,
    balance_after REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS spot_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    asset TEXT NOT NULL,
    price_usdt REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS bot_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_profiles (
    advertiser_no TEXT PRIMARY KEY,
    nickname TEXT,
    max_order_count INTEGER DEFAULT 0,
    avg_completion_rate REAL DEFAULT 0.0,
    assets_json TEXT DEFAULT '[]',
    methods_json TEXT DEFAULT '[]',
    times_seen INTEGER DEFAULT 0,
    times_top1 INTEGER DEFAULT 0,
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_hourly_summary (
    hour_bucket TEXT NOT NULL,
    asset TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    best_price_avg REAL DEFAULT 0.0,
    best_price_max REAL DEFAULT 0.0,
    best_tc_avg REAL DEFAULT 0.0,
    spot_price_avg REAL DEFAULT 0.0,
    top_competitor_nick TEXT DEFAULT '',
    samples_count INTEGER DEFAULT 0,
    PRIMARY KEY (hour_bucket, asset, payment_method)
);

CREATE TABLE IF NOT EXISTS fiwind_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    bid REAL NOT NULL,
    ask REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_exchange_rates_asset ON exchange_rates(asset, timestamp);
CREATE INDEX IF NOT EXISTS idx_price_changes_adv ON price_changes(adv_no, timestamp);
CREATE INDEX IF NOT EXISTS idx_detected_orders_type ON detected_orders(trade_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_spot_prices_asset ON spot_prices(asset, timestamp);
CREATE INDEX IF NOT EXISTS idx_benchmark_method ON usdt_sell_benchmark(payment_method, timestamp);
CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON market_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_hourly_summary_asset ON market_hourly_summary(asset, hour_bucket);
CREATE INDEX IF NOT EXISTS idx_fiwind_quotes_ts ON fiwind_quotes(timestamp);
"""


