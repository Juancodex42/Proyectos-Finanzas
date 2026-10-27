import numpy as np
import pandas as pd

class MarketRegimeGating:
    """
    Motor de Gating de Régimen de Mercado Determinista para Opciones Binarias.
    Filtra la idoneidad de las estrategias evitando operaciones contra el contexto predominante.
    """
    @staticmethod
    def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high = df['high']
        low = df['low']
        close = df['close']

        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.ewm(span=period, adjust=False).mean()
        plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(span=period, adjust=False).mean() / atr.replace(0, 1e-8))
        minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(span=period, adjust=False).mean() / atr.replace(0, 1e-8))

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-8)
        adx = dx.ewm(span=period, adjust=False).mean()
        return adx.fillna(0.0)

    @classmethod
    def filter_signals_by_regime(cls, df: pd.DataFrame, signals: pd.Series, strategy_type: str = 'MEAN_REVERSION') -> pd.Series:
        """
        strategy_type: 'MEAN_REVERSION' (BollingerBounce, RsiExtremes) o 'TREND_FOLLOWING' (EmaCross, MtfTcve)
        """
        if df is None or len(df) < 50 or signals is None or len(signals) == 0:
            return signals

        close = df['close']
        high = df['high']
        low = df['low']

        # 1. ADX
        adx = cls.compute_adx(df, 14)

        # 2. Kaufman Efficiency Ratio
        change_10 = (close - close.shift(10)).abs()
        vol_10 = (close - close.shift(1)).abs().rolling(10).sum().replace(0, 1e-8)
        er = change_10 / vol_10

        # 3. NATR y Spike de Volatilidad
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14 = tr.rolling(14).mean()
        natr = atr_14 / close.replace(0, 1e-8)
        natr_median = natr.rolling(100).median().fillna(natr)
        vol_spike = natr > (2.0 * natr_median)

        filtered_signals = signals.copy()

        # Cortacircuito de volatilidad: Bloquear 100% en spikes explosivos de noticias
        filtered_signals.loc[vol_spike] = None

        if strategy_type == 'MEAN_REVERSION':
            # Desactivar Reversión a la Media durante tendencias fuertes
            trending_mask = (adx > 25.0) & (er > 0.45)
            filtered_signals.loc[trending_mask] = None
        elif strategy_type == 'TREND_FOLLOWING':
            # Desactivar Seguimiento de Tendencia durante consolidaciones laterales apretadas
            ranging_mask = (adx < 20.0) & (er < 0.25)
            filtered_signals.loc[ranging_mask] = None

        return filtered_signals
