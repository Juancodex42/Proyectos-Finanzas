import pytest
import pandas as pd
import numpy as np
from engine.simulator import compute_atr, TripleBarrierSimulator

def create_synthetic_data(n=100, base_price=100.0, trend=0.0):
    np.random.seed(42)
    closes = [base_price]
    for i in range(1, n):
        ret = trend + np.random.normal(0, 0.01)
        closes.append(closes[-1] * (1.0 + ret))
    
    df = pd.DataFrame({
        'open': [c * (1.0 - np.random.uniform(-0.002, 0.002)) for c in closes],
        'close': closes,
        'high': [c * (1.0 + abs(np.random.uniform(0.002, 0.01))) for c in closes],
        'low': [c * (1.0 - abs(np.random.uniform(0.002, 0.01))) for c in closes],
        'volume': [1000.0 + np.random.uniform(0, 500) for _ in closes]
    })
    return df

class TestTripleBarrierSimulator:
    def test_atr_computation(self):
        df = create_synthetic_data(100)
        atr = compute_atr(df, period=14)
        assert len(atr) == len(df)
        assert not np.isnan(atr[-1])
        assert atr[-1] > 0

    def test_long_trade_hit_sl_loses_exact_bullet_risk(self):
        df = create_synthetic_data(100)
        # Entry at index 31 (open 100). Next bars drop significantly
        df.loc[31, 'open'] = 100.0
        df.loc[31, 'high'] = 100.2
        df.loc[31, 'low'] = 70.0
        df.loc[31, 'close'] = 75.0
        
        signals = pd.Series([None] * len(df))
        signals.iloc[30] = 'CALL'
        
        bullet_risk = 33.3333
        res = TripleBarrierSimulator.run(
            df=df,
            signals=signals,
            sl_atr=1.5,
            tp_atr=4.5,
            max_holding=10,
            bullet_risk=bullet_risk,
            fee_pct=0.0005,
            slippage_pct=0.0002
        )
        
        trades = res.get('trades', [])
        assert len(trades) >= 1
        t = trades[0]
        assert t['direction'] == 'LONG'
        assert t['exit_reason'] == 'SL'
        assert pytest.approx(t['pnl'], abs=1.0) == -bullet_risk
        assert t['r_multiple'] <= -0.95

    def test_long_trade_hit_tp_gains_asymmetric_rr(self):
        df = create_synthetic_data(100)
        # Entry at index 31 (open 100). Next bars spike up
        df.loc[31, 'open'] = 100.0
        df.loc[31, 'high'] = 140.0
        df.loc[31, 'low'] = 99.8
        df.loc[31, 'close'] = 138.0
        
        signals = pd.Series([None] * len(df))
        signals.iloc[30] = 'LONG'
        
        bullet_risk = 33.3333
        res = TripleBarrierSimulator.run(
            df=df,
            signals=signals,
            sl_atr=1.0,
            tp_atr=3.0,
            max_holding=10,
            bullet_risk=bullet_risk,
            fee_pct=0.0005,
            slippage_pct=0.0002
        )
        
        trades = res.get('trades', [])
        assert len(trades) >= 1
        t = trades[0]
        assert t['direction'] == 'LONG'
        assert t['exit_reason'] == 'TP'
        assert t['pnl'] > (bullet_risk * 2.0)
        assert t['r_multiple'] >= 2.0

    def test_timeout_exit_at_max_holding(self):
        df = create_synthetic_data(100)
        # Flatten price around index 31 to 45
        for i in range(31, 45):
            df.loc[i, 'open'] = 100.0
            df.loc[i, 'high'] = 100.1
            df.loc[i, 'low'] = 99.9
            df.loc[i, 'close'] = 100.0
            
        signals = pd.Series([None] * len(df))
        signals.iloc[30] = 'CALL'
        
        res = TripleBarrierSimulator.run(
            df=df,
            signals=signals,
            sl_atr=5.0,
            tp_atr=10.0,
            max_holding=4,
            bullet_risk=33.3333
        )
        
        trades = res.get('trades', [])
        assert len(trades) >= 1
        t = trades[0]
        assert t['exit_reason'] == 'TIMEOUT'
        assert t['duration'] == 4
