import pandas as pd
import numpy as np
from .base import BaseStrategy

class ClimaxReversalStrategy(BaseStrategy):
    name = "Multi-Candle Climax & Streak Reversal"
    description = "Agotamiento por rachas consecutivas (3-5 velas), mechas de rechazo extremas y reduccion de volumen/cuerpo en niveles clave."

    def get_params_schema(self) -> list[dict]:
        return [
            {"name": "streak_len", "type": "int", "default": 3, "min": 2, "max": 5, "description": "Consecutive Candles in Trend"},
            {"name": "wick_ratio", "type": "float", "default": 0.35, "min": 0.20, "max": 0.70, "description": "Min Climax Wick Ratio"},
            {"name": "vol_mult", "type": "float", "default": 1.3, "min": 0.8, "max": 3.0, "description": "Volume Expansion Spike"},
            {"name": "rsi_period", "type": "int", "default": 7, "min": 3, "max": 14, "description": "RSI Exhaustion Period"},
            {"name": "rsi_oversold", "type": "float", "default": 30.0, "min": 15.0, "max": 40.0, "description": "RSI Oversold Level"},
            {"name": "rsi_overbought", "type": "float", "default": 70.0, "min": 60.0, "max": 85.0, "description": "RSI Overbought Level"},
            {"name": "check_exhaustion", "type": "bool", "default": True, "description": "Require Decreasing Body Sizes"},
            {"name": "bb_period", "type": "int", "default": 20, "min": 10, "max": 50, "description": "Bollinger Filter Period"},
            {"name": "bb_std", "type": "float", "default": 2.0, "min": 1.5, "max": 3.5, "description": "Bollinger Filter Std Dev"}
        ]

    def prepare_data(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty or 'close' not in df.columns:
            return {}
        close = df['close']
        high = df['high'] if 'high' in df.columns else close
        low = df['low'] if 'low' in df.columns else close
        open_p = df['open'] if 'open' in df.columns else close
        has_vol = ('volume' in df.columns) and (df['volume'].fillna(0).sum() > 0)
        volume = df['volume'] if 'volume' in df.columns else pd.Series(0, index=df.index)

        # Geometry
        candle_range = high - low
        body = (close - open_p).abs()
        lower_wick = np.minimum(open_p, close) - low
        upper_wick = high - np.maximum(open_p, close)

        valid_range = candle_range > 0
        lower_wick_ratio = pd.Series(np.where(valid_range, lower_wick / candle_range.replace(0, 1e-8), 0.0), index=df.index)
        upper_wick_ratio = pd.Series(np.where(valid_range, upper_wick / candle_range.replace(0, 1e-8), 0.0), index=df.index)
        body_ratio = pd.Series(np.where(valid_range, body / candle_range.replace(0, 1e-8), 1.0), index=df.index)

        # Direction: 1 for bullish candle (close > open), -1 for bearish candle (close < open), 0 for flat
        direction = np.sign(close - open_p)

        from engine.indicators import compute_wilders_rsi
        rsi_7 = compute_wilders_rsi(close, min(len(close) - 1, 7)).fillna(50.0)
        rsi_14 = compute_wilders_rsi(close, min(len(close) - 1, 14)).fillna(50.0)
        vol_sma = volume.rolling(window=min(len(volume), 20), min_periods=1).mean() if has_vol else pd.Series(0, index=df.index)

        # Bollinger Bands
        bb_sma = close.rolling(window=min(len(close), 20), min_periods=1).mean()
        bb_std_dev = close.rolling(window=min(len(close), 20), min_periods=1).std(ddof=0).fillna(0.0)

        return {
            'close': close,
            'high': high,
            'low': low,
            'open': open_p,
            'volume': volume,
            'body': body,
            'candle_range': candle_range,
            'lower_wick_ratio': lower_wick_ratio,
            'upper_wick_ratio': upper_wick_ratio,
            'body_ratio': body_ratio,
            'direction': direction,
            'rsi_7': rsi_7,
            'rsi_14': rsi_14,
            'vol_sma': vol_sma,
            'bb_sma': bb_sma,
            'bb_std_dev': bb_std_dev,
            'has_vol': has_vol,
            'orig_indices': df.index
        }

    def generate_signals(self, df: pd.DataFrame = None, params: dict = None, precomputed: dict = None, **kwargs) -> pd.Series:
        if precomputed is None and isinstance(df, dict):
            precomputed = df
            df = None

        if df is not None and (df.empty or len(df) == 0 or 'close' not in df.columns):
            return pd.Series(dtype=object, index=df.index)

        if not isinstance(precomputed, dict) or 'direction' not in precomputed:
            if df is None:
                return pd.Series(dtype=object)
            precomputed = self.prepare_data(df)

        orig_indices = df.index if df is not None else precomputed.get('orig_indices', pd.Index([]))
        close = df['close'] if df is not None and 'close' in df else precomputed.get('close', pd.Series(dtype=float))
        high = df['high'] if df is not None and 'high' in df else precomputed.get('high', close)
        low = df['low'] if df is not None and 'low' in df else precomputed.get('low', close)
        open_p = df['open'] if df is not None and 'open' in df else precomputed.get('open', close)
        volume = df['volume'] if (df is not None and 'volume' in df.columns) else precomputed.get('volume', pd.Series(0, index=orig_indices))

        if len(close) == 0:
            return pd.Series(dtype=object, index=orig_indices)

        p = params or {}
        try:
            streak_len = max(1, int(float(p.get("streak_len", p.get("min_streak", 3)))))
        except (ValueError, TypeError):
            streak_len = 3
        try:
            wick_ratio = float(p.get("wick_ratio", p.get("min_wick_ratio", p.get("climax_wick_ratio", 0.35))))
        except (ValueError, TypeError):
            wick_ratio = 0.35
        try:
            vol_mult = float(p.get("vol_mult", p.get("volume_mult", 1.3)))
        except (ValueError, TypeError):
            vol_mult = 1.3
        try:
            rsi_period = max(1, int(float(p.get("rsi_period", 7))))
        except (ValueError, TypeError):
            rsi_period = 7
        try:
            rsi_extreme = float(p.get("rsi_extreme", 30.0))
        except (ValueError, TypeError):
            rsi_extreme = 30.0
        try:
            rsi_oversold = float(p.get("rsi_oversold", rsi_extreme))
        except (ValueError, TypeError):
            rsi_oversold = 30.0
        try:
            rsi_overbought = float(p.get("rsi_overbought", 100.0 - rsi_extreme if "rsi_extreme" in p else 70.0))
        except (ValueError, TypeError):
            rsi_overbought = 70.0
        check_exhaustion = bool(p.get("check_exhaustion", True))
        try:
            bb_period = max(1, int(float(p.get("bb_period", 20))))
        except (ValueError, TypeError):
            bb_period = 20
        try:
            bb_std = float(p.get("bb_std", 2.0))
        except (ValueError, TypeError):
            bb_std = 2.0

        direction = precomputed.get('direction', np.sign(close - open_p))
        body = precomputed.get('body', (close - open_p).abs())
        lower_wick_ratio = precomputed.get('lower_wick_ratio', pd.Series(0.0, index=orig_indices))
        upper_wick_ratio = precomputed.get('upper_wick_ratio', pd.Series(0.0, index=orig_indices))
        body_ratio = precomputed.get('body_ratio', (close - open_p).abs() / (high - low).replace(0, 1e-8))
        has_vol = precomputed.get('has_vol', False)

        # 1. Streak Detection
        bullish_streak = pd.Series(True, index=orig_indices)
        bearish_streak = pd.Series(True, index=orig_indices)
        for i in range(streak_len):
            bullish_streak = bullish_streak & (direction.shift(i) > 0)
            bearish_streak = bearish_streak & (direction.shift(i) < 0)

        # 2. Exhaustion check
        if check_exhaustion and streak_len >= 2:
            body_prev = body.shift(1)
            body_prev2 = body.shift(2) if streak_len >= 3 else body_prev
            exhaustion = (body <= body_prev * 1.2) | (body_ratio <= 0.40)
        else:
            exhaustion = pd.Series(True, index=orig_indices)

        # 3. RSI Exhaustion
        from engine.indicators import compute_wilders_rsi
        if rsi_period == 7 and 'rsi_7' in precomputed:
            rsi = precomputed['rsi_7']
        elif rsi_period == 14 and 'rsi_14' in precomputed:
            rsi = precomputed['rsi_14']
        else:
            rsi = compute_wilders_rsi(close, min(len(close) - 1, rsi_period)).fillna(50.0)

        # 4. Volume Spike
        if has_vol:
            eff_vol = min(len(volume), 20)
            vol_sma = precomputed.get('vol_sma', volume.rolling(window=eff_vol, min_periods=1).mean())
            vol_climax = (vol_sma == 0) | (volume >= (vol_sma * vol_mult))
        else:
            vol_climax = pd.Series(True, index=orig_indices)

        # 5. Bollinger Bands Envelope
        eff_bb = min(len(close), bb_period)
        if bb_period == 20 and 'bb_sma' in precomputed and 'bb_std_dev' in precomputed:
            bb_sma = precomputed['bb_sma']
            bb_std_dev = precomputed['bb_std_dev']
        else:
            bb_sma = close.rolling(window=eff_bb, min_periods=1).mean()
            bb_std_dev = close.rolling(window=eff_bb, min_periods=1).std(ddof=0).fillna(0.0)

        bb_lower = bb_sma - (bb_std * bb_std_dev)
        bb_upper = bb_sma + (bb_std * bb_std_dev)

        call_cond = (
            bearish_streak &
            (lower_wick_ratio >= wick_ratio) &
            (low <= bb_lower) &
            (rsi <= rsi_oversold) &
            exhaustion &
            vol_climax
        )

        put_cond = (
            bullish_streak &
            (upper_wick_ratio >= wick_ratio) &
            (high >= bb_upper) &
            (rsi >= rsi_overbought) &
            exhaustion &
            vol_climax
        )

        conflict = call_cond & put_cond
        call_cond = call_cond & (~conflict)
        put_cond = put_cond & (~conflict)

        signals = pd.Series(index=orig_indices, data=None, dtype=object)
        signals.loc[call_cond] = 'CALL'
        signals.loc[put_cond] = 'PUT'

        return signals
