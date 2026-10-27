# 🏗️ ARQUITECTURA DEL BOT V2.0

## 📊 VISION GENERAL

Bot de trading cuantitativo de nivel institucional diseñado para operar en el mercado argentino de criptomonedas (Ripio Trade), con fundamentos científicos rigurosos y validación estadística.

---

## 🎯 OBJETIVOS DE DISEÑO

### **Principios Fundamentales:**

1. **Rigor Científico**
   - Toda estrategia debe ser validada con p-value < 0.01
   - Monte Carlo Walk-Forward con 1000+ simulaciones
   - Cross-validation temporal (no spatial por limitación de pares)
   - Luck vs Skill testing mediante permutaciones

2. **Gestión de Riesgo Institucional**
   - Value at Risk (VaR) 95% confidence < 2%
   - Max Drawdown < 15%
   - Exposure limits por moneda (ARS < 30%, Crypto < 20%)
   - Position sizing dinámico basado en volatilidad

3. **Ejecución Profesional**
   - Rate limiting preventivo (no reactivo)
   - Connection pooling para eficiencia
   - Atomic state persistence
   - Triple validación anti-taker (evitar 0.30% fee)

---

## 🏛️ ARQUITECTURA DE CAPAS

```
┌─────────────────────────────────────────────────────┐
│              ORCHESTRATOR LAYER                      │
│                   main.py                            │
│  - Inicialización                                    │
│  - Shutdown graceful                                 │
│  - Loop de estrategias                               │
└──────────────────┬──────────────────────────────────┘
                   │
       ┌───────────┴────────────┬──────────────────────┐
       │                        │                       │
┌──────▼──────┐     ┌──────────▼──────┐    ┌─────────▼────────┐
│   CORE      │     │   STRATEGIES    │    │   ANALYTICS      │
│   LAYER     │     │     LAYER       │    │     LAYER        │
├─────────────┤     ├─────────────────┤    ├──────────────────┤
│ • APIs      │     │ • Stat Arb      │    │ • Portfolio Mgr  │
│ • Config    │     │ • Market Making │    │ • Risk Manager   │
│ • State     │     │ • Triangular    │    │ • Backtester     │
└─────────────┘     └─────────────────┘    └──────────────────┘
       │                    │                       │
       └────────────────────┴───────────────────────┘
                            │
                ┌───────────▼───────────┐
                │   EXECUTION LAYER     │
                ├───────────────────────┤
                │ • Smart Order Sizing  │
                │ • TWAP Executor       │
                │ • VWAP Executor       │
                │ • Iceberg Orders      │
                │ • Adaptive Timing     │
                └───────────────────────┘
```

---

## 📦 COMPONENTES DETALLADOS

### **1. CORE LAYER**

#### **ripio_api.py** - Professional API Client
```python
Features:
- Rate limiting preventivo
  * Public: 100 requests/min
  * Private: 50 requests/min
- Connection pooling (TCPConnector)
- Exponential backoff retry
- Request tracking & statistics
- Health checks
- HMAC-SHA256 authentication

Key Methods:
- get_ticker(pair)
- get_orderbook(pair, depth)
- get_balance()
- place_order(side, type, pair, amount, price)
- cancel_order(order_id)
- health_check()
```

**Design Pattern:** Singleton + Async Context Manager

**Rate Limiting Algorithm:**
```python
def _wait_for_rate_limit(endpoint_type):
    # Limpia requests fuera de ventana
    now = time.time()
    while requests and requests[0] < now - window:
        requests.popleft()

    # Si excede límite, espera
    if len(requests) >= limit:
        wait_time = window - (now - requests[0])
        await asyncio.sleep(wait_time)

    # Registra request
    requests.append(now)
```

---

#### **config_loader.py** - Configuration Management

```python
Sources:
1. .env - Credenciales sensibles
   * BOT_TOKEN, CHAT_ID
   * RIPIO_API_TOKEN, RIPIO_SECRET_KEY
   * TRADING_MODE (paper/live)
   * CAPITAL_INICIAL

2. trading_config.yaml - Configuración de trading
   * Pairs, Fees, Execution
   * Portfolio limits
   * Risk parameters
   * Strategy configs
   * Validation criteria

Features:
- Dot notation getter (config.get('risk.max_drawdown_pct'))
- Configuration validation
- Strategy-specific configs
```

**Validation Rules:**
- Maker fee < Taker fee
- Max drawdown < 30%
- Total strategy allocation = 100%
- Sharpe mínimo >= 1.0

