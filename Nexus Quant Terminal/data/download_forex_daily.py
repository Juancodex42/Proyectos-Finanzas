"""
Descarga datos históricos diarios de Yahoo Finance para Forex, Oro, Petróleo y Nasdaq usando yfinance.
Guarda en CSV con la estructura compatible con BinSim.
"""

import os
import csv
from datetime import datetime, timedelta, timezone
import yfinance as yf
import pandas as pd
import numpy as np

# Configuración de Activos
TICKERS = {
    "EURUSD": "EURUSD=X",
    "GBPJPY": "GBPJPY=X",
    "AUDNZD": "AUDNZD=X",
    "USDCAD": "USDCAD=X",
    "XAUUSD": "GC=F",     # Oro
    "WTI": "CL=F",        # Petróleo
    "NASDAQ": "^NDX"      # Nasdaq 100
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
DAYS_BACK = 730  # 2 años

CSV_HEADERS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_base",
    "taker_buy_quote", "datetime"
]


def download_ticker(name, ticker, days_back):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_file = os.path.join(OUTPUT_DIR, f"{name}_1d.csv")

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_back)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    print(f"\nDescargando {name} ({ticker}) usando yfinance...")
    
    try:
        # Descarga con yfinance
        df = yf.download(ticker, start=start_str, end=end_str, interval="1d")
        if df.empty:
            print(f"  [ERROR] No se obtuvieron datos para {name}")
            return None, 0
    except Exception as e:
        print(f"  Error descargando {name}: {e}")
        return None, 0

    candles = []
    for index, row in df.iterrows():
        try:
            # Obtener timestamp a partir del index (Date)
            dt = index.to_pydatetime()
            # Hacer dt consciente de zona horaria (UTC) para evitar desfasaje local al llamar timestamp()
            open_time_ms = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
            close_time_ms = open_time_ms + (24 * 60 * 60 * 1000) - 1
            
            # yfinance puede devolver series en raras ocasiones, extraemos valor float
            op = float(row['Open'].iloc[0]) if hasattr(row['Open'], 'iloc') else float(row['Open'])
            hi = float(row['High'].iloc[0]) if hasattr(row['High'], 'iloc') else float(row['High'])
            lo = float(row['Low'].iloc[0]) if hasattr(row['Low'], 'iloc') else float(row['Low'])
            cl = float(row['Close'].iloc[0]) if hasattr(row['Close'], 'iloc') else float(row['Close'])
            
            # Chequear volumen si está presente
            vol = 0.0
            if 'Volume' in row:
                v_val = row['Volume']
                vol = float(v_val.iloc[0]) if hasattr(v_val, 'iloc') else float(v_val)
            
            if np.isnan(op) or np.isnan(hi) or np.isnan(lo) or np.isnan(cl):
                continue
                
            candle = [
                open_time_ms,
                op,
                hi,
                lo,
                cl,
                vol,
                close_time_ms,
                vol,  # quote_volume (simulado)
                100,  # number of trades (simulado)
                vol,  # taker buy base volume (simulado)
                vol,  # taker buy quote volume (simulado)
                dt.strftime("%Y-%m-%d %H:%M:%S")
            ]
            candles.append(candle)
        except Exception as ex:
            continue

    # Ordenar por timestamp
    candles.sort(key=lambda x: x[0])

    if not candles:
        print(f"  [ERROR] No se obtuvieron velas válidas para {name}")
        return None, 0

    # Guardar en nuestro formato
    with open(output_file, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(CSV_HEADERS)
        writer.writerows(candles)

    print(f"  [OK] Guardado: {output_file} ({len(candles)} velas)")
    return output_file, len(candles)


def main():
    print("=" * 60)
    print("  BinSim - Descarga de Datos de Yahoo Finance (Forex/Macro) usando yfinance")
    print("=" * 60)

    # pandas y numpy se importan a nivel de módulo

    results = []
    for name, ticker in TICKERS.items():
        file_path, count = download_ticker(name, ticker, DAYS_BACK)
        if file_path:
            results.append((name, file_path, count))

    print("\n" + "=" * 60)
    print("  RESUMEN DE DESCARGA")
    print("=" * 60)
    for name, file_path, count in results:
        print(f"  {name:<8s}: {count:>6,} velas -> {file_path}")
    print("=" * 60)
    print("Listo! Datos guardados en:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
