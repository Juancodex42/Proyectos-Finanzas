import pandas as pd
import numpy as np
from .base import BaseStrategy
from engine.indicators import compute_ema, compute_wilders_rsi
from sklearn.ensemble import HistGradientBoostingClassifier

class VolatilitySqueezeMLStrategy(BaseStrategy):
    name = "Volatility Squeeze MTF ML (Walk-Forward Calibrado)"
    description = "Meta-filtro ML con Walk-Forward expandible, features de microestructura y umbral de probabilidad calibrado."

    def get_params_schema(self) -> list[dict]:
        return [
            {"name": "bb_pctl_thresh", "type": "float", "default": 0.35, "min": 0.10, "max": 0.50, "step": 0.05, "description": "Percentil Maximo de Ancho BB"},
            {"name": "prob_thresh", "type": "float", "default": 0.53, "min": 0.50, "max": 0.70, "step": 0.01, "description": "Umbral de Probabilidad ML P(WIN)"},
            {"name": "use_mtf", "type": "bool", "default": True, "description": "Activar Filtro de Tendencia Macro MTF"},
        ]

    def prepare_data(self, df: pd.DataFrame) -> dict:
        if df is None or len(df) < 20 or 'close' not in df.columns:
            return {}
            
        close = df['close']
        open_p = df['open'] if 'open' in df.columns else close
        high = df['high'] if 'high' in df.columns else close
        low = df['low'] if 'low' in df.columns else close
        volume = df['volume'] if 'volume' in df.columns else pd.Series(1.0, index=df.index)
        
        candle_range = (high - low).replace(0, 1e-8)
        
        # Candle geometry
        wick_upper = (high - np.maximum(open_p, close)) / candle_range
        wick_lower = (np.minimum(open_p, close) - low) / candle_range
        body_ratio = (close - open_p).abs() / candle_range
        
        # True Range & ATR
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14 = tr.rolling(min(14, len(df)), min_periods=1).mean().ffill().replace(0, 1e-8)
        
        # Bollinger Bands
        bb_sma20 = close.rolling(min(20, len(df)), min_periods=1).mean()
        bb_std20 = close.rolling(min(20, len(df)), min_periods=1).std(ddof=0).fillna(0.0)
        bb_upper = bb_sma20 + 2.0 * bb_std20
        bb_lower = bb_sma20 - 2.0 * bb_std20
        bb_w = (4.0 * bb_std20) / bb_sma20.replace(0, 1e-8)
        
        w_min = bb_w.rolling(min(100, len(df)), min_periods=1).min().ffill()
        w_max = bb_w.rolling(min(100, len(df)), min_periods=1).max().ffill()
        bb_pctl = (bb_w - w_min) / (w_max - w_min + 1e-8)
        
        # BB Position (where in the band 0=lower, 1=upper)
        bb_pos = (close - bb_lower) / (bb_upper - bb_lower + 1e-8)
        
        # EMAs MTF
        ema_20 = compute_ema(close, min(len(close), 20)).ffill().fillna(close)
        ema_50 = compute_ema(close, min(len(close), 50)).ffill().fillna(close)
        if len(close) >= 200:
            ema_200 = compute_ema(close, 200).ffill().fillna(close)
        else:
            ema_200 = close.ewm(span=min(len(close), 200), min_periods=1).mean().ffill().fillna(close)
        
        # Momentum & Oscillators
        rsi_7 = compute_wilders_rsi(close, min(len(close) - 1, 7)).fillna(50.0)
        rsi_14 = compute_wilders_rsi(close, min(len(close) - 1, 14)).fillna(50.0)
        
        # Volume
        vol_sma20 = volume.rolling(min(20, len(volume)), min_periods=1).mean().ffill().replace(0, 1e-8)
        rel_vol = volume / vol_sma20
        vol_delta = (volume / volume.shift(1).replace(0, 1e-8)).fillna(1.0)
        
        # Returns at multiple lags
        ret_1 = close.pct_change(1).fillna(0)
        ret_3 = close.pct_change(min(3, len(df) - 1)).fillna(0)
        ret_5 = close.pct_change(min(5, len(df) - 1)).fillna(0)
        ret_10 = close.pct_change(min(10, len(df) - 1)).fillna(0)
        
        # ATR change (volatility expansion/contraction)
        shift_atr = min(5, len(df) - 1)
        atr_change = ((atr_14 / atr_14.shift(shift_atr).replace(0, 1e-8)) - 1.0).fillna(0.0)
        
        # EMA slope (trend strength)
        ema_slope = ((ema_20 - ema_20.shift(shift_atr)) / atr_14).fillna(0.0)
        
        # 19 features total (all vectorized)
        features = pd.DataFrame({
            'wick_upper': wick_upper,
            'wick_lower': wick_lower,
            'body_ratio': body_ratio,
            'natr_14': atr_14 / close.replace(0, 1e-8),
            'bb_width': bb_w,
            'bb_pctl': bb_pctl.fillna(0.5),
            'bb_pos': bb_pos.fillna(0.5),
            'dist_ema20': (close - ema_20) / atr_14,
            'dist_ema50': (close - ema_50) / atr_14,
            'dist_ema200': (close - ema_200) / atr_14,
            'rsi_7': rsi_7,
            'rsi_14': rsi_14,
            'rel_vol': rel_vol,
            'vol_delta': vol_delta,
            'ret_1': ret_1,
            'ret_3': ret_3,
            'ret_5': ret_5,
            'ret_10': ret_10,
            'atr_change': atr_change,
        }, index=df.index).fillna(0.0)
        
        # Clip extremes using backward rolling window statistics to prevent lookahead bias
        min_p = min(20, max(5, len(df) // 5))
        roll_window = min(200, len(df))
        for col in features.columns:
            q01 = features[col].rolling(roll_window, min_periods=min_p).quantile(0.01).fillna(features[col])
            q99 = features[col].rolling(roll_window, min_periods=min_p).quantile(0.99).fillna(features[col])
            features[col] = features[col].clip(q01, q99)
        
        return {
            'close': close,
            'open': open_p,
            'high': high,
            'low': low,
            'volume': volume,
            'bb_upper': bb_upper,
            'bb_lower': bb_lower,
            'bb_pctl': bb_pctl,
            'ema_20': ema_20,
            'ema_50': ema_50,
            'ema_200': ema_200,
            'rsi_7': rsi_7,
            'atr_14': atr_14,
            'features': features,
            'orig_indices': df.index
        }

    def generate_signals(self, df: pd.DataFrame = None, params: dict = None, precomputed: dict = None, **kwargs) -> pd.Series:
        p = params or {}
        try:
            bb_pctl_thresh = float(p.get("bb_pctl_thresh", 0.35))
        except (ValueError, TypeError):
            bb_pctl_thresh = 0.35
        try:
            prob_thresh = float(p.get("prob_thresh", 0.53))
        except (ValueError, TypeError):
            prob_thresh = 0.53
        use_mtf = bool(p.get("use_mtf", True))
        try:
            expiry = max(1, int(float(p.get("expiry_candles", 1))))
        except (ValueError, TypeError):
            expiry = 1
        
        if precomputed is None or not isinstance(precomputed, dict) or 'features' not in precomputed:
            if df is None or len(df) < 20 or 'close' not in df.columns:
                return pd.Series(dtype=object, index=df.index if df is not None else None)
            precomputed = self.prepare_data(df)
            if not precomputed or 'features' not in precomputed:
                return pd.Series(dtype=object, index=df.index)
            
        orig_indices = df.index if df is not None else precomputed.get('orig_indices', pd.Index([]))
        features = precomputed['features']
        close = df['close'] if df is not None and 'close' in df else precomputed.get('close', pd.Series(dtype=float))
        open_p = df['open'] if df is not None and 'open' in df else precomputed.get('open', close)
        high = df['high'] if df is not None and 'high' in df else precomputed.get('high', close)
        low = df['low'] if df is not None and 'low' in df else precomputed.get('low', close)
        ema_20 = precomputed.get('ema_20', close)
        ema_50 = precomputed.get('ema_50', close)
        ema_200 = precomputed.get('ema_200', close)
        rsi_7 = precomputed.get('rsi_7', pd.Series(50.0, index=close.index))
        atr_14 = precomputed.get('atr_14', pd.Series(1.0, index=close.index))
        bb_pctl = precomputed.get('bb_pctl', pd.Series(0.0, index=close.index))
        
        if len(close) == 0:
            return pd.Series(dtype=object, index=orig_indices)
        
        candle_range = (high - low).replace(0, 1e-8)
        lower_wick = (np.minimum(open_p, close) - low) / candle_range
        upper_wick = (high - np.maximum(open_p, close)) / candle_range
        dist_ema20 = (close - ema_20).abs() / atr_14
        
        mtf_bull = (ema_20 >= ema_50) if use_mtf else pd.Series(True, index=close.index)
        mtf_bear = (ema_20 <= ema_50) if use_mtf else pd.Series(True, index=close.index)
        
        signals = pd.Series(index=orig_indices, data=None, dtype=object)
        
        # Base signals for ML to evaluate & filter (requiriendo compresión real de volatilidad)
        squeeze_cond = (bb_pctl <= bb_pctl_thresh) if bb_pctl is not None else pd.Series(True, index=close.index)
        call_cond = squeeze_cond & mtf_bull & (dist_ema20 <= 2.5) & (close >= open_p) & (lower_wick >= 0.15) & (rsi_7 >= 25) & (rsi_7 <= 75)
        put_cond = squeeze_cond & mtf_bear & (dist_ema20 <= 2.5) & (close <= open_p) & (upper_wick >= 0.15) & (rsi_7 <= 75) & (rsi_7 >= 25)
        
        signals.loc[call_cond] = 'CALL'
        signals.loc[put_cond] = 'PUT'
        
        # =====================================================================
        # EXPANDING WALK-FORWARD ML META-FILTER
        # =====================================================================
        active_indices = signals.dropna().index
        if len(active_indices) < 20:
            return signals
        
        n_active = len(active_indices)
        
        if n_active < 30:
            return signals

        # 2. Walk-Forward Expanding ML Meta-Filter (Strictly Causal - Zero Look-Ahead)
        n_df = len(df) if df is not None else len(orig_indices)
        locs = np.array([orig_indices.get_loc(idx) for idx in active_indices])
        valid_mask = (locs + expiry) < n_df
        
        entry_prices = np.full(n_active, np.nan)
        exit_prices = np.full(n_active, np.nan)
        locs_valid = locs[valid_mask]
        open_vals = open_p.values
        close_vals = close.values
        
        entry_prices[valid_mask] = open_vals[np.minimum(locs_valid + 1, n_df - 1)]
        exit_prices[valid_mask] = close_vals[np.minimum(locs_valid + expiry, n_df - 1)]
        
        dirs = signals.loc[active_indices].values
        diffs = exit_prices - entry_prices
        y_all = np.full(n_active, np.nan)
        y_all[valid_mask] = np.where(
            dirs[valid_mask] == 'CALL',
            diffs[valid_mask] > 1e-8,
            diffs[valid_mask] < -1e-8
        ).astype(float)
        
        X_all = features.loc[active_indices].values
        X_all = np.nan_to_num(X_all, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Expanding walk-forward: divide into K chronological folds
        min_train_size = min(250, max(50, n_active // 3))
        fold_size = max(20, n_active // 8)
        n_folds = max(2, (n_active - min_train_size) // fold_size + 1)
        
        oos_probs = np.full(n_active, np.nan)
        
        for fold_idx in range(1, n_folds + 1):
            train_end = min(min_train_size + (fold_idx - 1) * fold_size, n_active)
            test_start = train_end
            test_end = min(train_end + fold_size, n_active)
            
            if test_start >= n_active:
                break
            
            train_indices = np.arange(0, train_end)
            train_valid = valid_mask[train_indices] & ~np.isnan(y_all[train_indices])
            
            if train_valid.sum() < 30:
                continue
            
            X_train = X_all[train_indices[train_valid]]
            y_train = y_all[train_indices[train_valid]].astype(int)
            
            clf = HistGradientBoostingClassifier(
                max_iter=100,
                max_depth=3,
                learning_rate=0.03,
                min_samples_leaf=10,
                l2_regularization=3.0,
                max_bins=64,
                random_state=42
            )
            clf.fit(X_train, y_train)
            
            test_indices = np.arange(test_start, test_end)
            if len(test_indices) == 0:
                continue
            X_test = X_all[test_indices]
            probs = clf.predict_proba(X_test)[:, 1]
            oos_probs[test_indices] = probs
        
        # --- AUDIT GUARANTEE: CERO DATA LEAKAGE EN WARMUP FOLD ---
        # NUNCA usar el último modelo entrenado (last_clf) para puntuar el período inicial no puntuado (unscored).
        # Hacerlo equivaldría a usar un clasificador que ya vio el futuro para operar el pasado.
        # Las señales no puntuadas solo se filtran de forma neutral o se dejan pasar con threshold base.
        filtered = pd.Series(index=orig_indices, data=None, dtype=object)
        for i, idx in enumerate(active_indices):
            prob = oos_probs[i]
            if np.isnan(prob):
                if prob_thresh <= 0.50:
                    filtered.loc[idx] = signals.loc[idx]
            elif prob >= prob_thresh:
                filtered.loc[idx] = signals.loc[idx]
        
        return filtered
