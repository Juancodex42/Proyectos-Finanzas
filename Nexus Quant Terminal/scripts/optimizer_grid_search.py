import sys, os, time, itertools, warnings
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
warnings.filterwarnings('ignore')
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))

from engine.simulator import BinarySimulator
from engine.ml_engine.feature_extractor import BinaryFeatureExtractor
from engine.ml_engine.meta_filter import BinaryMLMetaFilter
from engine.ml_engine.meta_labeler import MetaLabeler
from engine.ml_engine.regime_detector import RegimeDetector
from engine.ml_engine.cusum_monitor import CUSUMMonitor
from strategies import STRATEGIES

DATASETS = [
    ('BTCUSDT_30m', os.path.join(ROOT_DIR, 'data', 'raw', 'BTCUSDT_30m.csv')),
    ('BTCUSDT_4h', os.path.join(ROOT_DIR, 'data', 'raw', 'BTCUSDT_4h.csv')),
    ('ETHUSDT_4h', os.path.join(ROOT_DIR, 'data', 'raw', 'ETHUSDT_4h.csv')),
]

STRATEGY_NAMES = ['mean_reversion', 'rsi_extremes', 'bollinger_bounce', 'volatility_squeeze_ml', 'support_resistance']

META_THRESHOLDS = [0.52, 0.55, 0.60, 0.65]

REGIME_CONFIGS = [
    ('none', None),     # Sin régimen
    ('hmm_48', 0.48),   
    ('hmm_50', 0.50),
]

EXPIRY_CANDLES = [1, 2]
PAYOUT = 0.85

def create_labels(df, signals, expiry_candles=1):
    entry_prices = df['open'].shift(-1)
    exit_prices = df['close'].shift(-expiry_candles)
    
    labels = pd.Series(index=signals.index, dtype=float)
    calls = signals == 'CALL'
    puts = signals == 'PUT'
    
    diff = exit_prices - entry_prices
    
    labels[calls & (diff > 1e-8)] = 1.0
    labels[calls & (diff <= 1e-8)] = 0.0
    labels[puts & (diff < -1e-8)] = 1.0
    labels[puts & (diff >= -1e-8)] = 0.0
    
    return labels.dropna()

_df_cache = {}

_signal_cache = {}

