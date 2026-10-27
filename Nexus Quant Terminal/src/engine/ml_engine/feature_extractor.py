import numpy as np
import pandas as pd
from scipy.signal import fftconvolve
from engine.indicators import compute_wilders_rsi, compute_ema

def frac_diff_fixed(series: pd.Series, d: float = 0.4, threshold: float = 1e-5) -> pd.Series:
    """
    Fixed-Width Window Fractional Differentiation (FFD).
    López de Prado, Advances in Financial Machine Learning, Ch. 5.
    
    Preserva memoria de la serie original mientras logra estacionariedad.
    d=0: serie original (no estacionaria, máxima memoria)
    d=1: retornos (estacionaria, cero memoria)  
    d=0.3-0.5: sweet spot (estacionaria + memoria parcial)
    """
    vals = series.dropna().values
    n = len(vals)
    if n == 0:
        return pd.Series(dtype=float)
    
    # Calcular pesos del kernel fraccionario
    weights = [1.0]
    k = 1
    while k < n:
        w = -weights[-1] * (d - k + 1) / k
        if abs(w) < threshold:
            break
        weights.append(w)
        k += 1
    
    w_arr = np.array(weights, dtype=float)
    if len(w_arr) > n:
        w_arr = w_arr[:n]
    width = len(w_arr)
    
    # Aplicar convolución vectorizada vía FFT (50x speedup)
    output = np.full(n, np.nan)
    conv_res = fftconvolve(vals, w_arr, mode='valid')
    output[width - 1:] = np.real(conv_res)
    
    result = pd.Series(output, index=series.dropna().index)
    return result.reindex(series.index)

class BinaryFeatureExtractor:
    """
    Extractor de Características Microestructurales y de Régimen para Opciones Binarias en M1/M5.
    Calcula vectores de características sin sesgo de mirada al futuro (Zero Look-Ahead Bias).
    """
    @staticmethod
    def extract_features(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or len(df) < 50:
            return pd.DataFrame()

        features = pd.DataFrame(index=df.index)
        close = df['close']
        open_p = df['open']
        high = df['high']
        low = df['low']
        volume = df['volume'] if 'volume' in df.columns else pd.Series(1.0, index=df.index)

        candle_range = (high - low).replace(0, 1e-8)

        # 1. Micro-geometría de velas
        features['wick_upper_ratio'] = (high - np.maximum(open_p, close)) / candle_range
        features['wick_lower_ratio'] = (np.minimum(open_p, close) - low) / candle_range
        features['body_ratio'] = (close - open_p).abs() / candle_range
        
        # 2. Volatilidad y Rangos (ATR)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14 = tr.rolling(14).mean().replace(0, 1e-8)
        atr_20 = tr.rolling(20).mean().replace(0, 1e-8)
        
        features['natr'] = atr_14 / close.replace(0, 1e-8)
        
        # Score de Rechazo por mecha
        max_wick = np.maximum(features['wick_upper_ratio'], features['wick_lower_ratio'])
        features['rejection_score'] = (max_wick * candle_range) / atr_20

        # Kaufman Efficiency Ratio (ER) - 10 periodos
        change_10 = (close - close.shift(10)).abs()
        volatility_10 = (close - close.shift(1)).abs().rolling(10).sum().replace(0, 1e-8)
        features['kaufman_er'] = change_10 / volatility_10

        # Exponente de Hurst Aproximado (Rescaled Range R/S en 30 periodos)
        returns = close.pct_change()
        def calc_hurst(x):
            x_clean = x[~np.isnan(x)]
            if len(x_clean) < 30: return np.nan
            y = x_clean - np.mean(x_clean)
            z = np.concatenate(([0.0], np.cumsum(y)))
            s = np.std(x_clean, ddof=0)
            if s <= 1e-12: return np.nan
            return (np.max(z) - np.min(z)) / s
            
        rs_ratio = returns.rolling(30).apply(calc_hurst, raw=True).replace(0, 1e-8)
        features['hurst_exp'] = np.log(rs_ratio.clip(lower=1.0001)) / np.log(30)

        # Bollinger Band Width
        sma_20 = close.rolling(20).mean()
        std_20 = close.rolling(20).std(ddof=0)
        features['bb_width'] = (2.0 * 2.0 * std_20) / sma_20.replace(0, 1e-8)

        # 3. Deltas de Volumen
        vol_sma_20 = volume.rolling(20).mean().replace(0, 1e-8)
        features['rel_volume'] = volume / vol_sma_20
        if 'taker_buy_base' in df.columns:
            features['taker_buy_ratio'] = df['taker_buy_base'] / volume.replace(0, 1e-8)
        else:
            features['taker_buy_ratio'] = 0.5

        # 4. Indicadores Técnicos y Distancias Normalizadas a Medias y S/R
        rsi_14 = compute_wilders_rsi(close, 14)
        rsi_7 = compute_wilders_rsi(close, 7)
        features['rsi_14'] = rsi_14
        features['rsi_7'] = rsi_7
        features['delta_rsi'] = rsi_7 - rsi_14

        ema_200 = compute_ema(close, 200)
        features['dist_ema200_atr'] = (close - ema_200) / atr_14

        high_50 = high.rolling(50).max()
        low_50 = low.rolling(50).min()
        features['dist_high50_atr'] = (high_50 - close) / atr_14
        features['dist_low50_atr'] = (close - low_50) / atr_14

        # 5. Features Fraccionalmente Diferenciadas (preservan memoria)
        features['frac_close'] = frac_diff_fixed(close, d=0.4)
        features['frac_volume'] = frac_diff_fixed(volume, d=0.3)
        features['frac_high_low_range'] = frac_diff_fixed(candle_range, d=0.35)

        # Forward-fill primero (no inyectar 0 falsos), luego rellenar residuales
        return features.ffill().fillna(0.0)
