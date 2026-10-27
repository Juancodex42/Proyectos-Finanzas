import sys, os, time
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from optimizer_grid_search import evaluate_combination, DATASETS, STRATEGY_NAMES, META_THRESHOLDS, REGIME_CONFIGS, EXPIRY_CANDLES

print("Iniciando debug...")
t0 = time.time()
combo = (DATASETS[0][0], os.path.join(os.path.dirname(os.path.abspath(__file__)), DATASETS[0][1]), STRATEGY_NAMES[0], META_THRESHOLDS[0], REGIME_CONFIGS[1], EXPIRY_CANDLES[0])
print(f"Probando combo: {combo}")

# evaluamos paso a paso replicando evaluate_combination para ver donde cuelga
dataset_name, csv_path, strat_name, meta_thresh, regime_config, expiry = combo

print(f"Reading CSV... {time.time()-t0:.2f}s")
df = pd.read_csv(csv_path)
if len(df) > 15000: df = df.tail(15000).reset_index(drop=True)

print(f"Generando señales... {time.time()-t0:.2f}s")
from strategies import STRATEGIES
strategy = STRATEGIES[strat_name]()
signals = strategy.generate_signals(df)

print(f"Split data... {time.time()-t0:.2f}s")
split = int(len(df) * 0.6)
df_train = df.iloc[:split]
df_test = df.iloc[split:].reset_index(drop=True)
signals_train = signals.iloc[:split]
signals_test = signals.iloc[split:].reset_index(drop=True)

print(f"Create labels... {time.time()-t0:.2f}s")
from optimizer_grid_search import create_labels
labels = create_labels(df_train, signals_train, expiry)

print(f"Entrenar MetaLabeler... {time.time()-t0:.2f}s")
from engine.ml_engine.meta_labeler import MetaLabeler
meta = MetaLabeler(threshold=meta_thresh)
meta.fit(df_train, signals_train, labels)

print(f"Aplicar MetaLabeler... {time.time()-t0:.2f}s")
if meta.is_fitted:
    filtered = meta.filter(df_test, signals_test)
else:
    filtered = signals_test

print(f"Aplicar Regimen... {time.time()-t0:.2f}s")
regime_name, regime_breakeven = regime_config
from engine.ml_engine.regime_detector import RegimeDetector
if regime_breakeven is not None:
    regime = RegimeDetector(n_states=3)
    regime.fit(df_train, signals_train, labels)

print(f"Simular... {time.time()-t0:.2f}s")
from engine.simulator import BinarySimulator
sim = BinarySimulator().run(df_test, filtered, expiry_candles=expiry, payout=0.85)

print(f"Terminado! {time.time()-t0:.2f}s")