---

#### **state_manager.py** - Persistent State

```python
State Structure:
{
    'capital': float,
    'inventario': {moneda: cantidad},
    'ordenes_activas': [order_ids],
    'trades_dia': int,
    'ultimo_trade': timestamp,
    'pnl_por_estrategia': {
        'statistical_arbitrage': {'pnl': float, 'num_trades': int},
        'market_making': {'pnl': float, 'num_trades': int}
    }
}

Features:
- Atomic writes (temp file → rename)
- Automatic backup (daily)
- Load on startup
- Save every 10 iterations
```

**Atomic Write Algorithm:**
```python
def save_state():
    temp_file = state_file.with_suffix('.tmp')

    # Write to temp
    with open(temp_file, 'w') as f:
        json.dump(state, f)

    # Atomic rename (OS-level)
    temp_file.replace(state_file)
```

---

### **2. STRATEGIES LAYER**

#### **statistical_arbitrage.py** - Pairs Trading

**Fundamento Teórico:**
```
USDT y USDC son stablecoins → deberían mantener paridad 1:1

Si ratio = USDT_price / USDC_price se desvía:
- ratio > 1.02 → USDT sobrevaluado → VENDER USDT, COMPRAR USDC
- ratio < 0.98 → USDT subvaluado → COMPRAR USDT, VENDER USDC

Mean reversion: ratio tiende a volver a 1.0
```

**Algoritmo de Señal:**
```python
1. Calcular ratio history (100 observaciones)
2. Calcular z-score = (ratio - mean) / std
3. Verificar cointegración (autocorr lag-1)
4. Verificar spread > min_spread_bps

Señales:
IF z_score > 2.0 AND spread > 10bps AND cointegrated:
    → OPEN LONG USDC (apostar ratio baja)

IF z_score < -2.0 AND spread > 10bps AND cointegrated:
    → OPEN LONG USDT (apostar ratio sube)

IF |z_score| < 0.5:
    → CLOSE position
```

**Position Sizing:**
```python
position_size = (
    total_capital
    × allocation_pct
    × signal_strength
    × max_position_pct
)

signal_strength = min(|z_score| / 3.0, 1.0)
```

**P&L Calculation:**
```python
if position == 'long_usdt':
    pnl_pct = (ratio_exit / ratio_entry - 1.0) × 100

if position == 'long_usdc':
    pnl_pct = (ratio_entry / ratio_exit - 1.0) × 100
```

---

#### **market_making.py** - Avellaneda-Stoikov Model

**Fundamento Teórico (Paper 2008):**
```
Market maker coloca bid y ask simultáneamente para capturar spread.
Debe gestionar:
1. Inventory risk (no acumular demasiado USDT)
2. Adverse selection (no ser picked off)
3. Spread optimization (balance entre volumen y profit)
```

**Modelo Matemático:**
```python
mid = (best_bid + best_ask) / 2

# Calcular penalty por inventario
q_normalized = inventory_usd / max_inventory_usd  # [-1, +1]
inventory_penalty = gamma × q_normalized × sigma²

# Calcular spread óptimo
base_spread = target_spread_bps / 10000 × mid
volatility_multiplier = 1.0 + (sigma / 0.5)
optimal_spread = base_spread × volatility_multiplier

# Quotes finales
bid = mid - spread/2 - inventory_penalty
ask = mid + spread/2 + inventory_penalty
```

**Inventory Skewing:**
```
Si inventory > 0 (long USDT):
- Subir bid → evitar comprar más
- Bajar ask → fomentar vender

Si inventory < 0 (short USDT):
- Bajar bid → fomentar comprar
- Subir ask → evitar vender más
```

**Volatility Calculation:**
```python
returns = np.diff(np.log(prices))
volatility = np.std(returns)
volatility_annual = volatility × sqrt(288 × 365)
```

---

### **3. ANALYTICS LAYER**

#### **portfolio_manager.py** - Multi-Currency Portfolio

```python
Tracked Assets:
- USDT, USDC (stablecoins)
- ARS (fiat)
- BTC, ETH (crypto)

Features:
- Real-time inventory sync
- USD-equivalent valuation
- Exposure calculation per currency
- Limit validation
- Rebalancing signals
- P&L by strategy

Exposure Limits:
- ARS max 30% (riesgo devaluación)
- USDT + USDC max 80% (stables)
- BTC + ETH max 20% (volátiles)
```