def evaluate_combination(args):
    dataset_name, csv_path, strat_name, meta_thresh, regime_config, expiry = args
    
    try:
        if csv_path not in _df_cache:
            df = pd.read_csv(csv_path)
            if len(df) > 15000:
                df = df.tail(15000).reset_index(drop=True)
            _df_cache[csv_path] = df
        df = _df_cache[csv_path]
        
        cache_key = (csv_path, strat_name)
        if cache_key not in _signal_cache:
            strategy = STRATEGIES[strat_name]()
            _signal_cache[cache_key] = strategy.generate_signals(df)
        signals = _signal_cache[cache_key]
        
        # Split con Purged CV & Embargo
        from engine.ml_engine.purged_cv import PurgedGroupTimeSeriesSplit
        train_end, test_start = PurgedGroupTimeSeriesSplit.purge_embargo_split(
            n_samples=len(df), train_ratio=0.6, expiry_candles=expiry, embargo_pct=0.01
        )
        df_train = df.iloc[:train_end]
        df_test = df.iloc[test_start:].reset_index(drop=True)
        signals_train = signals.iloc[:train_end]
        signals_test = signals.iloc[test_start:].reset_index(drop=True)
        
        # Crear labels de entrenamiento
        labels = create_labels(df_train, signals_train, expiry)
        if len(labels) < 20:
            return None
        
        # Entrenar MetaLabeler
        meta = MetaLabeler(threshold=meta_thresh)
        meta.fit(df_train, signals_train, labels)
        
        # Aplicar MetaLabeler en test
        if meta.is_fitted:
            filtered = meta.filter(df_test, signals_test)
        else:
            filtered = signals_test
        
        # Aplicar Régimen (si corresponde)
        regime_name, regime_breakeven = regime_config
        if regime_breakeven is not None:
            regime = RegimeDetector(n_states=3)
            regime.fit(df_train, signals_train, labels)
            # OVERRIDE: usar breakeven relajado
            regime.favorable_states = [
                s for s, stats in regime.state_stats.items()
                if stats['win_rate'] > regime_breakeven
            ]
            if not regime.favorable_states and regime.state_stats:
                # Si ninguno pasa, usar el mejor estado
                best = max(regime.state_stats.items(), key=lambda x: x[1]['win_rate'])
                regime.favorable_states = [best[0]]
            
            # Filtrar por régimen (vectorizado, forward-only)
            obs_test = regime._prepare_observations(df_test)
            if len(obs_test) > 0 and regime.is_fitted:
                states_test = regime.predict_forward(obs_test)
                state_series = pd.Series(states_test, index=df_test.index)
                
                regime_filtered = pd.Series(index=filtered.index, data=None, dtype=object)
                for idx in filtered.dropna().index:
                    if idx in state_series.index and state_series.loc[idx] in regime.favorable_states:
                        regime_filtered.loc[idx] = filtered.loc[idx]
                filtered = regime_filtered
        
        # Simular
        sim = BinarySimulator().run(df_test, filtered, expiry_candles=expiry, payout=PAYOUT)
        s = sim['summary']
        
        if s['total_trades'] < 10:
            return None
        
        return {
            'dataset': dataset_name,
            'strategy': strat_name,
            'meta_threshold': meta_thresh,
            'regime': regime_name,
            'expiry': expiry,
            'trades': s['total_trades'],
            'win_rate': s['win_rate'],
            'ev_per_trade': s['expected_value_per_trade'],
            'max_dd': s['max_drawdown'],
        }
    except Exception as e:
        return None

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    
    # Generar todas las combinaciones
    combos = []
    for ds_name, ds_path in DATASETS:
        full_path = os.path.join(base, ds_path)
        if not os.path.exists(full_path):
            continue
        for strat in STRATEGY_NAMES:
            for thresh in META_THRESHOLDS:
                for regime in REGIME_CONFIGS:
                    for expiry in EXPIRY_CANDLES:
                        combos.append((ds_name, full_path, strat, thresh, regime, expiry))
    
    print(f"Total combinaciones: {len(combos)}")
    print("Ejecutando...")
    
    results = []
    start = time.time()
    
    # Ejecutar en paralelo
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {executor.submit(evaluate_combination, combo): combo for combo in combos}
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            if completed % 10 == 0:
                elapsed = time.time() - start
                print(f"  Progreso: {completed}/{len(combos)} ({elapsed:.0f}s)")
            
            try:
                r = future.result(timeout=60)
                if r is not None and r['win_rate'] > 0.50:
                    results.append(r)
            except Exception as e:
                pass
    
    elapsed = time.time() - start
    print(f"\nCompletado en {elapsed:.1f}s")
    print(f"Combinaciones con WR > 50%: {len(results)}")
    
    if not results:
        print("\nNINGUNA combinación superó el 50%")
        return
    
    # Ordenar por EV/trade descendente
    results.sort(key=lambda x: x['ev_per_trade'], reverse=True)
    
    print("\n" + "=" * 110)
    print("TOP 20 MEJORES COMBINACIONES (ordenadas por EV/trade)")
    print("=" * 110)
    print(f"{'Dataset':<14} {'Strategy':<20} {'Thresh':>6} {'Regime':<8} {'Exp':>3} {'Trades':>7} {'WinRate':>8} {'EV/Trade':>10} {'MaxDD':>7}")
    print("-" * 110)
    
    for r in results[:20]:
        print(f"{r['dataset']:<14} {r['strategy']:<20} {r['meta_threshold']:>6.2f} {r['regime']:<8} {r['expiry']:>3} {r['trades']:>7} {r['win_rate']*100:>7.1f}% {r['ev_per_trade']:>+9.4f} {r['max_dd']*100:>6.1f}%")
    
    # Análisis: ¿Qué parámetros aparecen más en el top?
    print("\n" + "=" * 80)
    print("ANÁLISIS DE PARÁMETROS DOMINANTES")
    print("=" * 80)
    
    top = results[:20]
    # Datasets más exitosos
    from collections import Counter
    ds_counts = Counter(r['dataset'] for r in top)
    print(f"\nDatasets más exitosos: {dict(ds_counts)}")
    
    strat_counts = Counter(r['strategy'] for r in top)
    print(f"Estrategias más exitosas: {dict(strat_counts)}")
    
    thresh_counts = Counter(r['meta_threshold'] for r in top)
    print(f"Thresholds más exitosos: {dict(thresh_counts)}")
    
    regime_counts = Counter(r['regime'] for r in top)
    print(f"Régimen más exitoso: {dict(regime_counts)}")
    
    expiry_counts = Counter(r['expiry'] for r in top)
    print(f"Expiry más exitoso: {dict(expiry_counts)}")
    
    # Mejor combinación absoluta
    best = results[0]
    print(f"\n*** MEJOR COMBINACIÓN ***")
    print(f"Dataset: {best['dataset']}")
    print(f"Estrategia: {best['strategy']}")
    print(f"Meta Threshold: {best['meta_threshold']}")
    print(f"Régimen: {best['regime']}")
    print(f"Expiry: {best['expiry']}")
    print(f"Trades OOS: {best['trades']}")
    print(f"Win Rate OOS: {best['win_rate']*100:.1f}%")
    print(f"EV/Trade: {best['ev_per_trade']:+.4f}")
    print(f"Max Drawdown: {best['max_dd']*100:.1f}%")

if __name__ == '__main__':
    main()
