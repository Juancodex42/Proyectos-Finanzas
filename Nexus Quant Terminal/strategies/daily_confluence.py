import pandas as pd
import numpy as np
from .base import BaseStrategy

class DailyConfluenceStrategy(BaseStrategy):
    name = "Confluencia Diaria Multi-Activo"
    description = "Estrategia de alta probabilidad basada en confluencia EMA Semanal/Diaria, RSI y filtro de mechas."

    def get_params_schema(self) -> list[dict]:
        return [
            {"name": "ema_weekly_period", "type": "int", "default": 20, "min": 5, "max": 100, "description": "Periodo EMA Semanal"},
            {"name": "ema_daily_period", "type": "int", "default": 20, "min": 5, "max": 100, "description": "Periodo EMA Diario"},
            {"name": "rsi_period", "type": "int", "default": 14, "min": 2, "max": 30, "description": "Periodo RSI"},
            {"name": "pullback_tolerance", "type": "float", "default": 0.012, "min": 0.001, "max": 0.05, "description": "Tolerancia Pullback"},
            {"name": "rsi_min_call", "type": "float", "default": 20.0, "min": 10.0, "max": 50.0, "description": "RSI Mínimo CALL"},
            {"name": "rsi_max_call", "type": "float", "default": 60.0, "min": 30.0, "max": 70.0, "description": "RSI Máximo CALL"},
            {"name": "rsi_min_put", "type": "float", "default": 40.0, "min": 30.0, "max": 70.0, "description": "RSI Mínimo PUT"},
            {"name": "rsi_max_put", "type": "float", "default": 80.0, "min": 50.0, "max": 90.0, "description": "RSI Máximo PUT"},
            {"name": "wick_rejection_ratio", "type": "float", "default": 0.25, "min": 0.1, "max": 0.8, "description": "Ratio Mínimo Rechazo Mecha"}
        ]

    def __init__(self, ema_weekly_period=20, ema_daily_period=20, rsi_period=14, volume_period=20, pullback_tolerance=0.012, rsi_min_call=20.0, rsi_max_call=60.0, rsi_min_put=40.0, rsi_max_put=80.0, wick_rejection_ratio=0.25, direction_filter='BOTH', exclude_weekends=True, allowed_days=None):
        self.ema_weekly_period = ema_weekly_period
        self.ema_daily_period = ema_daily_period
        self.rsi_period = rsi_period
        self.volume_period = volume_period
        self.pullback_tolerance = pullback_tolerance
        self.rsi_min_call = rsi_min_call
        self.rsi_max_call = rsi_max_call
        self.rsi_min_put = rsi_min_put
        self.rsi_max_put = rsi_max_put
        self.wick_rejection_ratio = wick_rejection_ratio
        self.direction_filter = direction_filter.upper() if isinstance(direction_filter, str) else 'BOTH'
        self.exclude_weekends = exclude_weekends
        self.allowed_days = allowed_days if allowed_days is not None else [0, 1, 2, 3, 4]

    def _resample_to_weekly(self, df_daily: pd.DataFrame) -> pd.DataFrame:
        df = df_daily.copy()
        if 'open_time' not in df.columns:
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df['open_time'] = df['datetime'].astype('int64') // 10**9
            elif isinstance(df.index, pd.DatetimeIndex):
                df['datetime'] = df.index
                df['open_time'] = df.index.astype('int64') // 10**9
            else:
                return pd.DataFrame()
        else:
            if df['open_time'].max() > 1e11:
                df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
            else:
                df['datetime'] = pd.to_datetime(df['open_time'], unit='s')
        
        df.set_index('datetime', inplace=True)
        agg_dict = {
            'open_time': 'first',
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }
        if 'volume' in df.columns:
            agg_dict['volume'] = 'sum'
            
        df_weekly = df.resample('W-MON').agg(agg_dict)
        df_weekly.dropna(subset=['close'], inplace=True)
        df_weekly.reset_index(inplace=True)
        return df_weekly

    def prepare_data(self, df_daily: pd.DataFrame = None, df: pd.DataFrame = None) -> dict:
        if df_daily is None:
            df_daily = df
        if df_daily is None or df_daily.empty or 'close' not in df_daily.columns:
            return {
                'df_merged': pd.DataFrame(),
                'df_weekly': pd.DataFrame(),
                'records': [],
                'orig_indices': df_daily.index if df_daily is not None else pd.Index([]),
                'has_vol': False
            }
            
        df = df_daily.copy()
        df['_orig_idx_'] = df_daily.index
        
        if 'open_time' not in df.columns:
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df['open_time'] = df['datetime'].astype('int64') // 10**9
            elif isinstance(df.index, pd.DatetimeIndex):
                df['datetime'] = df.index
                df['open_time'] = df.index.astype('int64') // 10**9
            else:
                df['open_time'] = np.arange(len(df)) * 86400
                df['datetime'] = pd.to_datetime(df['open_time'], unit='s')
        else:
            if df['open_time'].max() > 1e11:
                df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
            else:
                df['datetime'] = pd.to_datetime(df['open_time'], unit='s')
            
        close = df['close']
        has_vol = ('volume' in df.columns) and (df['volume'].fillna(0).sum() > 0)
        volume = df['volume'] if 'volume' in df.columns else pd.Series(0, index=df.index)
        
        from engine.indicators import compute_ema, compute_wilders_rsi
        df['ema_daily'] = compute_ema(close, min(len(close), self.ema_daily_period)).ffill().fillna(close)
        df['rsi_daily'] = compute_wilders_rsi(close, min(len(close) - 1, self.rsi_period)).fillna(50.0)
        df['rsi_fast'] = compute_wilders_rsi(close, min(len(close) - 1, 3)).fillna(50.0)
        df['vol_sma'] = volume.rolling(window=min(len(volume), self.volume_period), min_periods=1).mean() if has_vol else pd.Series(0, index=df.index)
        
        df_weekly = self._resample_to_weekly(df_daily)
        if not df_weekly.empty and len(df_weekly) >= 1:
            eff_period = min(len(df_weekly), self.ema_weekly_period)
            df_weekly['ema_weekly'] = compute_ema(df_weekly['close'], eff_period)
            if df_weekly['ema_weekly'].isna().all():
                df_weekly['ema_weekly'] = df_weekly['close'].ewm(span=max(2, eff_period), min_periods=1).mean()
            else:
                df_weekly['ema_weekly'] = df_weekly['ema_weekly'].ffill().fillna(df_weekly['close'])
            df_weekly['ema_weekly_dir'] = df_weekly['ema_weekly'].diff().fillna(0.0)
            
            # --- GARANTÍA CAUSAL MULTI-TIMEFRAME (ZERO LOOK-AHEAD) ---
            is_ms = df_weekly['open_time'].max() > 1e11
            offset = 7 * 24 * 60 * 60 * 1000 if is_ms else 7 * 24 * 60 * 60
            df_weekly['completion_time'] = (df_weekly['open_time'] + offset).astype('int64')
            df['open_time'] = df['open_time'].astype('int64')
            
            df.sort_values('open_time', inplace=True)
            df_weekly.sort_values('completion_time', inplace=True)
            
            df_merged = pd.merge_asof(
                df,
                df_weekly[['completion_time', 'ema_weekly', 'ema_weekly_dir', 'close']],
                left_on='open_time',
                right_on='completion_time',
                direction='backward',
                suffixes=('', '_weekly')
            )
            df_merged.sort_values('_orig_idx_', inplace=True)
        else:
            df_merged = df.copy()
            df_merged['ema_weekly'] = np.nan
            df_merged['ema_weekly_dir'] = np.nan
            df_merged['close_weekly'] = np.nan

        high = df_merged['high'] if 'high' in df_merged.columns else df_merged['close']
        low = df_merged['low'] if 'low' in df_merged.columns else df_merged['close']
        tr1 = high - low
        tr2 = (high - df_merged['close'].shift(1)).abs()
        tr3 = (low - df_merged['close'].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df_merged['atr_14'] = tr.rolling(window=min(14, len(df_merged)), min_periods=1).mean().ffill().fillna(0.0)
        
        records = df_merged.to_dict('records')
        return {
            'df_merged': df_merged,
            'df_weekly': df_weekly,
            'records': records,
            'orig_indices': df_daily.index,
            'has_vol': has_vol
        }

    def generate_signals(self, df_daily: pd.DataFrame = None, params: dict = None, precomputed: dict = None, as_list: bool = False, df: pd.DataFrame = None, **kwargs) -> pd.Series | list[dict]:
        if df_daily is None:
            df_daily = df if df is not None else kwargs.get('df')

        # Handle positional or kwargs precomputed passing
        if precomputed is None and isinstance(df_daily, dict):
            precomputed = df_daily
            df_daily = None

        if df_daily is not None and (df_daily.empty or len(df_daily) == 0 or 'close' not in df_daily.columns):
            return [] if as_list else pd.Series(dtype=object, index=df_daily.index)

        if not isinstance(precomputed, dict) or 'df_merged' not in precomputed or 'orig_indices' not in precomputed:
            if df_daily is None:
                return [] if as_list else pd.Series(dtype=object)
            precomputed = self.prepare_data(df_daily)
            
        df_m = precomputed.get('df_merged', pd.DataFrame())
        orig_indices = precomputed.get('orig_indices', df_m.index if not df_m.empty else pd.Index([]))
        has_vol = precomputed.get('has_vol', True)
        
        if df_m is None or df_m.empty or len(df_m) == 0:
            return [] if as_list else pd.Series(dtype=object, index=orig_indices)

        p = params or {}
        try:
            ema_daily_period = max(1, int(float(p.get("ema_daily_period", self.ema_daily_period))))
        except (ValueError, TypeError):
            ema_daily_period = self.ema_daily_period
        try:
            ema_weekly_period = max(1, int(float(p.get("ema_weekly_period", self.ema_weekly_period))))
        except (ValueError, TypeError):
            ema_weekly_period = self.ema_weekly_period
        try:
            rsi_period = max(1, int(float(p.get("rsi_period", self.rsi_period))))
        except (ValueError, TypeError):
            rsi_period = self.rsi_period
        try:
            pullback_tol_param = float(p.get("pullback_tolerance", self.pullback_tolerance))
        except (ValueError, TypeError):
            pullback_tol_param = self.pullback_tolerance
        try:
            rsi_min_call = float(p.get("rsi_min_call", self.rsi_min_call))
        except (ValueError, TypeError):
            rsi_min_call = self.rsi_min_call
        try:
            rsi_max_call = float(p.get("rsi_max_call", self.rsi_max_call))
        except (ValueError, TypeError):
            rsi_max_call = self.rsi_max_call
        try:
            rsi_min_put = float(p.get("rsi_min_put", self.rsi_min_put))
        except (ValueError, TypeError):
            rsi_min_put = self.rsi_min_put
        try:
            rsi_max_put = float(p.get("rsi_max_put", self.rsi_max_put))
        except (ValueError, TypeError):
            rsi_max_put = self.rsi_max_put
        try:
            wick_rejection_min = float(p.get("wick_rejection_ratio", self.wick_rejection_ratio))
        except (ValueError, TypeError):
            wick_rejection_min = self.wick_rejection_ratio
        try:
            put_wick_min = float(p.get("put_wick_rejection_ratio", wick_rejection_min))
        except (ValueError, TypeError):
            put_wick_min = wick_rejection_min
        try:
            regime_min_move = float(p.get("regime_min_move", 0.002))
        except (ValueError, TypeError):
            regime_min_move = 0.002
        direction_filter = p.get("direction_filter", self.direction_filter)
        if isinstance(direction_filter, str):
            direction_filter = direction_filter.upper()

        warmup_period = max(10, min(30, len(df_m) // 4)) if len(df_m) < 180 else 30
        warmup_mask = np.arange(len(df_m)) >= warmup_period
        
        close = df_m['close']
        open_p = df_m['open']
        high = df_m['high']
        low = df_m['low']

        from engine.indicators import compute_ema, compute_wilders_rsi
        if ema_daily_period == self.ema_daily_period and 'ema_daily' in df_m:
            ema_d = df_m['ema_daily']
        else:
            ema_d = compute_ema(close, min(len(close), ema_daily_period)).ffill().fillna(close)

        if rsi_period == self.rsi_period and 'rsi_daily' in df_m:
            rsi_d = df_m['rsi_daily']
        else:
            rsi_d = compute_wilders_rsi(close, min(len(close) - 1, rsi_period)).fillna(50.0)

        rsi_f = df_m.get('rsi_fast', pd.Series(50.0, index=df_m.index))
        
        # Robustly fill weekly fields on-the-fly when series is short/intraday
        if ema_weekly_period == self.ema_weekly_period and 'ema_weekly' in df_m and df_m['ema_weekly'].notna().any():
            ema_w = df_m.get('ema_weekly', ema_d).ffill().fillna(ema_d)
            ema_w_dir = df_m.get('ema_weekly_dir', pd.Series(0.0, index=df_m.index)).ffill().fillna(0.0)
        elif precomputed is not None and 'df_weekly' in precomputed and not precomputed['df_weekly'].empty and 'completion_time' in precomputed['df_weekly'].columns:
            df_w = precomputed['df_weekly'].copy()
            eff_period = min(len(df_w), ema_weekly_period)
            df_w['ema_weekly_custom'] = compute_ema(df_w['close'], eff_period).ffill().fillna(df_w['close'])
            df_w['ema_weekly_dir_custom'] = df_w['ema_weekly_custom'].diff().fillna(0.0)
            
            # Merge causal backward
            m_temp = pd.merge_asof(
                df_m[['open_time']],
                df_w[['completion_time', 'ema_weekly_custom', 'ema_weekly_dir_custom']],
                left_on='open_time',
                right_on='completion_time',
                direction='backward'
            )
            ema_w = m_temp['ema_weekly_custom'].ffill().fillna(ema_d)
            ema_w_dir = m_temp['ema_weekly_dir_custom'].ffill().fillna(0.0)
        else:
            # Fallback causal: aproximar período semanal en velas diarias (x7)
            close_w_src = df_m.get('close_weekly', close).ffill().fillna(close)
            ema_w = compute_ema(close_w_src, min(len(close_w_src), ema_weekly_period * 7)).ffill().fillna(ema_d)
            ema_w_dir = ema_w.diff().fillna(0.0)

        close_w = df_m.get('close_weekly', close).ffill().fillna(close)
        
        # 1. Weekly Trend
        weekly_bull = (close_w >= ema_w) & (ema_w_dir >= 0)
        weekly_bear = (close_w <= ema_w) & (ema_w_dir <= 0)
        
        # 2. Regime Move
        if regime_min_move > 0:
            shift_bars = min(28, max(1, len(df_m) // 4))
            ema_prev = ema_w.shift(shift_bars).ffill().fillna(ema_w)
            regime_move = (ema_w - ema_prev).abs() / np.maximum(ema_prev, 1e-8)
            regime_valid = (ema_prev > 0) & ((regime_move >= regime_min_move) | (regime_move.isna()))
            regime_valid = regime_valid.fillna(True)
        else:
            regime_valid = pd.Series(True, index=df_m.index)
            
        # 3. Pullback Tolerance
        pullback_call = (low <= ema_d * (1 + pullback_tol_param)) & (low >= ema_d * (1 - pullback_tol_param))
        pullback_put = (high >= ema_d * (1 - pullback_tol_param)) & (high <= ema_d * (1 + pullback_tol_param))
        
        # 4. Dual RSI Filters
        rsi_call = (rsi_d >= rsi_min_call) & (rsi_d <= rsi_max_call)
        rsi_put = (rsi_d >= rsi_min_put) & (rsi_d <= rsi_max_put)
        if rsi_f.notna().any():
            rsi_call = rsi_call & (rsi_f <= 55.0)
            rsi_put = rsi_put & (rsi_f >= 45.0)
            
        # 5. Volume Filter (Safe 0-Volume Fallback)
        if has_vol and 'vol_sma' in df_m.columns:
            vol_sma = df_m['vol_sma']
            vol_low = (vol_sma == 0) | (df_m['volume'] <= vol_sma * 1.2)
        else:
            vol_low = pd.Series(True, index=df_m.index)
            
        # 6. Candle Wicks & Geometry
        candle_range = high - low
        lower_wick = np.minimum(open_p, close) - low
        upper_wick = high - np.maximum(open_p, close)
        body_ratio = (close - open_p).abs() / np.maximum(candle_range, 1e-8)
        
        valid_range = candle_range > 0
        wick_rejection_call = np.where(valid_range, (lower_wick / candle_range) >= wick_rejection_min, True)
        wick_rejection_put = np.where(valid_range, (upper_wick / candle_range) >= put_wick_min, True)
        body_ok = np.where(valid_range, body_ratio <= 0.65, True)
        dir_close_call = np.where(valid_range, close >= open_p, True)
        dir_close_put = np.where(valid_range, close <= open_p, True)
        
        # 7. Day of Week / Weekend Exclusion
        open_t = df_m['open_time']
        is_ms = open_t.max() > 1e11
        sig_timestamps = np.where(is_ms, open_t // 1000, open_t)
        dt_series = pd.to_datetime(sig_timestamps, unit='s', utc=True)
        day_of_week = pd.Series(dt_series, index=df_m.index).dt.tz_convert('America/New_York').dt.weekday
        
        if self.allowed_days is not None:
            day_valid = day_of_week.isin(self.allowed_days)
        elif self.exclude_weekends:
            day_valid = day_of_week < 5
        else:
            day_valid = pd.Series(True, index=df_m.index)
            
        # Combine Conditions
        is_call = warmup_mask & weekly_bull & regime_valid & pullback_call & rsi_call & vol_low & wick_rejection_call & body_ok & dir_close_call & day_valid
        is_put = warmup_mask & weekly_bear & regime_valid & pullback_put & rsi_put & vol_low & wick_rejection_put & body_ok & dir_close_put & day_valid
        
        if direction_filter == 'CALL':
            is_put = pd.Series(False, index=df_m.index)
        elif direction_filter == 'PUT':
            is_call = pd.Series(False, index=df_m.index)
            
        # Anti-streak edge trigger
        is_call = is_call & (~is_call.shift(1).fillna(False))
        is_put = is_put & (~is_put.shift(1).fillna(False))
        
        conflict = is_call & is_put
        is_call = is_call & (~conflict)
        is_put = is_put & (~conflict)
        
        series_signals = pd.Series(index=orig_indices, dtype=object)
        
        call_orig_indices = df_m.loc[is_call, '_orig_idx_']
        put_orig_indices = df_m.loc[is_put, '_orig_idx_']
        
        series_signals.loc[call_orig_indices] = 'CALL'
        series_signals.loc[put_orig_indices] = 'PUT'
        
        if as_list:
            signals_list = []
            active_rows = df_m[is_call | is_put]
            for _, row in active_rows.iterrows():
                sig_dir = 'CALL' if row['_orig_idx_'] in call_orig_indices.values else 'PUT'
                sig_t = int(row['open_time'] // 1000) if row['open_time'] > 1e11 else int(row['open_time'])
                signals_list.append({
                    'time': sig_t,
                    'direction': sig_dir,
                    'price': float(row['close']),
                    'rsi': float(row['rsi_daily']) if not pd.isna(row['rsi_daily']) else 50.0,
                    'ema_daily': float(row['ema_daily']) if not pd.isna(row['ema_daily']) else 0.0,
                    'ema_weekly': float(row['ema_weekly']) if not pd.isna(row.get('ema_weekly')) else 0.0
                })
            return signals_list
            
        return series_signals

    def generate_signals_list(self, df_daily: pd.DataFrame = None, params: dict = None, precomputed: dict = None, df: pd.DataFrame = None) -> list[dict]:
        return self.generate_signals(df_daily=df_daily, params=params, precomputed=precomputed, as_list=True, df=df)
