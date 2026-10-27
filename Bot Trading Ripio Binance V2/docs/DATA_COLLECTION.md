# Data Collection - Guía Completa

## Fuentes de Datos Evaluadas

### ✅ Ripio Trade API (ELEGIDA)

**Endpoint**: `/public/trades` y `/public/tickers/{pair}`

**Ventajas**:
- Datos directos del exchange que usarás
- Sin costo (endpoint público)
- No requiere autenticación
- Precisión máxima

**API Documentation**: [Ripio Trade API](https://apidocs.ripiotrade.co/)

**Rate Limits**:
- Sin verificar: 1 req/seg (86,400/día)
- Verificado: 3.5 req/seg (302,400/día)

---

### ❌ CoinGecko (descartada)

**Por qué NO**:
- No tiene pares argentinos (USDT_ARS, USDC_ARS)
- Solo exchanges globales

---

### ❌ CoinMarketCap (descartada)

**Por qué NO**:
- Tiene Ripio Coin (RCN), no los pares de trading
- No es útil para arbitraje USDT/USDC

---

## Collector Implementado

### Archivo Creado

**`collect_data.py`** - Script para recolectar datos de Ripio

### Qué Recolecta

Por cada timestamp (cada 5 minutos):
```csv
timestamp,USDT_ARS_bid,USDT_ARS_ask,USDT_ARS_mid,USDT_ARS_spread,USDC_ARS_bid,USDC_ARS_ask,USDC_ARS_mid,USDC_ARS_spread
2026-01-15 18:00:00,1500.50,1502.30,1501.40,1.80,1498.20,1500.10,1499.15,1.90
2026-01-15 18:05:00,1501.20,1503.00,1502.10,1.80,1498.80,1500.60,1499.70,1.80
...
```

**Datos por registro**:
- Timestamp
- Bid/Ask/Mid price (USDT_ARS)
- Spread (USDT_ARS)
- Bid/Ask/Mid price (USDC_ARS)
- Spread (USDC_ARS)

---

## Uso del Collector

### Modo 1: Continuous (RECOMENDADO)

```bash
python collect_data.py --mode continuous --interval 5
```

**Qué hace**:
- Recolecta indefinidamente
- Cada 5 minutos guarda snapshot
- Crea archivo nuevo cada día: `ripio_2026-01-15.csv`
- Presiona Ctrl+C para detener

**Ideal para**: Dejar corriendo 30+ días

---

### Modo 2: Timed

```bash
python collect_data.py --mode timed --days 30 --interval 5
```

**Qué hace**:
- Recolecta exactamente 30 días
- Se detiene automáticamente
- Total: 8,640 registros (30 días × 288 registros/día)

---

### Con Credenciales

**Opción A: Variables de entorno (.env)**
```bash
# En .env
RIPIO_API_TOKEN=your_token
RIPIO_SECRET_KEY=your_secret

# Ejecutar
python collect_data.py --mode continuous
```

**Opción B: Argumentos**
```bash
python collect_data.py --mode continuous \
    --api-token "your_token" \
    --secret-key "your_secret"
```

---

## Output

### Archivo Generado

```
data/historical/ripio_2026-01-15.csv
data/historical/ripio_2026-01-16.csv
data/historical/ripio_2026-01-17.csv
...
```

**Formato**: Un archivo CSV por día

---

### Logs

```
data/logs/data_collector.log
```

**Ejemplo**:
```
2026-01-15 18:00:00 - [COLLECTOR] Iteration 1
2026-01-15 18:00:00 - [PRICES] USDT: 1501.40, USDC: 1499.15, Ratio: 1.001501
2026-01-15 18:05:00 - [COLLECTOR] Iteration 2
2026-01-15 18:05:00 - [PRICES] USDT: 1502.10, USDC: 1499.70, Ratio: 1.001600
...
2026-01-15 22:00:00 - [STATS] Data points: 100, Errors: 0
```

---

## Cálculos Derivados

### Después de recolectar, puedes calcular:

```python
import pandas as pd

# Cargar datos
df = pd.read_csv('data/historical/ripio_2026-01-15.csv')

# Calcular ratio USDT/USDC
df['ratio'] = df['USDT_ARS_mid'] / df['USDC_ARS_mid']

# Calcular z-score
df['ratio_mean'] = df['ratio'].rolling(100).mean()
df['ratio_std'] = df['ratio'].rolling(100).std()
df['z_score'] = (df['ratio'] - df['ratio_mean']) / df['ratio_std']

# Ver oportunidades históricas
opportunities = df[abs(df['z_score']) > 2.0]
print(f"Oportunidades detectadas: {len(opportunities)}")
```

---

## Consolidar Múltiples Días

```python
import pandas as pd
from pathlib import Path

# Cargar todos los CSVs
data_dir = Path('data/historical')
files = sorted(data_dir.glob('ripio_*.csv'))

# Concatenar
dfs = [pd.read_csv(f) for f in files]
df_full = pd.concat(dfs, ignore_index=True)

# Guardar consolidado
df_full.to_csv('data/historical/ripio_full_30_days.csv', index=False)

print(f"Total registros: {len(df_full)}")
print(f"Período: {df_full['timestamp'].min()} → {df_full['timestamp'].max()}")
```

---

## Validación de Datos

### Script de validación

```python
import pandas as pd

df = pd.read_csv('data/historical/ripio_2026-01-15.csv')

# 1. Check valores faltantes
missing = df.isnull().sum()
print(f"Valores faltantes:\n{missing}")

# 2. Check frecuencia
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp')
df['time_diff'] = df['timestamp'].diff()
print(f"Frecuencia promedio: {df['time_diff'].mean()}")

# 3. Check spreads anormales
avg_spread_usdt = df['USDT_ARS_spread'].mean()
avg_spread_usdc = df['USDC_ARS_spread'].mean()
print(f"Spread promedio USDT: {avg_spread_usdt:.2f} ARS")
print(f"Spread promedio USDC: {avg_spread_usdc:.2f} ARS")

# 4. Check outliers (precios)
usdt_std = df['USDT_ARS_mid'].std()
usdt_outliers = df[abs(df['USDT_ARS_mid'] - df['USDT_ARS_mid'].mean()) > 3 * usdt_std]
print(f"Outliers USDT: {len(usdt_outliers)}")
```

---

## Troubleshooting

### Error: "Ripio API no responde"

**Causa**: Credenciales incorrectas o API caída

**Solución**:
```bash
# Verificar credenciales
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('RIPIO_API_TOKEN'))"

# Health check manual
python -c "from src.core.ripio_api import ProfessionalRipioAPI; import asyncio; api = ProfessionalRipioAPI('token', 'secret'); asyncio.run(api.init_session()); asyncio.run(api.health_check())"
```

---

### Error: "Rate limit exceeded"

**Causa**: Demasiadas requests por segundo

**Solución**:
```bash
# Aumentar intervalo a 10 minutos (seguro bajo rate limit)
python collect_data.py --mode continuous --interval 10
```

---

### Datos incompletos (NaN)

**Causa**: Ticker no disponible momentáneamente

**Solución**: Normal, el collector sigue. Al procesar datos:
```python
# Eliminar filas con NaN
df_clean = df.dropna()

# O interpolar
df['USDT_ARS_mid'] = df['USDT_ARS_mid'].interpolate()
```

---

## Próximos Pasos

### 1. Activar Collector (HOY)

```bash
# En una terminal separada dentro del directorio del proyecto
python collect_data.py --mode continuous --interval 5
```

**Dejarlo corriendo** 30 días

---

### 2. Monitorear (Diario)

```bash
# Ver cuántos datos tienes
ls -lh data/historical/

# Ver últimas líneas del log
tail -n 20 data/logs/data_collector.log
```

---

### 3. Después de 30 días

```bash
# Consolidar datos
python -c "import pandas as pd; from pathlib import Path; files = sorted(Path('data/historical').glob('ripio_*.csv')); df = pd.concat([pd.read_csv(f) for f in files]); df.to_csv('data/historical/ripio_full.csv', index=False); print(f'Total: {len(df)} records')"

# Backtest
python run_backtest.py --mode full --data data/historical/ripio_full.csv
```

---

## Recursos

**API Documentation**:
- [Ripio Trade API Docs](https://apidocs.ripiotrade.co/)
- [Ripio GitHub Examples](https://github.com/ripio/trade)

**Data Analysis**:
- [CoinGecko OHLC Guide](https://www.coingecko.com/learn/ohlcv-candlestick-chart-python-streamlit)
- [CoinAPI OHLCV Blog](https://www.coinapi.io/blog/understanding-ohlcv-in-market-data-analysis)

---

**Última actualización**: 2026-01-15

**Status**: ✅ Collector implementado y listo para usar
