import unittest
import numpy as np
import pandas as pd

from engine.simulator import BinarySimulator
from engine.ml_engine.feature_extractor import BinaryFeatureExtractor, frac_diff_fixed
from engine.ml_engine.regime_detector import RegimeDetector
from engine.ml_engine.cusum_monitor import CUSUMMonitor
from engine.ml_engine.meta_labeler import MetaLabeler
from engine.ml_engine.meta_filter import BinaryMLMetaFilter
from engine.auto_tuner import WalkForwardEngine

class MockStrategy:
    """Mock strategy for WalkForwardEngine testing."""
    def prepare_data(self, df):
        return None

    def generate_signals(self, df, params, precomputed=None):
        signals = pd.Series(index=df.index, dtype=object)
        if params.get("generate_oos_trades", True):
            if len(df) > 5:
                signals.iloc[2] = 'CALL'
        return signals

class TestSimulatorIntegrity(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=100, freq='5min')
        self.df = pd.DataFrame({
            'open_time': (dates.astype(np.int64) // 10**6).values, # ms epoch
            'open': [100.0] * 100,
            'high': [101.0] * 100,
            'low': [99.0] * 100,
            'close': [100.0] * 100, # Flat prices -> ties
            'volume': [50.0] * 100
        }, index=dates)

    # 1. BinarySimulator Tests
    def test_multi_asset_tie_rule_loss(self):
        sim = BinarySimulator()
        universe_data = {'EURUSD': self.df.copy()}
        signals_by_pair = {'EURUSD': [{'time': int(self.df['open_time'].iloc[10]), 'direction': 'CALL'}]}
        
        res = sim.run_multi_asset(universe_data, signals_by_pair, tie_rule='LOSS')
        self.assertEqual(res['summary']['ties'], 0)
        self.assertEqual(res['summary']['losses'], 1)
        self.assertLess(res['summary']['net_pnl'], 0)

    def test_multi_asset_tie_rule_return_stake(self):
        sim = BinarySimulator()
        universe_data = {'EURUSD': self.df.copy()}
        signals_by_pair = {'EURUSD': [{'time': int(self.df['open_time'].iloc[10]), 'direction': 'CALL'}]}
        
        res = sim.run_multi_asset(universe_data, signals_by_pair, tie_rule='RETURN_STAKE')
        self.assertEqual(res['summary']['ties'], 1)
        self.assertEqual(res['summary']['losses'], 0)
        self.assertEqual(res['summary']['net_pnl'], 0.0)

    def test_multi_asset_barbell_streak_reset_no_corruption(self):
        sim = BinarySimulator()
        # Build price data with distinct movement for 2 pairs
        dates = pd.date_range('2023-01-01', periods=50, freq='5min')
        times = (dates.astype(np.int64) // 10**6).values
        
        df1 = pd.DataFrame({
            'open_time': times,
            'open': [100 + i for i in range(50)],
            'high': [101 + i for i in range(50)],
            'low': [99 + i for i in range(50)],
            'close': [101 + i for i in range(50)], # Wins for CALL
            'volume': [50.0] * 50
        })
        
        df2 = pd.DataFrame({
            'open_time': times,
            'open': [200.0] * 50,
            'high': [201.0] * 50,
            'low': [199.0] * 50,
            'close': [200.0] * 50, # Flat
            'volume': [50.0] * 50
        })
        
        universe_data = {'FX1': df1, 'FX2': df2}
        signals_by_pair = {
            'FX1': [
                {'time': int(times[2]), 'direction': 'CALL'},
                {'time': int(times[10]), 'direction': 'CALL'},
                {'time': int(times[18]), 'direction': 'CALL'},
            ],
            'FX2': [
                {'time': int(times[4]), 'direction': 'CALL'}
            ]
        }
        
        res = sim.run_multi_asset(
            universe_data, signals_by_pair,
            mode='BARBELL', n_consecutive=2, bet_fraction=0.5
        )
        self.assertIsNotNone(res)
        self.assertGreater(len(res['trades']), 0)

    def test_multi_asset_barbell_reset_in_flight_trade_accounting(self):
        day = 86400
        t1 = 1767261600
        t2, t3, t4, t5, t6, t7 = [t1 + i * day for i in range(1, 7)]
        
        eur_df = pd.DataFrame({
            'open_time': [t1, t2, t3, t4, t5, t6, t7],
            'open': [1.1000] * 7,
            'high': [1.1050] * 7,
            'low': [1.0950] * 7,
            'close': [1.1020] * 7,
            'volume': [1000] * 7
        })
        btc_df = pd.DataFrame({
            'open_time': [t1, t2, t6, t7, t1 + 7*day],
            'open': [50000.0] * 5,
            'high': [50500.0] * 5,
            'low': [49500.0] * 5,
            'close': [50200.0] * 5,
            'volume': [100] * 5
        })
        
        universe_data = {'EURUSD': eur_df, 'BTCUSDT': btc_df}
        signals_by_pair = {
            'EURUSD': [
                {'time': t1, 'direction': 'CALL'},
                {'time': t3, 'direction': 'CALL'}
            ],
            'BTCUSDT': [
                {'time': t1, 'direction': 'CALL'}
            ]
        }
        
        sim = BinarySimulator()
        res = sim.run_multi_asset(
            universe_data=universe_data,
            signals_by_pair=signals_by_pair,
            expiry_candles=1,
            payout=0.85,
            initial_capital=1000.0,
            mode='BARBELL',
            n_consecutive=2,
            bet_fraction=0.5,
            risk_ratio=0.20
        )
        
        trades = res['trades']
        equity_curve = res['equity_curve']
        self.assertEqual(len(trades), 3)
        
        btc_trade = next(t for t in trades if t['pair'] == 'BTCUSDT')
        eq_day5 = equity_curve[-2]['equity']
        eq_day6 = equity_curve[-1]['equity']
        next_cap = 114.225
        in_flight_pnl_captured = (eq_day6 - eq_day5) - next_cap
        
        self.assertAlmostEqual(in_flight_pnl_captured, btc_trade['pnl'], places=4)

    # 2. BinaryFeatureExtractor & Hurst Tests
    def test_frac_diff_fixed_vectorized(self):
        s = pd.Series(np.random.randn(1000).cumsum())
        res = frac_diff_fixed(s, d=0.4)
        self.assertEqual(len(res), len(s))
        self.assertFalse(res.dropna().empty)

    def test_calc_hurst_nan_origin_zero_and_near_zero_std(self):
        # Test series with initial NaNs and constant values
        arr = np.array([np.nan] * 5 + [100.0] * 50)
        close = pd.Series(arr)
        extractor = BinaryFeatureExtractor()
        df = pd.DataFrame({
            'open': close, 'high': close + 1, 'low': close - 1, 'close': close, 'volume': 100
        })
        features = extractor.extract_features(df)
        self.assertIn('hurst_exp', features.columns)
        self.assertFalse(np.isinf(features['hurst_exp']).any())

    # 3. RegimeDetector & CUSUMMonitor Tests
    def test_regime_detector_no_lookahead(self):
        detector = RegimeDetector()
        obs = detector._prepare_observations(self.df)
        self.assertEqual(obs.shape[0], len(self.df))
        self.assertFalse(np.isnan(obs).any())

    def test_cusum_monitor_bounds_and_recovery(self):
        monitor = CUSUMMonitor(expected_wr=0.6, payout=0.85, window=20)
        # Push 1200 trade results to test 1000 boundary
        for _ in range(1200):
            monitor.update(-1.0)
        
        self.assertLessEqual(len(monitor.trade_results), 1000)
        self.assertEqual(monitor.total_trades_count, 1200)
        self.assertTrue(monitor.is_paused)
        
        # Test recovery with paper winning trades post-pause
        statuses = [monitor.update(0.85) for _ in range(10)]
            
        self.assertIn('RESUME', statuses)
        self.assertFalse(monitor.is_paused)
        
        # Test reset()
        monitor.reset()
        self.assertEqual(len(monitor.trade_results), 0)
        self.assertEqual(monitor.total_trades_count, 0)
        self.assertFalse(monitor.is_paused)

    # 4. MetaLabeler & BinaryMLMetaFilter Tests
    def test_meta_labeler_timestamp_parsing(self):
        labeler = MetaLabeler()
        # Test with millisecond timestamps
        signal_indices = self.df.index[10:15]
        context = labeler._extract_context_features(self.df, signal_indices)
        self.assertIn('hour_of_day', context.columns)
        self.assertFalse(context['hour_of_day'].isna().any())

    def test_meta_filter_rolling_median(self):
        m_filter = BinaryMLMetaFilter(probability_threshold=0.65, adaptive_threshold=True)
        # Verify that changing future NATR doesn't affect past threshold evaluation
        X_past = pd.DataFrame({'natr': [0.01] * 50}, index=range(50))
        signals_past = pd.Series(['CALL'], index=[40])
        
        X_future = pd.DataFrame({'natr': [0.01] * 50 + [0.50] * 50}, index=range(100))
        
        # Threshold at index 40 should be base_threshold because future values at index 50..99 are not in past
        m_filter.filter_signals(signals_past, X_past)
        past_thresh = m_filter.probability_threshold
        
        m_filter.filter_signals(signals_past, X_future)
        future_thresh = m_filter.probability_threshold
        
        self.assertEqual(past_thresh, future_thresh)

    # 5. WalkForwardEngine Tests
    def test_walk_forward_engine_zero_oos_trades_not_stable(self):
        wfe_engine = WalkForwardEngine(n_windows=3, train_ratio=0.6)
        mock_strat = MockStrategy()
        
        # Create dataset with 500 rows
        dates = pd.date_range('2023-01-01', periods=500, freq='5min')
        df_test = pd.DataFrame({
            'open_time': (dates.astype(np.int64) // 10**6).values,
            'open': np.random.randn(500).cumsum() + 100,
            'high': np.random.randn(500).cumsum() + 101,
            'low': np.random.randn(500).cumsum() + 99,
            'close': np.random.randn(500).cumsum() + 100,
            'volume': 100
        }, index=dates)
        
        # Strategy that generates 0 OOS trades
        params = {"generate_oos_trades": False}
        res = wfe_engine.run_wfa(df_test, mock_strat, params)
        
        self.assertEqual(res['stable_windows'], 0)

if __name__ == '__main__':
    unittest.main()