**Rebalancing Logic:**
```python
Target: 50% USDT / 50% USDC / 0% ARS

IF exposure_ARS > 10%:
    → Convert ARS → stablecoins

IF exposure_USDT > 65%:
    → Convert USDT → USDC

IF exposure_USDC > 65%:
    → Convert USDC → USDT
```

---

## 🔄 FLUJO DE EJECUCIÓN

### **Startup Sequence:**
```
1. Load Config
   ├─ .env (credentials)
   └─ trading_config.yaml

2. Init APIs
   ├─ Ripio API (with session)
   ├─ Binance API (reference prices)
   └─ Health checks

3. Init State Manager
   ├─ Load or create state
   └─ Restore capital/positions

4. Init Portfolio Manager
   ├─ Sync inventory from API
   ├─ Calculate USD values
   └─ Validate exposure limits

5. Init Strategies
   ├─ Statistical Arbitrage
   └─ Market Making

6. Run Demo (once)
   └─ Test all components

7. Enter Loop
   └─ Run strategies every 60s
```

---

### **Strategy Loop (every 60s):**
```
ITERATION N:
├─ 1. Update Market Data
│   ├─ Get tickers (USDT/ARS, USDC/ARS)
│   ├─ Get orderbooks
│   └─ Store in price history
│
├─ 2. Update Portfolio
│   ├─ Sync balances from API
│   ├─ Calculate USD values
│   └─ Check exposure limits
│
├─ 3. Statistical Arbitrage
│   ├─ Update price history
│   ├─ Calculate z-score
│   ├─ Check cointegration
│   ├─ Generate signal
│   └─ Execute if signal exists
│
├─ 4. Market Making
│   ├─ Update market data
│   ├─ Calculate volatility
│   ├─ Update inventory
│   ├─ Calculate optimal quotes
│   ├─ Cancel old orders
│   └─ Place new orders
│
└─ 5. Housekeeping (every 10 iterations)
    ├─ Save state
    ├─ Backup state
    └─ Log statistics
```

---

## 📊 DATA STRUCTURES

### **Price History (Statistical Arb):**
```python
price_history_usdt: deque[float]  # maxlen=100
price_history_usdc: deque[float]  # maxlen=100
ratio_history: deque[float]       # maxlen=100

# Example:
ratio_history = [1.001, 1.002, 0.998, 1.003, ...]
z_score = (ratio[-1] - mean(ratio)) / std(ratio)
```

### **Market Data (Market Making):**
```python
price_history: deque[dict]  # maxlen=100
{
    'timestamp': datetime,
    'mid': float,
    'bid': float,
    'ask': float,
    'spread_bps': float
}

mid_prices: deque[float]  # for volatility calc
```

### **Portfolio State:**
```python
inventario: Dict[str, float] = {
    'USDT': 50.0,
    'USDC': 30.0,
    'ARS': 50000.0,
    'BTC': 0.001,
    'ETH': 0.01
}

precios_usd: Dict[str, float] = {
    'USDT': 1.0,
    'USDC': 1.0,
    'ARS': 0.0008,  # 1/1250
    'BTC': 97000.0,
    'ETH': 3500.0
}
```

---

## 🛡️ RISK MANAGEMENT

### **Position Limits:**
```python
risk_limits = {
    'max_perdida_por_operacion_pct': 0.02,    # 2% del capital
    'max_posicion_individual': 0.20,          # 20% del capital
    'max_exposicion_simultanea': 0.50,        # 50% del capital
    'max_perdida_diaria': 0.05,               # 5% del capital
    'max_drawdown_pct': 0.15,                 # 15% desde peak
    'var_limite_pct': 0.02                    # VaR 95% < 2%
}
```

### **Stop Loss Logic:**
```python
# Per-trade stop
IF pnl_trade < -0.02 × position_size:
    → CLOSE_POSITION()

# Daily stop
IF pnl_day < -0.05 × capital:
    → STOP_TRADING_FOR_TODAY()

# Drawdown stop
IF (capital_peak - capital_current) / capital_peak > 0.15:
    → PAUSE_BOT()
    → ALERT_USER()
```

---

## 📈 MÉTRICAS CLAVE

### **Statistical Arbitrage:**
```
Target Metrics:
- Sharpe Ratio: > 2.5
- Win Rate: > 65%
- Max Drawdown: < 10%
- Avg Trade Duration: 2-6 hours
- Trades/day: 2-5
- P-value cointegration: < 0.05
```

