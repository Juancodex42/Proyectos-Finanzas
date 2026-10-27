# Guía Rápida - Bot Trading V2

## 1. Test del Framework de Backtesting (5 minutos)

### Ejecutar análisis completo con datos sintéticos

```bash
# Ejecutar desde la raíz del proyecto
python run_backtest.py --mode full --synthetic --days 30 \
    --capital 10000 --simulations 1000 --permutations 1000 --export
```

**Resultado esperado:**
```
BACKTEST REPORT - Mean Reversion
Total Return:          0.30%
Sharpe Ratio:          1.26
Win Rate:              36.6%
Total Trades:          350

MONTE CARLO SIMULATION
Mean Sharpe:           6.79
P(Profitable):         100.0%
P(Sharpe > 1.0):       100.0%

LUCK vs SKILL ANALYSIS
T-Statistic:           7.99
P-Value:               0.7650
```

Los reportes se guardan en `reports/`:
- `backtest_report_*.txt`
- `monte_carlo_report_*.txt`
- `luck_vs_skill_report_*.txt`
- `trades.csv`
- `equity_curve.csv`

---

## 2. Ejecutar Bot en Modo Continuo (Paper Trading)

### Ejecutar estrategias en loop

```bash
python main.py
```

El bot ejecutará:
1. Demo inicial (verificación de APIs y portfolio)
2. Loop continuo cada 60 segundos:
   - Statistical Arbitrage (USDT/ARS ↔ USDC/ARS)
   - Market Making (Avellaneda-Stoikov)
3. Guardado de estado cada 10 iteraciones

**Output esperado:**
```
[ITERATION 1] Running strategies...
[STAT ARB] Strategy initialized (enabled: True)
[MARKET MAKING] Strategy initialized (enabled: True)

[ITERATION 2] Running strategies...
[STAT ARB] Not enough data for signal
[MARKET MAKING] Not placing orders: Not enough market data

[ITERATION 10] Running strategies...
[STATE] State saved
```

---

## 3. Modos de Backtesting Disponibles

### a) Backtest Básico

```bash
python run_backtest.py --mode basic --synthetic --days 30 --strategy mean_reversion
```

**Métricas calculadas:**
- Total Return
- Sharpe Ratio
- Sortino Ratio
- Max Drawdown
- Win Rate
- Profit Factor
- VaR/CVaR

---

### b) Walk-Forward Analysis

```bash
python run_backtest.py --mode walk_forward --synthetic --days 90 \
    --train-window 30 --test-window 7 --num-folds 4
```

**Validación temporal:**
- Divide datos en 4 folds
- Entrena en cada período, testea en siguiente
- Promedia métricas para robustez

---

### c) Monte Carlo Simulation

```bash
python run_backtest.py --mode monte_carlo --synthetic --days 30 --simulations 1000
```

**Análisis de distribución:**
- 1000 simulaciones bootstrap
- Distribución de Sharpe ratio
- P(Sharpe > 1.0)
- Percentiles 5th-95th

---

### d) Luck vs Skill Detection

```bash
python run_backtest.py --mode luck_vs_skill --synthetic --days 30 --permutations 1000
```

**Significancia estadística:**
- Permutation testing
- T-statistic y p-value
- Distingue ventaja real vs azar

---

## 4. Configuración Rápida

### Editar config.json

```json
{
  "strategies": {
    "statistical_arbitrage": {
      "enabled": true,
      "allocation_pct": 0.40,
      "z_score_entry": 2.0,
      "z_score_exit": 0.5
    },
    "market_making": {
      "enabled": true,
      "allocation_pct": 0.30,
      "target_spread_bps": 50,
      "order_size_usd": 100
    }
  },
  "risk": {
    "max_posicion_individual": 0.20,
    "max_drawdown": 0.15,
    "var_95_limit": 0.10
  },
  "paper_trading": true
}
```

---

## 5. Estructura de Archivos Generados

```
bot_v2/
├── reports/
│   ├── backtest_report_Mean_Reversion_20260115_170122.txt
│   ├── monte_carlo_report_20260115_170123.txt
│   ├── luck_vs_skill_report_20260115_170123.txt
│   ├── trades.csv
│   └── equity_curve.csv
├── data/
│   ├── historical/         # Datos históricos (CSV)
│   └── state/
│       └── bot_state.json  # Estado persistente
└── logs/
    └── bot.log             # Logs de ejecución
```

---

## 6. Próximos Pasos Recomendados

### Paso 1: Validar Framework (HECHO ✅)
```bash
python run_backtest.py --mode full --synthetic --days 30
```

### Paso 2: Obtener Datos Históricos Reales
```bash
# Recolectar 30 días de datos de Ripio
# (Requiere implementar data collection desde API)
```

### Paso 3: Backtest con Datos Reales
```bash
python run_backtest.py --mode full --data data/historical/ripio_data.csv
```

### Paso 4: Paper Trading (7+ días)
```bash
python main.py  # Deja corriendo 7 días
```

### Paso 5: Evaluar Performance Paper Trading
- Sharpe > 2.0 ✅
- Win Rate > 60% ✅
- Min 100 trades ✅
- Max DD < 10% ✅

### Paso 6: Live Trading (Capital Mínimo $100)
```bash
# Editar config.json: "paper_trading": false
python main.py
```

---

## 7. Comandos Útiles

### Ver logs en tiempo real
```bash
tail -f logs/bot.log
```

### Ver estado guardado
```bash
cat data/state/bot_state.json | python -m json.tool
```

### Ver reportes recientes
```bash
ls -lt reports/ | head
```

### Limpiar reportes viejos
```bash
rm reports/*
```

---

## 8. Troubleshooting Rápido

### Error: Module not found
```bash
pip install -r requirements.txt
```

### Error: No module named 'src'
```bash
# Asegurarse de ejecutar los comandos desde el directorio raíz del proyecto
cd "Bot Trading Ripio Binance V2"
```

### Error: File not found (data)
```bash
# Crear directorios necesarios
mkdir -p data/historical data/state reports logs
```

---

## 9. Métricas Clave a Monitorear

### Performance
- **Sharpe Ratio > 1.5**: Bueno, > 2.0: Excelente
- **Win Rate > 55%**: Aceptable, > 60%: Bueno
- **Max Drawdown < 15%**: Control de riesgo OK

### Validación Estadística
- **P-value < 0.05**: Significativo (no es suerte)
- **T-statistic > 2.0**: Ventaja consistente
- **Consistency > 75%**: Robustez temporal

### Monte Carlo
- **P(Sharpe > 1.0) > 70%**: Alta confianza
- **Sharpe 5th percentile > 1.0**: Robusto en peor caso

---

## 10. Contacto y Soporte

- **Logs detallados**: `logs/bot.log`
- **Estado del bot**: `data/state/bot_state.json`
- **Reportes**: `reports/`

**Última actualización**: 2026-01-15
**Versión**: 2.0.0
