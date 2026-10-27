import time, sys, os
import pandas as pd
import numpy as np

# Setup path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.simulator import BinarySimulator
from engine.ml_engine.feature_extractor import BinaryFeatureExtractor
from engine.ml_engine.meta_filter import BinaryMLMetaFilter
from engine.ml_engine.cusum_monitor import CUSUMMonitor
from engine.ml_engine.meta_labeler import MetaLabeler
from engine.ml_engine.regime_detector import RegimeDetector
from strategies import STRATEGIES

def create_labels(df, signals, expiry_candles=1):
    labels = pd.Series(index=signals.index, dtype=float)
    for idx in signals.dropna().index:
        entry_idx = df.index.get_loc(idx)
        exit_idx = entry_idx + expiry_candles
        if entry_idx + 1 >= len(df) or exit_idx >= len(df):
            continue
        entry_price = float(df.iloc[entry_idx + 1]['open'])
        exit_price = float(df.iloc[exit_idx]['close'])
        signal = signals.loc[idx]
        diff = exit_price - entry_price
        if signal == 'CALL':
            labels.loc[idx] = 1.0 if diff > 1e-8 else 0.0
        elif signal == 'PUT':
            labels.loc[idx] = 1.0 if diff < -1e-8 else 0.0
    return labels.dropna()

