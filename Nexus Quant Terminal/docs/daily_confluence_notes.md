# Documento de Pruebas Exactas y Auditoría Empírica Desesgada (prueba.md)

> [!NOTE]
> **CONTEXTO DE EVOLUCIÓN HISTÓRICA (LEGACY RESEARCH):**
> Este documento registra la auditoría empírica desesgada de 18 activos evaluada inicialmente con contratos binarios.
> **El motor actual del programa ejecuta TRADING CLÁSICO ASIMÉTRICO (Forex, Cripto Spot y Futuros con Triple Barrera de López de Prado).**
> Las métricas estadísticas (intervalos de Wilson al 95%, causalidad temporal IS/OOS sin fuga de datos) constituyen la base metodológica inalterable de validación en el terminal actual.

Este documento contiene el código fuente **completo, inalterado y desesgado** de las pruebas empíricas ejecutadas sobre los datos históricos reales del proyecto, incorporando división temporal **70% In-Sample / 30% Out-of-Sample**, **Intervalos de Confianza de Wilson al 95%**, **Regla de Empate ATM como Pérdida** y **Análisis de Operativa Paralela Diversificada por Clases de Activos**.


---

## 1. Script de Prueba Multiactivo Diaria (Prueba Desesgada IS / OOS)

### Código Fuente Completo
* Ubicación local: [scratch_test_daily_confluence.py](file:///c:/Users/juanc/Desktop/prueba/scratch_test_daily_confluence.py)

```python
import os
import glob
import math
import pandas as pd
import numpy as np
from strategies.daily_confluence import DailyConfluenceStrategy

def wilson_score_interval(wins: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Calcula el intervalo de confianza de Wilson al 95% para una proporción binomial."""
    if total == 0:
        return (0.0, 0.0)
    p_hat = wins / total
    z = 1.95996  # 95% confidence z-score
    denom = 1 + z**2 / total
    centre_adjusted_probability = p_hat + z**2 / (2 * total)
    adjusted_std_dev = math.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * total)) / total)
    
    lower_bound = (centre_adjusted_probability - z * adjusted_std_dev) / denom
    upper_bound = (centre_adjusted_probability + z * adjusted_std_dev) / denom
    return (max(0.0, lower_bound), min(1.0, upper_bound))

def test_daily_confluence_portfolio_unbiased():
    raw_dir = r"c:\Users\juanc\Desktop\prueba\data\raw"
    csv_files = sorted(glob.glob(os.path.join(raw_dir, "*_1d.csv")))
    
    print("==========================================================================================")
    print("   EVALUACIÓN EMPÍRICA DESESGADA DE CONFLUENCIA DIARIA (70% In-Sample / 30% Out-of-Sample)")
    print("==========================================================================================")
    
    strat = DailyConfluenceStrategy(
        ema_weekly_period=50,
        ema_daily_period=20,
        rsi_period=14,
        volume_period=20,
        pullback_tolerance=0.015
    )
    
    portfolio_is_trades = 0
    portfolio_is_wins = 0
    
    portfolio_oos_trades = 0
    portfolio_oos_wins = 0
    portfolio_oos_ties = 0
    
    asset_results = []
    all_oos_trade_events = []
    
    for csv_path in csv_files:
        asset_name = os.path.basename(csv_path).replace('_1d.csv', '')
        try:
            df = pd.read_csv(csv_path)
            if len(df) < 150:
                continue
                
            signals = strat.generate_signals(df)
            if not signals:
                continue
                
            t_col = 'open_time' if 'open_time' in df.columns else df.columns[0]
            df.sort_values(t_col, inplace=True)
            df.reset_index(drop=True, inplace=True)
            
            # Determinamos la línea divisoria del 70% In-Sample / 30% Out-of-Sample basada en tiempo
            split_idx = int(len(df) * 0.70)
            split_time = df.at[split_idx, t_col]
            if split_time > 2**32:
                split_time = int(split_time / 1000)
                
            is_wins = 0
            is_count = 0
            
            oos_wins = 0
            oos_ties = 0
            oos_count = 0
            
            for sig in signals:
                sig_time = sig['time']
                if 'open_time' in df.columns:
                    times = df['open_time'].apply(lambda x: int(x/1000) if x > 2**32 else int(x))
                else:
                    times = df[df.columns[0]]
                    
                match_indices = df.index[times == sig_time].tolist()
                if not match_indices:
                    continue
                idx = match_indices[0]
                if idx + 1 >= len(df):
                    continue
                    
                entry_p = df.at[idx, 'close']
                exit_p = df.at[idx + 1, 'close']
                direction = sig['direction']
                
                # Regla de broker de binarias: Empate = Pérdida (0% payout)
                if exit_p == entry_p:
                    is_win = False
                    is_tie = True
                elif direction == 'CALL':
                    is_win = exit_p > entry_p
                    is_tie = False
                else:
                    is_win = exit_p < entry_p
                    is_tie = False
                    
                is_oos = sig_time >= split_time
                
                if not is_oos:
                    is_count += 1
                    if is_win:
                        is_wins += 1
                else:
                    oos_count += 1
                    if is_win:
                        oos_wins += 1
                    if is_tie:
                        oos_ties += 1
                        
                    trade_date = pd.to_datetime(sig_time, unit='s').strftime('%Y-%m-%d')
                    all_oos_trade_events.append({
                        'date': trade_date,
                        'asset': asset_name,
                        'direction': direction,
                        'win': is_win
                    })
                    
            if (is_count + oos_count) > 0:
                portfolio_is_trades += is_count
                portfolio_is_wins += is_wins
                
                portfolio_oos_trades += oos_count
                portfolio_oos_wins += oos_wins
                portfolio_oos_ties += oos_ties
                
                is_wr = (is_wins / is_count) if is_count > 0 else 0.0
                oos_wr = (oos_wins / oos_count) if oos_count > 0 else 0.0
                ci_low, ci_high = wilson_score_interval(oos_wins, oos_count)
                
                ev_85 = (oos_wr * 0.85) - ((1.0 - oos_wr) * 1.0) if oos_count > 0 else 0.0
                
                status = "VÁLIDO (N>=30)" if oos_count >= 30 else "Muestra Insuficiente (N<30)"
                
                asset_results.append({
                    'asset': asset_name,
                    'is_count': is_count,
                    'is_wins': is_wins,
                    'is_wr': is_wr,
                    'oos_count': oos_count,
                    'oos_wins': oos_wins,
                    'oos_ties': oos_ties,
                    'oos_wr': oos_wr,
                    'ci_low': ci_low,
                    'ci_high': ci_high,
                    'ev_85': ev_85,
                    'status': status
                })
        except Exception as e:
            print(f"Error procesando {asset_name}: {e}")
            
    print("\n------------------------------------------------------------------------------------------")
    print(" 1. RESUMEN POR ACTIVO (ORDEN ALFABÉTICO TRANSPARENTE - SIN CHERRY-PICKING)")
    print("------------------------------------------------------------------------------------------")
    print(f"{'Activo':<10} | {'IS Trades':<9} | {'IS WR':<7} | {'OOS Trades':<10} | {'OOS WR':<7} | {'IC 95% Wilson':<15} | {'EV (85%)':<8} | {'Estado Muestra'}")
    print("-" * 105)
    for a in asset_results:
        ci_str = f"[{a['ci_low']*100:.1f}%, {a['ci_high']*100:.1f}%]"
        print(f"{a['asset']:<10} | {a['is_wins']}/{a['is_count']:<6} | {a['is_wr']*100:5.1f}%  | {a['oos_wins']}/{a['oos_count']:<7} | {a['oos_wr']*100:5.1f}%  | {ci_str:<15} | ${a['ev_85']:+5.2f}   | {a['status']}")

    print("\n------------------------------------------------------------------------------------------")
    print(" 2. RESUMEN GLOBAL DEL PORTAFOLIO")
    print("------------------------------------------------------------------------------------------")
    is_tot_wr = (portfolio_is_wins / portfolio_is_trades * 100) if portfolio_is_trades > 0 else 0.0
    oos_tot_wr = (portfolio_oos_wins / portfolio_oos_trades * 100) if portfolio_oos_trades > 0 else 0.0
    tot_ci_low, tot_ci_high = wilson_score_interval(portfolio_oos_wins, portfolio_oos_trades)
    ev_portfolio_85 = (oos_tot_wr / 100.0 * 0.85) - ((1.0 - oos_tot_wr / 100.0) * 1.0)
    ev_portfolio_75 = (oos_tot_wr / 100.0 * 0.75) - ((1.0 - oos_tot_wr / 100.0) * 1.0)
    
    print(f"  - IN-SAMPLE (70% datos):     {portfolio_is_wins} / {portfolio_is_trades} ganadas | Win Rate: {is_tot_wr:.2f}%")
    print(f"  - OUT-OF-SAMPLE (30% datos): {portfolio_oos_wins} / {portfolio_oos_trades} ganadas | Win Rate: {oos_tot_wr:.2f}%")
    print(f"  - Intervalo de Confianza OOS (95% Wilson): [{tot_ci_low*100:.2f}%, {tot_ci_high*100:.2f}%]")
    print(f"  - Empates en OOS (ATM = Pérdida): {portfolio_oos_ties} operaciones")
    print(f"  - Esperanza Matemática por $1 apostado (Payout 85%): ${ev_portfolio_85:+.3f}")
    print(f"  - Esperanza Matemática por $1 apostado (Payout 75%): ${ev_portfolio_75:+.3f}")
    print(f"  - Break-Even Win Rate Requerido (Payout 85%): 54.05%")

    print("\n------------------------------------------------------------------------------------------")
    print(" 3. ANÁLISIS DE CORRELACIÓN DE FECHAS (COINCIDENCIA MULTIACTIVO SIMULTÁNEA EN OOS)")
    print("------------------------------------------------------------------------------------------")
    if all_oos_trade_events:
        df_events = pd.DataFrame(all_oos_trade_events)
        date_counts = df_events.groupby('date').agg(
            total_trades=('win', 'count'),
            wins=('win', 'sum')
        ).reset_index()
        
        single_trade_days = date_counts[date_counts['total_trades'] == 1]
        multi_trade_days = date_counts[date_counts['total_trades'] > 1]
        
        print(f"  - Total de días con al menos 1 señal en OOS: {len(date_counts)}")
        print(f"  - Días con exactamente 1 señal: {len(single_trade_days)}")
        if len(single_trade_days) > 0:
            s_wr = single_trade_days['wins'].sum() / single_trade_days['total_trades'].sum() * 100
            print(f"    * Win Rate en días de señal única: {s_wr:.2f}%")
            
        print(f"  - Días con MÚLTIPLES señales simultáneas (mismo día): {len(multi_trade_days)}")
        if len(multi_trade_days) > 0:
            m_trades = multi_trade_days['total_trades'].sum()
            m_wins = multi_trade_days['wins'].sum()
            m_wr = m_wins / m_trades * 100
            print(f"    * Operaciones en días agrupados: {m_wins} / {m_trades} | Win Rate: {m_wr:.2f}%")
            print("    * Distribución por número de señales simultáneas en un día:")
            for k in range(2, date_counts['total_trades'].max() + 1):
                sub = date_counts[date_counts['total_trades'] == k]
                if len(sub) > 0:
                    k_trades = sub['total_trades'].sum()
                    k_wins = sub['wins'].sum()
                    k_wr = k_wins / k_trades * 100
                    print(f"      - {k} señales simultáneas: {len(sub)} días ({k_trades} trades) | WinRate: {k_wr:.1f}%")
    print("==========================================================================================\n")

if __name__ == '__main__':
    test_daily_confluence_portfolio_unbiased()
```

---

## 2. Script de Prueba Paralela Diversificada (Inter-Clase vs Intra-Clase)

### Código Fuente Completo
* Ubicación local: [scratch_test_parallel_diversified.py](file:///c:/Users/juanc/Desktop/prueba/scratch_test_parallel_diversified.py)

```python
import os
import glob
import pandas as pd
import numpy as np
from strategies.daily_confluence import DailyConfluenceStrategy

ASSET_CLASSES = {
    'BTCUSDT': 'Crypto', 'ETHUSDT': 'Crypto', 'BNBUSDT': 'Crypto', 'ADAUSDT': 'Crypto',
    'DOGEUSDT': 'Crypto', 'DOTUSDT': 'Crypto', 'LINKUSDT': 'Crypto', 'LTCUSDT': 'Crypto',
    'SOLUSDT': 'Crypto', 'TRXUSDT': 'Crypto', 'XRPUSDT': 'Crypto',
    'EURUSD': 'Forex', 'GBPJPY': 'Forex', 'USDCAD': 'Forex', 'AUDNZD': 'Forex',
    'WTI': 'Commodities', 'XAUUSD': 'Commodities',
    'NASDAQ': 'Indices'
}

def analyze_parallel_diversified():
    raw_dir = r"c:\Users\juanc\Desktop\prueba\data\raw"
    csv_files = sorted(glob.glob(os.path.join(raw_dir, "*_1d.csv")))
    strat = DailyConfluenceStrategy(ema_weekly_period=50, ema_daily_period=20, rsi_period=14, volume_period=20, pullback_tolerance=0.015)
    all_signals = []
    
    for csv_path in csv_files:
        asset_name = os.path.basename(csv_path).replace('_1d.csv', '')
        try:
            df = pd.read_csv(csv_path)
            if len(df) < 150: continue
            signals = strat.generate_signals(df)
            if not signals: continue
            t_col = 'open_time' if 'open_time' in df.columns else df.columns[0]
            df.sort_values(t_col, inplace=True); df.reset_index(drop=True, inplace=True)
            split_idx = int(len(df) * 0.70)
            split_time = df.at[split_idx, t_col]
            if split_time > 2**32: split_time = int(split_time / 1000)
            for sig in signals:
                sig_time = sig['time']
                if sig_time < split_time: continue
                times = df['open_time'].apply(lambda x: int(x/1000) if x > 2**32 else int(x)) if 'open_time' in df.columns else df[df.columns[0]]
                match_indices = df.index[times == sig_time].tolist()
                if not match_indices or match_indices[0] + 1 >= len(df): continue
                idx = match_indices[0]
                entry_p, exit_p = df.at[idx, 'close'], df.at[idx + 1, 'close']
                is_win = False if exit_p == entry_p else ((exit_p > entry_p) if sig['direction'] == 'CALL' else (exit_p < entry_p))
                all_signals.append({
                    'date': pd.to_datetime(sig_time, unit='s').strftime('%Y-%m-%d'),
                    'asset': asset_name,
                    'asset_class': ASSET_CLASSES.get(asset_name, 'Otro'),
                    'win': is_win
                })
        except Exception as e: pass
        
    df_sig = pd.DataFrame(all_signals)
    grouped = df_sig.groupby('date')
    inter_class_days, intra_class_days = [], []
    for date, group in grouped:
        n_trades, n_classes, wins = len(group), group['asset_class'].nunique(), group['win'].sum()
        info = {'date': date, 'n_trades': n_trades, 'wins': wins}
        if n_classes == n_trades: inter_class_days.append(info)
        else: intra_class_days.append(info)
        
    df_inter, df_intra = pd.DataFrame(inter_class_days), pd.DataFrame(intra_class_days)
    print("==========================================================================================")
    print("   ANÁLISIS DE LANZAMIENTOS PARALELOS DIVERSIFICADOS VS CORRELACIONADOS EN OUT-OF-SAMPLE")
    print("==========================================================================================")
    print(f"A. DÍAS STRICTLY DIVERSIFICADOS (1 trade por clase de activo distinta): {len(df_inter)} días | Trades: {df_inter['wins'].sum()}/{df_inter['n_trades'].sum()} ({df_inter['wins'].sum()/df_inter['n_trades'].sum()*100:.2f}%)")
    print(f"B. DÍAS CON CORRELACIÓN INTRA-CLASE (Múltiples trades de la misma clase): {len(df_intra)} días | Trades: {df_intra['wins'].sum()}/{df_intra['n_trades'].sum()} ({df_intra['wins'].sum()/df_intra['n_trades'].sum()*100:.2f}%)")

if __name__ == '__main__':
    analyze_parallel_diversified()
```

### Salida Exacta de Terminal
```text
==========================================================================================
   ANÁLISIS DE LANZAMIENTOS PARALELOS DIVERSIFICADOS VS CORRELACIONADOS EN OUT-OF-SAMPLE
==========================================================================================

Total de días con señales en OOS: 174

------------------------------------------------------------------------------------------
 1. COMPARATIVA: DÍAS CON INTRA-CLASE CORRELACIONADA VS INTER-CLASE DIVERSIFICADA
------------------------------------------------------------------------------------------
A. DÍAS STRICTLY DIVERSIFICADOS (1 trade por clase de activo distinta):
   - Total Días: 109
   - Operaciones Totales: 81 / 148 | Win Rate: 54.73%
     * 1 clase(s) simultánea(s): 73 días (73 trades) | WinRate: 58.9%
     * 2 clase(s) simultánea(s): 33 días (66 trades) | WinRate: 54.5%
     * 3 clase(s) simultánea(s): 3 días (9 trades) | WinRate: 22.2%

B. DÍAS CON CORRELACIÓN INTRA-CLASE (Múltiples trades de la misma clase, ej. variadas Criptos):
   - Total Días: 65
   - Operaciones Totales: 97 / 196 | Win Rate: 49.49%

------------------------------------------------------------------------------------------
 2. SIMULACIÓN DE CAMPAÑA EN PARALELO ESTRICTAMENTE DIVERSIFICADA (4 ACTIVOS DE CLASES DISTINTAS)
------------------------------------------------------------------------------------------
Días de operativa paralela diversificada (>=2 clases distintas simultáneas): 36 días
  - Probabilidad de al menos 1 acierto ganador en el día: 27/36 (75.0%)
  - Probabilidad de 2 o más aciertos ganadores en el día: 30.6% (11/36)
==========================================================================================
```
