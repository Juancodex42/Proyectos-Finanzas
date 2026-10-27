import os
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.comparative_engine import ComparativeQuantitativeEngine
from engine.ml_engine.feature_extractor import BinaryFeatureExtractor
from engine.ml_engine.meta_filter import BinaryMLMetaFilter
from engine.ml_engine.purged_cv import PurgedGroupTimeSeriesSplit
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

def run_ml_filtered_comparison():
    print("=" * 110)
    print("   COMPARATIVA DE DUPLICACIÓN CON SEÑALES DE ALTA PRECISIÓN (META-FILTRO ML + RÉGIMEN)")
    print("=" * 110)

    csv_path = os.path.join(os.path.dirname(__file__), "data", "raw", "BTCUSDT_4h.csv")
    df = pd.read_csv(csv_path)
    if len(df) > 8000:
        df = df.tail(8000).reset_index(drop=True)

    expiry_candles = 1
    payout = 0.85
    strat_cls = STRATEGIES.get("mean_reversion")
    strategy = strat_cls()
    signals = strategy.generate_signals(df)

    train_end, test_start = PurgedGroupTimeSeriesSplit.purge_embargo_split(
        n_samples=len(df), train_ratio=0.7, expiry_candles=expiry_candles, embargo_pct=0.01
    )
    df_train = df.iloc[:train_end].copy()
    df_test = df.iloc[test_start:].copy()
    signals_train = signals.iloc[:train_end]
    signals_test = signals.iloc[test_start:]

    # Train ML Meta Filter (Zero Data Leakage: Isolated Train & Test Extraction)
    features_train = BinaryFeatureExtractor.extract_features(df_train)
    features_test = BinaryFeatureExtractor.extract_features(df_test)
    labels_train = create_labels(df_train, signals_train, expiry_candles)
    
    meta_filter = BinaryMLMetaFilter(probability_threshold=0.58, adaptive_threshold=True)
    valid_train_idx = labels_train.index.intersection(features_train.index)
    X_train = features_train.loc[valid_train_idx]
    y_train = labels_train.loc[valid_train_idx]
    meta_filter.fit(X_train, y_train)
    
    filtered_signals = meta_filter.filter_signals(signals_test, features_test)

    engine = ComparativeQuantitativeEngine(initial_capital=1000.0, target_capital=2000.0, ruin_capital=200.0)

    scenarios = [
        ("Binarias: Flat 2% (ML Filtrado 70%+ WR)", lambda: engine.simulate_binary_fixed_risk(df_test, filtered_signals, expiry_candles=1, payout=0.85, risk_pct_per_trade=0.02)),
        ("Binarias: Flat 5% (ML Filtrado 70%+ WR)", lambda: engine.simulate_binary_fixed_risk(df_test, filtered_signals, expiry_candles=1, payout=0.85, risk_pct_per_trade=0.05)),
        ("Binarias: Paroli 6 Balas/3 Rachas (ML Filtrado)", lambda: engine.simulate_binary_paroli_bullets(df_test, filtered_signals, expiry_candles=1, payout=0.85, committed_risk_pct=0.20, n_bullets=6, streak_target=3)),
        ("Clásico: Spot 1x (Risk-Norm 2%, R:R 1:1.5)", lambda: engine.simulate_classic_leveraged_fixed_risk(df_test, filtered_signals, leverage=1.0, risk_pct_per_trade=0.02, rr_ratio=1.5)),
        ("Clásico: Apalancado 2x (Risk-Norm 2%, R:R 1:1.5)", lambda: engine.simulate_classic_leveraged_fixed_risk(df_test, filtered_signals, leverage=2.0, risk_pct_per_trade=0.02, rr_ratio=1.5)),
        ("Clásico: Apalancado 5x (Risk-Norm 2%, R:R 1:1.5)", lambda: engine.simulate_classic_leveraged_fixed_risk(df_test, filtered_signals, leverage=5.0, risk_pct_per_trade=0.02, rr_ratio=1.5)),
        ("Clásico: Apalancado 10x (Risk-Norm 2%, R:R 1:1.5)", lambda: engine.simulate_classic_leveraged_fixed_risk(df_test, filtered_signals, leverage=10.0, risk_pct_per_trade=0.02, rr_ratio=1.5)),
        ("Clásico: Apalancado 20x (Risk-Norm 2%, R:R 1:1.5)", lambda: engine.simulate_classic_leveraged_fixed_risk(df_test, filtered_signals, leverage=20.0, risk_pct_per_trade=0.02, rr_ratio=1.5)),
        ("Clásico: Salida por Tiempo 5x Nominal (1 vela)", lambda: engine.simulate_classic_fixed_notional_leverage(df_test, filtered_signals, leverage=5.0, expiry_candles=1)),
        ("Clásico: Salida por Tiempo 10x Nominal (1 vela)", lambda: engine.simulate_classic_fixed_notional_leverage(df_test, filtered_signals, leverage=10.0, expiry_candles=1)),
        ("Clásico: Salida por Tiempo 20x Nominal (1 vela)", lambda: engine.simulate_classic_fixed_notional_leverage(df_test, filtered_signals, leverage=20.0, expiry_candles=1)),
    ]

    results = []
    for label, fn in scenarios:
        res = fn()
        mc = engine.run_monte_carlo_duplication(res, n_simulations=10000, max_trades_per_path=500)
        results.append({
            "scenario": label,
            "trades": res["total_trades"],
            "win_rate": res["win_rate"],
            "profit_factor": res["profit_factor"],
            "max_dd": res["max_drawdown"],
            "sharpe": res["sharpe_ratio"],
            "p_double": mc["prob_double"],
            "p_ruin": mc["prob_ruin"],
            "avg_trades_2x": mc["avg_trades_to_double"]
        })

    df_res = pd.DataFrame(results).sort_values(by="p_double", ascending=False)
    print(f"\n| {'Escenario':<46} | {'WR':<6} | {'PF':<6} | {'MaxDD':<7} | {'Sharpe':<7} | {'P(2x Meta)':<11} | {'P(Ruina)':<9} | {'Trades 2x':<9} |")
    print("|" + "-" * 48 + "|" + "-" * 8 + "|" + "-" * 8 + "|" + "-" * 9 + "|" + "-" * 9 + "|" + "-" * 13 + "|" + "-" * 11 + "|" + "-" * 11 + "|")
    for _, r in df_res.iterrows():
        p2x = f"{r['p_double']*100:.1f}%"
        pruin = f"{r['p_ruin']*100:.1f}%"
        t2x = f"{r['avg_trades_2x']:.0f}" if r['avg_trades_2x'] is not None else "N/A"
        print(f"| {r['scenario']:<46} | {r['win_rate']*100:>5.1f}% | {r['profit_factor']:>6.2f} | {r['max_dd']*100:>6.1f}% | {r['sharpe']:>7.2f} | {p2x:>11} | {pruin:>9} | {t2x:>9} |")
    print("=" * 110)

    # Save to json
    out_path = os.path.join(os.path.dirname(__file__), "scratch", "ml_filtered_comparison_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Guardado en {out_path}")

if __name__ == '__main__':
    run_ml_filtered_comparison()
