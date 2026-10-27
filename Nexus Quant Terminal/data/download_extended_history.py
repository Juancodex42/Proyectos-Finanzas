"""
Descarga masiva de 5 años de datos (1825+ días) en temporalidad Diaria (1d) y 4 Horas (4h)
para Criptos, Forex, Commodities e Índices para construir un Dataset Cuantitativo Robusto (N > 1000 trades).
"""

import os
import csv
import time
import json
import urllib.request
import urllib.parse
import numpy as np
from datetime import datetime, timedelta, timezone

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Binance symbols (5 years)
BINANCE_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", 
    "ADAUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "TRXUSDT", "DOTUSDT"
]

# Yahoo symbols via API / download
YFINANCE_TICKERS = {
    "EURUSD": "EURUSD=X",
    "GBPJPY": "GBPJPY=X",
    "AUDNZD": "AUDNZD=X",
    "USDCAD": "USDCAD=X",
    "XAUUSD": "GC=F",
    "WTI": "CL=F",
    "NASDAQ": "^NDX"
}

DAYS_BACK_5Y = 1825  # 5 años

CSV_HEADERS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_base",
    "taker_buy_quote", "datetime"
]

def ms_to_dt(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def download_binance_klines(symbol, interval, days_back):
    end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_time = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp() * 1000)
    
    url_base = "https://api.binance.com/api/v3/klines"
    all_candles = []
    current_start = start_time
    
    print(f"Descargando Binance: {symbol} [{interval}] desde {ms_to_dt(start_time)} hasta {ms_to_dt(end_time)}...")
    
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
                current_start = data[-1][0] + 1
                time.sleep(0.15)
        except Exception as e:
            print(f" Error {symbol} {interval}: {e}. Reintentando...")
            time.sleep(2)
            
    seen = set()
    unique = []
    for c in all_candles:
        if c[0] not in seen:
            seen.add(c[0])
            unique.append(c)
    unique.sort(key=lambda x: x[0])
    
    output_file = os.path.join(OUTPUT_DIR, f"{symbol}_{interval}.csv")
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADERS)
        w.writerows(unique)
        
    print(f"  [OK] {symbol}_{interval}.csv -> {len(unique)} velas")
    return len(unique)

def download_yahoo_5y():
    try:
        import yfinance as yf
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=DAYS_BACK_5Y)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        for name, ticker in YFINANCE_TICKERS.items():
            print(f"Descargando Yahoo 5Y: {name} ({ticker})...")
            try:
                df = yf.download(ticker, start=start_str, end=end_str, interval="1d")
                if not df.empty:
                    candles = []
                    for idx, row in df.iterrows():
                        dt = idx.to_pydatetime()
                        open_time_ms = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
                        close_time_ms = open_time_ms + (24 * 60 * 60 * 1000) - 1
                        op = float(row['Open'].iloc[0]) if hasattr(row['Open'], 'iloc') else float(row['Open'])
                        hi = float(row['High'].iloc[0]) if hasattr(row['High'], 'iloc') else float(row['High'])
                        lo = float(row['Low'].iloc[0]) if hasattr(row['Low'], 'iloc') else float(row['Low'])
                        cl = float(row['Close'].iloc[0]) if hasattr(row['Close'], 'iloc') else float(row['Close'])
                        vol = float(row['Volume'].iloc[0]) if ('Volume' in row and hasattr(row['Volume'], 'iloc')) else 0.0
                        if not (np.isnan(op) or np.isnan(hi) or np.isnan(lo) or np.isnan(cl)):
                            candles.append([open_time_ms, op, hi, lo, cl, vol, close_time_ms, vol, 100, vol, vol, dt.strftime("%Y-%m-%d %H:%M:%S")])
                    candles.sort(key=lambda x: x[0])
                    out_f = os.path.join(OUTPUT_DIR, f"{name}_1d.csv")
                    with open(out_f, "w", newline="", encoding="utf-8") as f:
                        w = csv.writer(f)
                        w.writerow(CSV_HEADERS)
                        w.writerows(candles)
                    print(f"  [OK] {name}_1d.csv -> {len(candles)} velas")
            except Exception as e:
                print(f" Error con {name}: {e}")
    except ImportError:
        print("yfinance no está instalado.")

if __name__ == "__main__":
    download_yahoo_5y()
