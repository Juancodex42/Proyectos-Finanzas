import unittest
import pandas as pd
import numpy as np

from engine.ml_engine import (
    BinaryFeatureExtractor,
    CUSUMMonitor,
    MetaLabeler,
    RegimeDetector,
    BinaryMLMetaFilter
)
from engine.ml_engine.feature_extractor import frac_diff_fixed

class TestHighWinrateMechanisms(unittest.TestCase):
    
    def setUp(self):
        # Crear un dataframe dummy
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=200, freq='5min')
        self.df = pd.DataFrame({
            'open': np.random.randn(200).cumsum() + 100,
            'high': 0.0,
            'low': 0.0,
            'close': 0.0,
            'volume': np.random.randint(10, 100, size=200)
        }, index=dates)
        
        self.df['close'] = self.df['open'] + np.random.randn(200)
        self.df['high'] = self.df[['open', 'close']].max(axis=1) + np.random.rand(200)
        self.df['low'] = self.df[['open', 'close']].min(axis=1) - np.random.rand(200)

    def test_frac_diff_fixed(self):
        res = frac_diff_fixed(self.df['close'], d=0.4)
        self.assertEqual(len(res), len(self.df))
        self.assertFalse(res.isna().all())

    def test_cusum_monitor(self):
        monitor = CUSUMMonitor(expected_wr=0.6, payout=0.85, window=20)
        
        # Simular racha perdedora (deterioro)
        for _ in range(15):
            status = monitor.update(-1.0)
            
        self.assertIn(status, ['PAUSE', 'PAUSED'])
        self.assertFalse(monitor.should_trade())
        
        stats = monitor.get_stats()
        self.assertTrue(stats['is_paused'])

    def test_meta_labeler_instantiation(self):
        labeler = MetaLabeler(threshold=0.7)
        self.assertTrue(hasattr(labeler, 'fit'))
        self.assertTrue(hasattr(labeler, 'filter'))
        self.assertFalse(labeler.is_fitted)

    def test_regime_detector_instantiation(self):
        detector = RegimeDetector()
        self.assertTrue(hasattr(detector, 'fit'))
        self.assertTrue(hasattr(detector, 'get_current_state'))
        self.assertTrue(hasattr(detector, 'should_trade'))

    def test_meta_filter_adaptive(self):
        m_filter = BinaryMLMetaFilter(probability_threshold=0.65, adaptive_threshold=True)
        X_train = pd.DataFrame({'natr': [0.01]*10 + [0.01]*10})
        y_train = pd.Series([0]*10 + [1]*10)
        m_filter.fit(X_train, y_train)
        
        # Crear X dummy con natr alto
        X = pd.DataFrame({
            'natr': [0.01]*100 + [0.05] # Último valor alto
        }, index=range(101))
        signals = pd.Series(['CALL'], index=[100])
        # Al filtrar, debería ajustar el umbral.
        filtered = m_filter.filter_signals(signals, X)
        self.assertTrue(m_filter.probability_threshold > 0.65)

if __name__ == '__main__':
    unittest.main()
