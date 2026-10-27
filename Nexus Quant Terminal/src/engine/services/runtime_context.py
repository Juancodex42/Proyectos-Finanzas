"""Contexto compartido de ejecución, caché LRU de series OHLCV y utilidades de infraestructura.
Centraliza la carga de datos, sanitización de entradas, localización del motor Rust y singletons.
Referencia de diseño: docs/ARQUITECTURA.md"""

from collections import OrderedDict
import json
import math
import os
import re
import threading
import urllib.request
from flask import Response
import numpy as np
import pandas as pd

from config import Config
from engine.optimizer import CapitalOptimizer
from engine.simulator import BinarySimulator
from engine.statistics import StatisticsEngine

# Cache LRU en memoria para DataFrames OHLCV
_data_cache = OrderedDict()
_cache_lock = threading.Lock()
MAX_DATA_CACHE_SIZE = 30

# Instancias compartidas del motor cuantitativo
simulator = BinarySimulator()
stats_engine = StatisticsEngine()
optimizer = CapitalOptimizer()

INTERVAL_ORDER = {
    '1d': 1,
    '4h': 2,
    '2h': 3,
    '1h': 4,
    '30m': 5,
    '15m': 6,
    '5m': 7,
    '3m': 8,
    '1m': 9,
}


def _get_project_root() -> str:
    """Retorna la ruta absoluta al directorio raíz del proyecto."""
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )


def get_data_dir():
    """Obtiene el directorio de datos respetando app.config['DATA_DIR'] si existe."""
    try:
        from flask import current_app
        if current_app and 'DATA_DIR' in current_app.config:
            return current_app.config['DATA_DIR']
    except Exception:
        pass
    try:
        import app as app_module
        if hasattr(app_module, 'app') and 'DATA_DIR' in app_module.app.config:
            return app_module.app.config['DATA_DIR']
    except Exception:
        pass
    return getattr(Config, 'DATA_DIR', 'data')


def resolve_csv_filepath(filename: str) -> str:
    """Resuelve la ruta de un archivo CSV buscando primero en get_data_dir() y luego en data/."""
    data_dir = get_data_dir()
    primary = os.path.join(data_dir, filename)
    if os.path.exists(primary):
        return primary
    # Fallback a data/ raíz sólo si estamos usando el DATA_DIR por defecto (data/raw)
    if os.path.normpath(data_dir) == os.path.normpath(getattr(Config, 'DATA_DIR', '')):
        fallback = os.path.join(_get_project_root(), 'data', filename)
        if os.path.exists(fallback):
            return fallback
    return primary


def extract_markov_params(stats: dict) -> tuple:
    """Extrae P(W|W) y P(W|L) del resultado de StatisticsEngine.analyze().
    Retorna (p_ww, p_wl) si hay datos suficientes (>= 20 trades decisivos), o (None, None)."""
    if not stats:
        return None, None
    markov = stats.get('markov', {})
    tm = markov.get('transition_matrix', [])
    if tm and len(tm) >= 2 and len(tm[0]) >= 1 and len(tm[1]) >= 1:
        p_ww = float(tm[0][0])  # P(Win | Win anterior)
        p_wl = float(tm[1][0])  # P(Win | Loss anterior)
        decisive = stats.get('basic', {}).get('decisive', stats.get('decisive', 0))
        if decisive >= 20 and p_ww > 0 and p_wl > 0:
            return p_ww, p_wl
    return None, None


def is_safe_symbol(symbol):
    """Valida que el símbolo contenga únicamente caracteres alfanuméricos, guion o guion bajo."""
    return bool(isinstance(symbol, str) and re.match(r'^[a-zA-Z0-9_-]+$', symbol))


def is_safe_interval(interval):
    """Valida que el intervalo temporal contenga únicamente caracteres alfanuméricos."""
    return bool(isinstance(interval, str) and re.match(r'^[a-zA-Z0-9]+$', interval))


def clean_json_data(data):
    """Reemplaza recursivamente NaN e Infinity por None (null en JSON) y convierte tipos NumPy."""
    if isinstance(data, dict):
        return {k: clean_json_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_json_data(v) for v in data]
    elif isinstance(data, (np.integer,)):
        return int(data)
    elif isinstance(data, (np.floating, float)):
        if math.isnan(data) or math.isinf(data):
            return None
        return float(data)
    elif isinstance(data, np.ndarray):
        return clean_json_data(data.tolist())
    elif isinstance(data, np.bool_):
        return bool(data)
    return data


