"""
Descarga datos históricos OHLCV de Binance (API pública, sin API key).
Guarda en CSV para usar en BinSim.
"""

import urllib.request
import urllib.parse
import json
import csv
import os
import time
from datetime import datetime, timedelta, timezone

# --- Configuración ---
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", 
    "ADAUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "TRXUSDT",
    "DOTUSDT"
]
INTERVALS = ["1d"]
BASE_URL = "https://api.binance.com/api/v3/klines"
LIMIT = 1000  # Max por request
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")

# Cuántos días hacia atrás descargar
DAYS_BACK = 730  # ~2 años

CSV_HEADERS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_base",
    "taker_buy_quote", "datetime"
]


def ms_to_datetime(ms):
    """Convierte timestamp en milisegundos a string datetime."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def fetch_klines(symbol, interval, start_time, end_time=None, limit=1000):
    """Descarga un batch de velas de Binance."""
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "limit": limit
    }
    if end_time:
        params["endTime"] = end_time

    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "BinSim/1.0")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            return data
    except Exception as e:
        print(f"  Error en request: {e}")
        return None


def download_historical(symbol, interval, days_back):
    """Descarga el historial completo para un par e intervalo."""

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_file = os.path.join(OUTPUT_DIR, f"{symbol}_{interval}.csv")

    # Calcular timestamps
    end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_time = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp() * 1000)

    print(f"\n{'='*60}")
    print(f"Descargando {symbol} - {interval}")
    print(f"Desde: {ms_to_datetime(start_time)}")
    print(f"Hasta: {ms_to_datetime(end_time)}")
    print(f"{'='*60}")

    all_candles = []
    current_start = start_time
    batch_num = 0

    while current_start < end_time:
        batch_num += 1
        print(f"  Batch {batch_num}: desde {ms_to_datetime(current_start)}...", end=" ", flush=True)

        data = fetch_klines(symbol, interval, current_start, end_time, LIMIT)

        if data is None:
            print("RETRY en 5s...")
            time.sleep(5)
            continue

        if len(data) == 0:
            print("Sin más datos.")
            break

        # Procesar cada vela
        for candle in data:
            row = [
                candle[0],        # open_time (ms)
                float(candle[1]), # open
                float(candle[2]), # high
                float(candle[3]), # low
                float(candle[4]), # close
                float(candle[5]), # volume
                candle[6],        # close_time (ms)
                float(candle[7]), # quote_volume
                int(candle[8]),   # number of trades
                float(candle[9]), # taker buy base volume
                float(candle[10]),# taker buy quote volume
                ms_to_datetime(candle[0])  # datetime legible
            ]
            all_candles.append(row)

        print(f"{len(data)} velas (total: {len(all_candles)})")

        # Mover el start al último candle + 1ms
        current_start = data[-1][0] + 1

        # Rate limiting: Binance permite 1200 requests/minuto
        time.sleep(0.25)

    # Eliminar duplicados por open_time
    seen = set()
    unique_candles = []
    for candle in all_candles:
        if candle[0] not in seen:
            seen.add(candle[0])
            unique_candles.append(candle)

    # Ordenar por timestamp
    unique_candles.sort(key=lambda x: x[0])

    # Guardar CSV
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)
        writer.writerows(unique_candles)

    return output_file, len(unique_candles)


def update_symbol_incremental(symbol, interval="1d", days_back_fallback=730):
    """Actualiza incrementalmente el CSV de un par descargando solo velas faltantes."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_file = os.path.join(OUTPUT_DIR, f"{symbol}_{interval}.csv")
    
    if not os.path.exists(output_file):
        # Fallback a descarga histórica completa si no existe
        return download_historical(symbol, interval, days_back_fallback)

    # Leer CSV existente para encontrar la última fecha
    existing_rows = []
    last_open_time = 0
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if row and len(row) > 0:
                    try:
                        ot = int(row[0])
                        last_open_time = max(last_open_time, ot)
                        existing_rows.append(row)
                    except ValueError:
                        continue
    except Exception as e:
        print(f"Error leyendo CSV existente {output_file}: {e}")

    if last_open_time == 0:
        return download_historical(symbol, interval, days_back_fallback)

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    # Si la última vela fue hace menos de 20 horas, consideramos que ya está al día
    if (now_ms - last_open_time) < (20 * 3600 * 1000):
        return output_file, len(existing_rows)

    start_time = last_open_time + 1
    new_data = fetch_klines(symbol, interval, start_time, now_ms, LIMIT)
    
    if not new_data or len(new_data) == 0:
        return output_file, len(existing_rows)

    new_rows = []
    for candle in new_data:
        ot = candle[0]
        if ot > last_open_time:
            row = [
                ot,
                float(candle[1]),
                float(candle[2]),
                float(candle[3]),
                float(candle[4]),
                float(candle[5]),
                candle[6],
                float(candle[7]),
                int(candle[8]),
                float(candle[9]),
                float(candle[10]),
                ms_to_datetime(ot)
            ]
            new_rows.append(row)

    if not new_rows:
        return output_file, len(existing_rows)

    # Combinar y eliminar duplicados
    seen = set()
    all_rows = []
    for r in existing_rows + new_rows:
        try:
            ot = int(r[0])
            if ot not in seen:
                seen.add(ot)
                all_rows.append(r)
        except ValueError:
            pass

    all_rows.sort(key=lambda x: int(x[0]))

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)
        writer.writerows(all_rows)

    print(f"[INCREMENTAL] Actualizado {symbol} con {len(new_rows)} nuevas velas (Total: {len(all_rows)})")
    return output_file, len(all_rows)



def main():
    print("=" * 60)
    print("  BinSim - Descarga de Datos Históricos de Binance (Multi-Activo)")
    print("=" * 60)

    results = []
    
    # 1. Descargar 1d para todos los símbolos configurados
    for symbol in SYMBOLS:
        for interval in INTERVALS:
            file_path, count = download_historical(symbol, interval, DAYS_BACK)
            results.append((symbol, interval, file_path, count))
            
    # 2. Descargar 1h y 30m para BTCUSDT (compatibilidad con optimizador manual)
    for interval in ["1h", "30m"]:
        file_path, count = download_historical("BTCUSDT", interval, DAYS_BACK)
        results.append(("BTCUSDT", interval, file_path, count))

    print("\n" + "=" * 60)
    print("  RESUMEN DE DESCARGA")
    print("=" * 60)
    for symbol, interval, file_path, count in results:
        print(f"  {symbol:<8s} ({interval:>3s}): {count:>6,} velas -> {file_path}")
    print("=" * 60)
    print("Listo! Datos guardados en:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