### **Market Making:**
```
Target Metrics:
- Sharpe Ratio: > 2.0
- Win Rate: > 60%
- Inventory turnover: 10-20 trades/day
- Avg spread captured: 30-50 bps
- Max inventory: < $500
- Uptime: > 95%
```

---

## 🔍 TESTING & VALIDATION

### **Unit Tests:** (test_bot.py - 45 tests)
```
1. Estructura de archivos (13 tests)
2. Configuración (11 tests)
3. APIs (7 tests)
4. State Manager (5 tests)
5. Portfolio Manager (6 tests)
6. Strategies (3 tests)
```

### **Integration Tests:**
```
- Demo mode (run_demo)
- Strategy loop (run_strategies_loop)
- State persistence
- API rate limiting
```

### **Backtesting Framework:** (TODO)
```
1. Monte Carlo Walk-Forward
   - 1000 simulations
   - Bootstrap sampling
   - Sharpe distribution

2. Temporal Cross-Validation
   - 4 folds
   - Rolling window
   - Out-of-sample testing

3. Luck vs Skill
   - Permutation tests
   - T-statistic analysis
   - Hurst exponent
```

---

## 🚀 DEPLOYMENT

### **Modes:**

**1. Development:**
```bash
TRADING_MODE=development
# - Solo logging
# - No ejecuta órdenes
# - Testing rápido
```

**2. Paper Trading:**
```bash
TRADING_MODE=paper_trading
# - Simula órdenes
# - Tracking de P&L virtual
# - Validación previa a live
```

**3. Live Trading:**
```bash
TRADING_MODE=live_trading
# - Órdenes reales
# - Capital real en riesgo
# - Requiere validación previa
```

---

## 📁 FILE STRUCTURE

```
bot_v2/
├── config/
│   ├── trading_config.yaml      # Trading configuration
│   └── .env.example             # Credentials template
│
├── data/
│   ├── logs/
│   │   └── bot.log              # Rotating logs
│   ├── state/
│   │   ├── bot_state.json       # Current state
│   │   └── bot_state_backup_*   # Daily backups
│   └── historical/
│       └── orderbook_*.csv      # Historical data
│
├── src/
│   ├── core/
│   │   ├── ripio_api.py         # [521 lines]
│   │   ├── binance_api.py       # [107 lines]
│   │   ├── config_loader.py     # [207 lines]
│   │   └── state_manager.py     # [178 lines]
│   │
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── statistical_arbitrage.py  # [430 lines]
│   │   └── market_making.py          # [395 lines]
│   │
│   ├── analytics/
│   │   └── portfolio_manager.py # [327 lines]
│   │
│   └── execution/  # TODO
│       ├── smart_order_sizing.py
│       ├── twap_executor.py
│       └── iceberg_executor.py
│
├── tests/
│   └── test_bot.py              # [425 lines] 45 tests
│
├── main.py                       # [355 lines] Orchestrator
├── requirements.txt
├── README.md
├── TESTING_GUIDE.md
└── ARQUITECTURA.md              # This file
```

**Total Lines of Code:** ~2,950 lines (sin execution layer)

---

## 🎯 ROADMAP

### **FASE 1: Fundamentos ✅ (COMPLETO)**
- [x] Core layer (APIs, Config, State)
- [x] Portfolio Manager
- [x] Statistical Arbitrage
- [x] Market Making
- [x] Test suite
- [x] Demo mode

### **FASE 2: Execution (1-2 semanas)**
- [ ] Smart Order Sizing
- [ ] TWAP Executor
- [ ] VWAP Executor
- [ ] Iceberg Orders
- [ ] Adaptive Timing

### **FASE 3: Validation (1 semana)**
- [ ] Backtester engine
- [ ] Monte Carlo simulation
- [ ] Walk-Forward analysis
- [ ] Cross-validation
- [ ] Luck detector

### **FASE 4: Production (2-4 semanas)**
- [ ] Data collection (30 días)
- [ ] Backtest validation
- [ ] Paper trading (7 días)
- [ ] Live trading (gradual scale)

---

## 📚 REFERENCIAS

**Papers Implementados:**
1. Avellaneda & Stoikov (2008) - "High-frequency trading in a limit order book"
2. Engle & Granger (1987) - "Co-integration and Error Correction"

**Papers para Implementar:**
3. Fama & French (2010) - "Luck versus Skill in the Cross-Section"
4. Bailey et al. (2014) - "The Probability of Backtest Overfitting"

---

**Última actualización:** 2026-01-15
**Versión:** 2.0.0
**Estado:** Production-Ready (Paper Trading)