def preserve_peaks_subsample(data_list, max_points=500, key='equity'):
    """Submuestreo que preserva los picos locales (máximos y mínimos) sin exceder max_points."""
    if not data_list or len(data_list) <= max_points:
        return data_list

    num_bins = max(1, max_points // 2)
    bin_size = len(data_list) / float(num_bins)
    sampled = []

    for i in range(num_bins):
        start_idx = int(i * bin_size)
        end_idx = int((i + 1) * bin_size) if i < num_bins - 1 else len(data_list)
        chunk = data_list[start_idx:end_idx]
        if not chunk:
            continue

        min_elem = min(chunk, key=lambda x: x.get(key, 0) if x.get(key) is not None else 0)
        max_elem = max(chunk, key=lambda x: x.get(key, 0) if x.get(key) is not None else 0)

        candidates = [min_elem, max_elem]
        candidates.sort(key=lambda x: chunk.index(x))

        for item in candidates:
            if not sampled or item != sampled[-1]:
                sampled.append(item)

    return sampled


def get_genetic_optimizer_path():
    """Localiza el ejecutable compilado en Rust para el optimizador genético."""
    src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root_dir = _get_project_root()
    candidates = [
        os.path.join(src_dir, "engine", "genetic_optimizer", "target", "release", "genetic_optimizer.exe"),
        os.path.join(src_dir, "engine", "genetic_optimizer", "target", "release", "genetic_optimizer"),
        os.path.join(root_dir, "engine", "genetic_optimizer", "target", "release", "genetic_optimizer.exe"),
        os.path.join(root_dir, "engine", "genetic_optimizer", "target", "release", "genetic_optimizer"),
    ]
    for exe_path in candidates:
        if os.path.exists(exe_path):
            return exe_path
    return None


def extract_json_from_output(text):
    """Extrae el payload JSON válido desde la salida estándar del optimizador genético."""
    if not text:
        raise ValueError("No valid JSON found in process output.")

    non_progress_lines = [
        line for line in text.splitlines()
        if not line.strip().startswith("PROGRESS:")
    ]
    clean_text = "\n".join(non_progress_lines).strip()

    if not clean_text:
        raise ValueError("No valid JSON found in process output.")

    try:
        return json.loads(clean_text)
    except Exception:
        pass

    first_brace = clean_text.find('{')
    last_brace = clean_text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = clean_text[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    first_bracket = clean_text.find('[')
    last_bracket = clean_text.rfind(']')
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        candidate = clean_text[first_bracket:last_bracket + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    raise ValueError(f"No valid JSON found in process output: {text[:200]}")


def sse_response(generator):
    """Construye una respuesta HTTP Server-Sent Events (SSE) sin caché."""
    response = Response(generator, mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response


def sort_intervals(interval_list):
    """Ordena una lista de temporalidades de mayor a menor duración."""
    return sorted(list(set(interval_list)), key=lambda x: INTERVAL_ORDER.get(x, 99))


def fetch_and_save_binance_klines(pair, interval):
    """Descarga velas históricas desde la API pública de Binance y las guarda en CSV."""
    if not is_safe_symbol(pair) or not is_safe_interval(interval):
        return None
    url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={interval}&limit=1000"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if isinstance(data, list) and len(data) > 0:
                rows = []
                for c in data:
                    open_time = int(c[0])
                    rows.append({
                        'open_time': open_time,
                        'open': float(c[1]),
                        'high': float(c[2]),
                        'low': float(c[3]),
                        'close': float(c[4]),
                        'volume': float(c[5]),
                        'close_time': int(c[6]),
                        'quote_asset_volume': float(c[7]),
                        'number_of_trades': int(c[8]),
                        'taker_buy_base_asset_volume': float(c[9]),
                        'taker_buy_quote_asset_volume': float(c[10]),
                        'ignore': 0,
                    })
                df = pd.DataFrame(rows)
                df.sort_values('open_time', inplace=True)
                df.reset_index(drop=True, inplace=True)
                df['time'] = df['open_time'] // 1000

                filename = f"{pair}_{interval}.csv"
                data_dir = get_data_dir()
                filepath = os.path.join(data_dir, filename)
                try:
                    os.makedirs(data_dir, exist_ok=True)
                    df.to_csv(filepath, index=False)
                except Exception as save_err:
                    print(f"Error saving {filename}: {save_err}")

                return df
    except Exception as e:
        print(f"Error fetching Binance klines for {pair} {interval}: {e}")
    return None


def load_csv_data(pair, interval):
    """Carga y almacena en caché LRU los datos CSV con validación de integridad OHLC."""
    if not is_safe_symbol(pair) or not is_safe_interval(interval):
        return None
    cache_key = f"{pair}_{interval}"

    with _cache_lock:
        if cache_key in _data_cache:
            _data_cache.move_to_end(cache_key)
            return _data_cache[cache_key].copy()

    filename = f"{pair}_{interval}.csv"
    filepath = resolve_csv_filepath(filename)
    if not os.path.exists(filepath):
        df = fetch_and_save_binance_klines(pair, interval)
    else:
        df = pd.read_csv(filepath)
        required_cols = ['open', 'high', 'low', 'close']
        if all(col in df.columns for col in required_cols):
            valid_mask = (
                (df['high'] >= df['low']) &
                (df['open'] <= df['high']) &
                (df['open'] >= df['low']) &
                (df['close'] <= df['high']) &
                (df['close'] >= df['low']) &
                (~df[required_cols].isna().any(axis=1))
            )
            df = df[valid_mask].copy()

        if 'open_time' in df.columns and not df.empty:
            df.sort_values('open_time', inplace=True)
            df.reset_index(drop=True, inplace=True)
            if df['open_time'].max() > 2**32:
                df['time'] = df['open_time'] // 1000
            else:
                df['time'] = df['open_time']

    if df is not None and not df.empty:
        with _cache_lock:
            if len(_data_cache) >= MAX_DATA_CACHE_SIZE:
                _data_cache.popitem(last=False)
            _data_cache[cache_key] = df
    return df.copy() if df is not None else None
