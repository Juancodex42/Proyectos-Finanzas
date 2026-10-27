"""
Descargador de Máximo Histórico de Datos (All Available History)
Para Criptos (Binance desde inicio 2017+), Forex, Commodities e Índices (Yahoo Finance con period='max').
"""

import os
import csv
import time
import json
import urllib.request
import urllib.parse
import numpy as np
import yfinance as yf
from datetime import datetime, timezone

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(RAW_DIR, exist_ok=True)

BINANCE_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", 
    "ADAUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "TRXUSDT", "DOTUSDT"
]

YFINANCE_TICKERS = {
    "EURUSD": "EURUSD=X",
    "GBPJPY": "GBPJPY=X",
    "AUDNZD": "AUDNZD=X",
    "USDCAD": "USDCAD=X",
    "XAUUSD": "GC=F",
    "WTI": "CL=F",
    "NASDAQ": "^NDX"
}

CSV_HEADERS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_base",
    "taker_buy_quote", "datetime"
]

def ms_to_dt(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def download_binance_all(symbol, interval="1d"):
    # Start from 2017-01-01 (timestamp: 1483228800000)
    start_time = 1483228800000
    end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    url_base = "https://api.binance.com/api/v3/klines"
    all_candles = []
    current_start = start_time
    
    print(f" Descargando Binance MAX: {symbol} [{interval}]...")
    
    while current_start < end_time:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "limit": 1000
        }
        url = f"{url_base}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "BinSim/2.0"})
        
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                if not data:
                    break
                for c in data:
                    all_candles.append([
                        c[0], float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5]),
                        c[6], float(c[7]), int(c[8]), float(c[9]), float(c[10]), ms_to_dt(c[0])
                    ])
                last_t = data[-1][0]
                if last_t <= current_start:
                    break
                current_start = last_t + 1
                time.sleep(0.12)
        except Exception as e:
            print(f" Error con {symbol}: {e}. Reintentando...")
            time.sleep(1.5)
            
    seen = set()
    unique = []
    for c in all_candles:
        if c[0] not in seen:
            seen.add(c[0])
            unique.append(c)
    unique.sort(key=lambda x: x[0])
    
    # Save to raw dir
    out_f1 = os.path.join(RAW_DIR, f"{symbol}_{interval}.csv")
    with open(out_f1, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADERS)
        w.writerows(unique)

    # Save to root data dir
    out_f2 = os.path.join(DATA_DIR, f"{symbol}_{interval}.csv")
    with open(out_f2, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADERS)
        w.writerows(unique)
        
    print(f"  [OK] {symbol}_{interval}.csv -> {len(unique)} velas ({ms_to_dt(unique[0][0]) if unique else ''} - {ms_to_dt(unique[-1][0]) if unique else ''})")
    return len(unique)

def download_yahoo_all():
    for name, ticker in YFINANCE_TICKERS.items():
        print(f" Descargando Yahoo MAX: {name} ({ticker})...")
        try:
            df = yf.download(ticker, period="max", interval="1d")
            if not df.empty:
                candles = []
                for idx, row in df.iterrows():
                    dt = idx.to_pydatetime()
                    open_time_ms = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
                    close_time_ms = open_time_ms + (24 * 60 * 60 * 1000) - 1
                    
                    def safe_val(val):
                        if hasattr(val, 'iloc'):
                            return float(val.iloc[0])
                        return float(val)
                        
                    op = safe_val(row['Open'])
                    hi = safe_val(row['High'])
                    lo = safe_val(row['Low'])
                    cl = safe_val(row['Close'])
                    vol = safe_val(row['Volume']) if 'Volume' in row else 0.0
                    
                    if not (np.isnan(op) or np.isnan(hi) or np.isnan(lo) or np.isnan(cl)):
                        candles.append([
                            open_time_ms, op, hi, lo, cl, vol,
                            close_time_ms, vol, 100, vol, vol,
                            dt.strftime("%Y-%m-%d %H:%M:%S")
                        ])
                        
                seen = set()
                unique = []
                for c in candles:
                    if c[0] not in seen:
                        seen.add(c[0])
                        unique.append(c)
                unique.sort(key=lambda x: x[0])
                
                out_f1 = os.path.join(RAW_DIR, f"{name}_1d.csv")
                with open(out_f1, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(CSV_HEADERS)
                    w.writerows(unique)

                out_f2 = os.path.join(DATA_DIR, f"{name}_1d.csv")
                with open(out_f2, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(CSV_HEADERS)
                    w.writerows(unique)
                    
                print(f"  [OK] {name}_1d.csv -> {len(unique)} velas ({ms_to_dt(unique[0][0]) if unique else ''} - {ms_to_dt(unique[-1][0]) if unique else ''})")
        except Exception as e:
            print(f" Error descargando {name}: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("  Descargando todo el Histórico Disponible (Binance + Yahoo)")
    print("=" * 60)
    for sym in BINANCE_SYMBOLS:
        download_binance_all(sym, "1d")
    download_yahoo_all()
    print("=" * 60)
    print("  ¡Descarga masiva de máximo histórico completada exitosamente!")
    print("=" * 60)
