import os
import threading
from collections import OrderedDict
import numpy as np
import pandas as pd

_MAX_UNIVERSE_CACHE_SIZE = 100
_UNIVERSE_CACHE = OrderedDict()
_UNIVERSE_LOCK = threading.Lock()

ASSET_CLASSES = {
    'BTCUSDT': 'Crypto', 'ETHUSDT': 'Crypto', 'BNBUSDT': 'Crypto', 'ADAUSDT': 'Crypto',
    'DOGEUSDT': 'Crypto', 'DOTUSDT': 'Crypto', 'LINKUSDT': 'Crypto', 'LTCUSDT': 'Crypto',
    'SOLUSDT': 'Crypto', 'TRXUSDT': 'Crypto', 'XRPUSDT': 'Crypto',
    # Major Forex pairs
    'EURUSD': 'Forex', 'GBPUSD': 'Forex', 'USDJPY': 'Forex', 'USDCHF': 'Forex',
    'AUDUSD': 'Forex', 'USDCAD': 'Forex', 'NZDUSD': 'Forex',
    # Cross Forex pairs
    'GBPJPY': 'Forex', 'EURJPY': 'Forex', 'EURGBP': 'Forex', 'AUDNZD': 'Forex',
    'AUDJPY': 'Forex', 'GBPAUD': 'Forex', 'EURAUD': 'Forex', 'EURCAD': 'Forex',
    'GBPCAD': 'Forex', 'GBPCHF': 'Forex', 'EURCHF': 'Forex', 'CADCHF': 'Forex',
    'CADJPY': 'Forex', 'NZDJPY': 'Forex', 'CHFJPY': 'Forex',
    'WTI': 'Commodities', 'XAUUSD': 'Commodities', 'XAGUSD': 'Commodities',
    'NASDAQ': 'Indices', 'SP500': 'Indices', 'DOW': 'Indices', 'DAX': 'Indices'
}

class CorrelationEngine:
    @staticmethod
    def get_asset_class(symbol: str) -> str:
        symbol_clean = symbol.upper().replace('_1D', '').replace('.CSV', '')
        return ASSET_CLASSES.get(symbol_clean, 'Other')

    def __init__(self, data_dir=None):
        if data_dir is None:
            self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
        else:
            self.data_dir = data_dir

    def load_universe(self, symbols: list[str], update_incremental: bool = False) -> dict[str, pd.DataFrame]:
        """Carga los DataFrames de los símbolos solicitados usando caché en memoria e incremento inteligente."""
        universe = {}

        if update_incremental:
            try:
                from data.download_binance import update_symbol_incremental
                for symbol in symbols:
                    if symbol.endswith("USDT") or symbol.endswith("BTC"):
                        update_symbol_incremental(symbol, "1d")
            except Exception as e:
                print(f"[WARN] Error durante actualización incremental: {e}")

        for symbol in symbols:
            # Buscar archivo CSV
            file_name = f"{symbol}_1d.csv"
            file_path = os.path.join(self.data_dir, file_name)
            if not os.path.exists(file_path):
                # Intentar fallback a archivo sin _1d.csv
                fallback_path = os.path.join(self.data_dir, f"{symbol}.csv")
                if os.path.exists(fallback_path):
                    file_path = fallback_path

            if os.path.exists(file_path):
                try:
                    mtime = os.path.getmtime(file_path)
                    cache_key = (file_path, mtime)
                    
                    # --- AUDIT GUARANTEE: GESTIÓN DE MEMORIA Y CACHÉ LRU ---
                    # Cachea datasets en memoria indexados por (ruta, mtime).
                    # Si el archivo cambia en disco, el mtime invalida la entrada previa.
                    # El límite _MAX_UNIVERSE_CACHE_SIZE = 100 con desalojo LRU previene fugas de memoria (OOM).
                    with _UNIVERSE_LOCK:
                        if cache_key in _UNIVERSE_CACHE:
                            _UNIVERSE_CACHE.move_to_end(cache_key)
                            universe[symbol] = _UNIVERSE_CACHE[cache_key].copy()
                        else:
                            # Purgar entradas obsoletas de mtime para el mismo archivo (Evita Memory Leak)
                            old_keys = [k for k in _UNIVERSE_CACHE if isinstance(k, tuple) and k[0] == file_path]
                            for k in old_keys:
                                del _UNIVERSE_CACHE[k]
                            
                            df = pd.read_csv(file_path)
                            df.sort_values('open_time', inplace=True)
                            df.reset_index(drop=True, inplace=True)
                            while len(_UNIVERSE_CACHE) >= _MAX_UNIVERSE_CACHE_SIZE:
                                _UNIVERSE_CACHE.popitem(last=False)
                            _UNIVERSE_CACHE[cache_key] = df
                            universe[symbol] = df.copy()
                except Exception as e:
                    print(f"Error cargando {symbol}: {e}")
            else:
                print(f"Archivo no encontrado: {file_path}")
        return universe

    def compute_correlation_matrix(self, universe: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Calcula la matriz de retornos logarítmicos y su correlación de Pearson."""
        if not universe:
            return pd.DataFrame(), pd.DataFrame()

        # Alinear datos por tiempo preservando la resolución nativa de las velas
        close_prices = {}
        for symbol, df in universe.items():
            if 'open_time' in df.columns:
                df_temp = df.copy()
                if df_temp['open_time'].max() > 2**32:
                    df_temp['time_key'] = (df_temp['open_time'] // 1000).astype('int64')
                else:
                    df_temp['time_key'] = df_temp['open_time'].astype('int64')
                close_prices[symbol] = df_temp.set_index('time_key')['close']
            else:
                continue

        df_prices = pd.DataFrame(close_prices)
        df_prices.sort_index(inplace=True)
        
        # Calcular retornos individuales por activo
        pct_returns = df_prices.pct_change().replace([np.inf, -np.inf], np.nan)
        pct_returns = pct_returns.clip(lower=-0.9999)
        df_returns = np.log1p(pct_returns)
        df_returns.dropna(how='all', inplace=True)

        # Matriz de correlación de Pearson sobre períodos con al menos 10 observaciones coincidentes
        corr_matrix = df_returns.corr(min_periods=10).fillna(0.0)
        return corr_matrix, df_returns

    def select_uncorrelated_assets(self, corr_matrix: pd.DataFrame, threshold: float = 0.65, min_assets: int = 3) -> list[str]:
        """Selecciona los activos descorrelacionados usando un algoritmo voraz que filtra pares cuya correlación absoluta supera un umbral dinámico."""
        if corr_matrix.empty:
            return []

        # Intentar selección con el umbral primario
        def _greedy_select(curr_threshold):
            avg_corr = corr_matrix.abs().mean().sort_values()
            sorted_symbols = list(avg_corr.index)
            selected = []
            for symbol in sorted_symbols:
                if not selected:
                    selected.append(symbol)
                    continue
                is_uncorrelated = True
                for sel in selected:
                    corr_val = corr_matrix.loc[symbol, sel]
                    if abs(corr_val) >= curr_threshold:
                        is_uncorrelated = False
                        break
                if is_uncorrelated:
                    selected.append(symbol)
            return selected

        selected = _greedy_select(threshold)
        
        # Si la selección es menor que min_assets, relajar el umbral de forma progresiva
        curr_thresh = threshold
        while len(selected) < min_assets and curr_thresh < 0.95:
            curr_thresh += 0.05
            selected = _greedy_select(curr_thresh)
            
        if not selected:
            selected = list(corr_matrix.columns)

        return selected