def main():
    print("+" + "-" * 82 + "+")
    print("|                    BACKTEST COMPARATIVO -- MECANISMOS DE WIN RATE                |")
    print("+" + "-" * 82 + "+")
    print("| Estrategia       | Modo              |  Trades | Win Rate |    EV/Trade |   DD   |")
    print("+" + "-" * 82 + "+")

    csv_path = os.path.join(os.path.dirname(__file__), "data", "raw", "BTCUSDT_4h.csv")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error cargando CSV: {e}")
        return

    # Usamos todas las velas o reducimos si es necesario para velocidad (10k max)
    if len(df) > 10000:
        df = df.tail(10000).reset_index(drop=True)

    expiry_candles = 1
    payout = 0.85
    strategies_to_test = ["mean_reversion", "rsi_extremes", "bollinger_bounce", "ema_cross", "volatility_squeeze"]

    for strat_name in strategies_to_test:
        try:
            strat_cls = STRATEGIES.get(strat_name)
            if not strat_cls:
                continue
                
            strategy = strat_cls()
            signals = strategy.generate_signals(df)

            from engine.ml_engine.purged_cv import PurgedGroupTimeSeriesSplit
            train_end, test_start = PurgedGroupTimeSeriesSplit.purge_embargo_split(
                n_samples=len(df), train_ratio=0.7, expiry_candles=expiry_candles, embargo_pct=0.01
            )
            df_train = df.iloc[:train_end].copy()
            df_test = df.iloc[test_start:].copy()
            
            signals_train = signals.iloc[:train_end]
            signals_test = signals.iloc[test_start:]

            # --- BASELINE ---
            sim_baseline = BinarySimulator().run(df_test.reset_index(drop=True), signals_test.reset_index(drop=True), expiry_candles=expiry_candles, payout=payout)
            stats_b = sim_baseline['summary']
            print(f"| {strat_name:<16} | BASELINE          | {stats_b['total_trades']:>7} | {stats_b['win_rate']*100:>7.1f}% | {stats_b['expected_value_per_trade']:>+10.4f} | {stats_b['max_drawdown']*100:>5.1f}% |")

            if len(signals_train.dropna()) < 10:
                print("+" + "-" * 82 + "+")
                continue
            
            # --- META-FILTER (Zero Data Leakage: Isolated Train & Test Extraction) ---
            features_train = BinaryFeatureExtractor.extract_features(df_train)
            features_test = BinaryFeatureExtractor.extract_features(df_test)
            labels_train = create_labels(df_train, signals_train, expiry_candles)
            
            meta_filter = BinaryMLMetaFilter(probability_threshold=0.55, adaptive_threshold=True)
            valid_train_idx = labels_train.index.intersection(features_train.index)
            X_train = features_train.loc[valid_train_idx]
            y_train = labels_train.loc[valid_train_idx]
            meta_filter.fit(X_train, y_train)
            
            filtered_signals_mf = meta_filter.filter_signals(signals_test, features_test)
            sim_mf = BinarySimulator().run(df_test.reset_index(drop=True), filtered_signals_mf.reset_index(drop=True), expiry_candles=expiry_candles, payout=payout)
            stats_mf = sim_mf['summary']
            print(f"| {strat_name:<16} | +META-FILTER      | {stats_mf['total_trades']:>7} | {stats_mf['win_rate']*100:>7.1f}% | {stats_mf['expected_value_per_trade']:>+10.4f} | {stats_mf['max_drawdown']*100:>5.1f}% |")
            
            # --- RÉGIMEN HMM ---
            regime = RegimeDetector()
            regime.fit(df_train, signals_train, labels_train)
            
            signals_regime = pd.Series(index=signals_test.index, dtype=object)
            for idx in signals_test.dropna().index:
                pos_idx = df.index.get_loc(idx)
                df_up_to_now = df.iloc[max(0, pos_idx-100):pos_idx+1]
                if regime.should_trade(df_up_to_now):
                    signals_regime.loc[idx] = signals_test.loc[idx]
                    
            filtered_signals_regime_mf = meta_filter.filter_signals(signals_regime, features_test)
            
            sim_reg = BinarySimulator().run(df_test.reset_index(drop=True), filtered_signals_regime_mf.reset_index(drop=True), expiry_candles=expiry_candles, payout=payout)
            stats_reg = sim_reg['summary']
            print(f"| {strat_name:<16} | +REGIMEN          | {stats_reg['total_trades']:>7} | {stats_reg['win_rate']*100:>7.1f}% | {stats_reg['expected_value_per_trade']:>+10.4f} | {stats_reg['max_drawdown']*100:>5.1f}% |")
            
            # --- PIPELINE COMPLETO (CUSUM) ---
            cusum = CUSUMMonitor(expected_wr=0.55, payout=payout, threshold_sigma=2.0, window=30)
            cusum_trades = []
            equity = 1000.0
            peak = 1000.0
            max_dd = 0.0
            
            for idx in filtered_signals_regime_mf.dropna().index:
                entry_idx = df.index.get_loc(idx)
                exit_idx = entry_idx + expiry_candles
                if entry_idx + 1 >= len(df) or exit_idx >= len(df):
                    continue
                    
                entry_price = float(df.iloc[entry_idx + 1]['open'])
                exit_price = float(df.iloc[exit_idx]['close'])
                signal = filtered_signals_regime_mf.loc[idx]
                
                trade_res = 0
                diff = exit_price - entry_price
                if (signal == 'CALL' and diff > 1e-8) or (signal == 'PUT' and diff < -1e-8):
                    trade_res = payout
                elif abs(diff) <= 1e-8:
                    trade_res = 0
                else:
                    trade_res = -1.0
                    
                if cusum.should_trade():
                    if trade_res == payout:
                        equity += 100 * payout
                    elif trade_res == -1.0:
                        equity -= 100
                    if equity > peak:
                        peak = equity
                    dd = (peak - equity)/peak
                    if dd > max_dd:
                        max_dd = dd
                    if trade_res != 0:
                        cusum_trades.append(trade_res)
                    
                cusum.update(trade_res)

            total_c = len(cusum_trades)
            wins_c = len([t for t in cusum_trades if t > 0])
            wr_c = wins_c / total_c if total_c > 0 else 0
            ev_c = (wr_c * payout) - ((1-wr_c)*1.0) if total_c > 0 else 0
            
            print(f"| {strat_name:<16} | FULL PIPELINE     | {total_c:>7} | {wr_c*100:>7.1f}% | {ev_c:>+10.4f} | {max_dd*100:>5.1f}% |")
            print("+" + "-" * 82 + "+")
        except Exception as e:
            print(f"| {strat_name:<16} | ERROR: {str(e)[:40]:<40} |")
            print("+" + "-" * 82 + "+")

if __name__ == '__main__':
    main()
