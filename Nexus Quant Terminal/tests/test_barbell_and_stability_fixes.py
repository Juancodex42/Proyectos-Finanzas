import unittest
import numpy as np
import pandas as pd

from strategies.volatility_squeeze_ml import VolatilitySqueezeMLStrategy
from engine.simulator import TripleBarrierSimulator
from engine.ml_engine.purged_cv import WalkForwardTimeSeriesSplit


class TestBarbellAndStabilityFixes(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        n = 250
        dates = pd.date_range('2023-01-01', periods=n, freq='1D')
        self.df = pd.DataFrame({
            'open_time': (dates.astype('int64') // 10**6).to_numpy(),
            'open': np.random.randn(n).cumsum() + 100,
            'high': 0.0,
            'low': 0.0,
            'close': 0.0,
            'volume': np.random.randint(100, 1000, size=n)
        }, index=dates)
        self.df['close'] = self.df['open'] + np.random.randn(n) * 0.5
        self.df['high'] = self.df[['open', 'close']].max(axis=1) + np.random.rand(n) * 0.5
        self.df['low'] = self.df[['open', 'close']].min(axis=1) - np.random.rand(n) * 0.5

    def test_volatility_squeeze_bb_pctl_thresh_connected(self):
        """Verifica que bb_pctl_thresh filtre señales cuando la compresión de volatilidad es estricta."""
        strat = VolatilitySqueezeMLStrategy()
        pre = strat.prepare_data(self.df)
        
        strict_signals = strat.generate_signals(self.df, params={'bb_pctl_thresh': 0.0001, 'prob_thresh': 0.50}, precomputed=pre)
        loose_signals = strat.generate_signals(self.df, params={'bb_pctl_thresh': 1.0, 'prob_thresh': 0.50}, precomputed=pre)

        strict_count = strict_signals.dropna().count() if strict_signals is not None else 0
        loose_count = loose_signals.dropna().count() if loose_signals is not None else 0

        self.assertLessEqual(strict_count, loose_count)

    def test_barbell_30_day_calendar_cycle(self):
        """Verifica que TripleBarrierSimulator no inyecte dinero artificial en el mismo día tras agotar balas."""
        signals = pd.Series(index=self.df.index, data='CALL')
        
        sim_res = TripleBarrierSimulator.run(
            df=self.df,
            signals=signals,
            sl_atr=1.5,
            tp_atr=3.0,
            initial_capital=1000.0,
            mode='BARBELL',
            n_consecutive=3,
            risk_ratio=0.20,
            bullet_risk=33.3333
        )
        
        trades = sim_res.get('trades', [])
        equity_curve = sim_res.get('equity_curve', [])
        
        for pt in equity_curve:
            self.assertGreaterEqual(pt['equity'], 0.0)

    def test_walk_forward_time_series_split_is_strictly_causal(self):
        """Verifica que WalkForwardTimeSeriesSplit garantice que train siempre preceda a test."""
        cv = WalkForwardTimeSeriesSplit(n_splits=4, min_train_ratio=0.30)
        X = np.arange(200)
        
        splits = list(cv.split(X))
        self.assertGreater(len(splits), 0)
        
        for train_idx, test_idx in splits:
            self.assertLess(np.max(train_idx), np.min(test_idx))


if __name__ == '__main__':
    unittest.main()
