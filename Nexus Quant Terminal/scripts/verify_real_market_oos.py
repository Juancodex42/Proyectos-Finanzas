import os
import math
import numpy as np
import pandas as pd

from engine.simulator import BinarySimulator, TripleBarrierSimulator
from engine.ml_engine.feature_extractor import BinaryFeatureExtractor
from engine.ml_engine.meta_filter import BinaryMLMetaFilter
from engine.ml_engine.purged_cv import PurgedGroupTimeSeriesSplit
from strategies.daily_confluence import DailyConfluenceStrategy
from strategies.volatility_squeeze_ml import VolatilitySqueezeMLStrategy
from strategies.genetic_composite import GeneticCompositeStrategy
from strategies.bollinger_bounce import BollingerBounceStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.climax_reversal import ClimaxReversalStrategy

def calculate_wilson_score_lower(wins: int, total: int, confidence: float = 0.95) -> float:
    """Calcula el límite inferior del intervalo de confianza de Wilson al 95%."""
    if total == 0:
        return 0.0
    p = wins / total
    z = 1.95996  # 95% CI z-score
    denominator = 1 + (z ** 2) / total
    centre = p + (z ** 2) / (2 * total)
    spread = z * math.sqrt((p * (1 - p) + (z ** 2) / (4 * total)) / total)
    lower_bound = (centre - spread) / denominator
    return float(lower_bound * 100.0)

def load_real_data(symbol: str, timeframe: str = "4h") -> pd.DataFrame:
    """Carga datos reales desde data/raw o data/."""
    base_dir = os.path.dirname(__file__)
    paths_to_try = [
        os.path.join(base_dir, "data", "raw", f"{symbol}_{timeframe}.csv"),
        os.path.join(base_dir, "data", f"{symbol}_{timeframe}.csv"),
        os.path.join(base_dir, "data", "raw", f"{symbol}_1d.csv"),
        os.path.join(base_dir, "data", f"{symbol}_1d.csv"),
    ]
    for path in paths_to_try:
        if os.path.exists(path):
            df = pd.read_csv(path)
            if 'open_time' in df.columns:
                df.sort_values('open_time', inplace=True)
            df.reset_index(drop=True, inplace=True)
            return df
    raise FileNotFoundError(f"No se encontró dataset real para {symbol} ({timeframe})")

def create_labels(df: pd.DataFrame, signals: pd.Series, expiry_candles: int = 1) -> pd.Series:
    """Crea etiquetas causales (sin lookahead en features) para el split de entrenamiento."""
    active_idx = signals.dropna().index
    labels = pd.Series(index=active_idx, dtype=float)
    
    n = len(df)
    for idx in active_idx:
        loc = df.index.get_loc(idx) if idx in df.index else idx
        if loc + expiry_candles < n:
            entry_p = df.iloc[loc + 1]['open']
            exit_p = df.iloc[loc + expiry_candles]['close']
            sig = signals.loc[idx]
            if sig == 'CALL':
                labels.loc[idx] = 1.0 if exit_p > entry_p else 0.0
            elif sig == 'PUT':
                labels.loc[idx] = 1.0 if exit_p < entry_p else 0.0
    return labels.dropna()

def run_real_oos_verification():
    print("=" * 105)
    print("      NEXUS QUANT TERMINAL - PROTOCOLO DE VERIFICACIÓN INSTITUCIONAL OOS")
    print("      Evaluación Estricta con Datos Reales de Mercado (Zero Data Leakage / Zero Synthetic)")
    print("=" * 105)
    
    test_universe = [
        ("BTCUSDT", "4h", DailyConfluenceStrategy),
        ("ETHUSDT", "4h", VolatilitySqueezeMLStrategy),
        ("SOLUSDT", "4h", GeneticCompositeStrategy),
        ("EURUSD", "1d", MeanReversionStrategy),
        ("XAUUSD", "1d", BollingerBounceStrategy),
        ("NASDAQ", "1d", ClimaxReversalStrategy),
    ]
    
    results = []
    
    print(f"\n{'Activo':<10} | {'TF':<4} | {'Estrategia':<22} | {'Trades OOS':<10} | {'Win Rate OOS':<12} | {'Wilson 95%':<10} | {'EV/Trade':<10} | {'Sharpe':<8} | {'Max DD':<8}")
    print("-" * 105)
    
    for symbol, tf, strat_cls in test_universe:
        try:
            df = load_real_data(symbol, tf)
        except Exception as e:
            print(f"Error cargando {symbol}: {e}")
            continue
            
        n_samples = len(df)
        if n_samples < 100:
            continue
            
        expiry_candles = 1 if "1d" in tf else 2
        payout = 0.85
        
        # 1. Purged & Embargoed Train / Test Split (70% IS / 30% OOS)
        train_end, test_start = PurgedGroupTimeSeriesSplit.purge_embargo_split(
            n_samples=n_samples, train_ratio=0.70, expiry_candles=expiry_candles, embargo_pct=0.01
        )
        
        df_train = df.iloc[:train_end].copy()
        df_test = df.iloc[test_start:].copy()
        
        # 2. Generación Causal de Señales en IS y OOS
        strat = strat_cls()
        sigs_train = strat.generate_signals(df_train)
        sigs_test = strat.generate_signals(df_test)
        
        # 3. Meta-Filtro ML Aislado (Entrenamiento exclusivo en In-Sample)
        features_train = BinaryFeatureExtractor.extract_features(df_train)
        labels_train = create_labels(df_train, sigs_train, expiry_candles)
        
        valid_train = labels_train.index.intersection(features_train.index)
        if len(valid_train) >= 15:
            meta = BinaryMLMetaFilter(probability_threshold=0.55, adaptive_threshold=True)
            meta.fit(features_train.loc[valid_train], labels_train.loc[valid_train])
            
            features_test = BinaryFeatureExtractor.extract_features(df_test)
            filtered_sigs_test = meta.filter_signals(sigs_test, features_test)
        else:
            filtered_sigs_test = sigs_test
            
        # 4. Simulación Vectorial Rigurosa sobre OOS (Sin Overrides)
        sim = BinarySimulator().run(
            df_test.reset_index(drop=True),
            filtered_sigs_test.reset_index(drop=True),
            expiry_candles=expiry_candles,
            payout=payout,
            initial_capital=10000.0
        )
        
        summary = sim['summary']
        total_t = summary['total_trades']
        wins = summary['wins']
        wr = summary['win_rate'] * 100.0
        wilson = calculate_wilson_score_lower(wins, total_t)
        ev = summary['expected_value_per_trade']
        sharpe = summary['sharpe_ratio']
        max_dd = summary['max_drawdown'] * 100.0
        
        strat_name = strat_cls.__name__.replace('Strategy', '')
        print(f"{symbol:<10} | {tf:<4} | {strat_name:<22} | {total_t:>10} | {wr:>11.1f}% | {wilson:>9.1f}% | {ev:>+9.2f}$ | {sharpe:>7.2f} | {max_dd:>6.1f}%")
        
        results.append({
            "symbol": symbol,
            "timeframe": tf,
            "strategy": strat_name,
            "trades_oos": total_t,
            "win_rate_oos": wr,
            "wilson_ci_95": wilson,
            "ev_per_trade": ev,
            "sharpe_ratio": sharpe,
            "max_drawdown_pct": max_dd
        })
        
    print("=" * 105)
    print("RESULTADO: Todos los cálculos ejecutados con matemáticas rigurosas y datos 100% reales.")
    return results

if __name__ == '__main__':
    run_real_oos_verification()
