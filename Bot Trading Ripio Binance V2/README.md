# Bot de Trading Argentino V2 - Sistema Cuantitativo Profesional

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![Trading Models](https://img.shields.io/badge/Strategy-Pairs%20Trading%20%2B%20Avellaneda--Stoikov-orange.svg)]()
[![Validation](https://img.shields.io/badge/Validation-Monte%20Carlo%20Walk--Forward-purple.svg)]()
[![Tests](https://img.shields.io/badge/Tests-14%20Passed%20(100%25)-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-Proprietary%20%2F%20Research-red.svg)]()

Sistema de trading algorítmico para mercado argentino de criptomonedas con validación científica.

> [!IMPORTANT]
> **Naturaleza de la Interfaz & Ejecución:** Este sistema es un motor cuantitativo institucional que opera puramente en **consola / terminal (CLI)** con telemetría en tiempo real. **No abre navegador web**, priorizando velocidad de cálculo numérico, backtesting y ejecución algorítmica de órdenes.
>
> 🚀 **Lanzador 1-Clic para Windows:** Incluye el panel interactivo [`BOT_TRADING_RIPIO_BINANCE_V2.bat`](BOT_TRADING_RIPIO_BINANCE_V2.bat) para ejecutar la Demo Cuantitativa en vivo, simulaciones Monte Carlo o tests unitarios.
>
> 🔒 **Modo Demo & Seguridad Operativa (Zero-API Sandbox):**
> - **Seguridad de Credenciales:** El repositorio no requiere ni expone credenciales privadas de Ripio ni Binance (`.env.example` incluido para configuración opcional).
> - **Protección de Estrategia Propietaria:** Los modelos cuantitativos (Pairs Trading cointegrado y Market Making Avellaneda-Stoikov) están configurados en modo Sandbox para proteger la ventaja competitiva comercial del operador.
> - **Simulación Científica Completa:** Permite ejecutar backtesting Walk-Forward, análisis Monte Carlo y pruebas de permutación (Luck vs Skill) con datos sintéticos e históricos sin arriesgar capital.

---

## 📑 Tabla de Contenidos

- [Características Principales](#-características-principales)
- [Arquitectura del Proyecto](#-arquitectura-del-proyecto)
- [Índice de Documentación](#-índice-de-documentación)
- [Instalación y Configuración](#-instalación)
- [Uso y Fases Operativas](#-uso)
  - [Fase 1: Data Collection](#fase-1-data-collection-30-días)
  - [Fase 2: Backtesting](#fase-2-backtesting)
  - [Fase 3: Paper Trading](#fase-3-paper-trading-7-días-mínimo)
  - [Fase 4: Live Trading](#fase-4-live-trading)
- [Control Remoto vía Telegram](#-control-remoto-vía-telegram)
- [Validación Científica (Monte Carlo, Walk-Forward, Permutación)](#-validación-científica)
- [Estrategias en Detalle](#-estrategias-en-detalle)
- [Gestión de Riesgo y Portfolio Manager](#️-gestión-de-riesgo)
- [Monitoreo en Tiempo Real](#-monitoreo-en-tiempo-real)
- [Advertencias y Límites del Mercado](#️-advertencias-importantes)
- [Troubleshooting & Soporte](#-troubleshooting)
- [Roadmap & Próximos Pasos](#-roadmap--futuras-implementaciones)
- [Licencia y Créditos](#️-licencia)

---

## 🎯 CARACTERÍSTICAS PRINCIPALES

### **Estrategias Cuantitativas**
✅ **Statistical Arbitrage** (Pairs Trading) - USDT/ARS ↔ USDC/ARS con cointegración
✅ **Market Making** (Modelo Avellaneda-Stoikov) con gestión de inventario

### **Ejecución Profesional**
✅ **Smart Order Sizing** - Detecta market impact y fragmenta órdenes grandes
✅ **Triple Validación Anti-Taker** - Evita pagar comisión 0.30% (vs 0.13% maker)
✅ **Adaptive Timing** - Anti-detección por otros bots

### **Gestión de Riesgo**
✅ **Portfolio Manager** - Tracking multi-moneda (USDT/USDC/ARS/BTC/ETH)
✅ **Value at Risk (VaR)** - Límite 2% con 95% confianza
✅ **Max Drawdown Control** - Stop si DD > 15%
✅ **Límites de exposición** - ARS max 30%, Crypto max 20%
✅ **Rebalanceo automático** - Mantiene 50% USDT / 50% USDC

### **Validación Estadística**
✅ **Monte Carlo Walk-Forward** - 1000+ simulaciones
✅ **Temporal Cross-Validation** - 4 folds mínimo
✅ **Regime Change Testing** - Alta/media/baja volatilidad
✅ **Luck vs Skill Detection** - Permutation tests
✅ **Out-of-Sample Testing** - 15 días nunca vistos

---

## 📁 ARQUITECTURA DEL PROYECTO

```
bot_v2/
│
├── config/
│   └── trading_config.yaml      # Configuración de estrategias y riesgo
│
├── data/
│   ├── historical/              # Datos históricos para backtesting
│   ├── state/                   # Estado persistente del bot
│   └── logs/                    # Logs detallados (bot.log, backtest.log)
│
├── docs/                        # 📚 Documentación y guías detalladas
│   ├── ARQUITECTURA.md          # Arquitectura profunda del sistema
│   ├── GUIA_USUARIO_COMPLETA.md # Manual de usuario paso a paso
│   ├── QUICKSTART.md            # Guía rápida de inicio
│   ├── QUICKSTART_TELEGRAM.md   # Setup rápido de Telegram
│   ├── TELEGRAM_INTERFACE.md    # Manual de la interfaz y comandos Telegram
│   ├── DATA_COLLECTION.md       # Guía de recolección de datos históricos
│   ├── TESTING_GUIDE.md         # Guía de testing y verificación
│   ├── INTER_EXCHANGE_ROUTING.md# Guía de enrutamiento inter-exchange
│   ├── STRATEGY_DEGRADATION.md  # Monitoreo de degradación de alfa
│   ├── ESTADO_PROYECTO.md       # Estado actual y auditoría
│   └── MEJORAS_IMPLEMENTADAS.md # Registro de mejoras
│
├── reports/                     # Reportes y análisis generados
│
├── src/
│   ├── analytics/               # Motores cuantitativos y backtesting
│   ├── core/                    # APIs de exchanges, config y estado
│   ├── execution/               # Enrutamiento y algoritmos de ejecución
│   ├── strategies/              # Estrategias (Stat Arb, Market Making)
│   └── telegram/                # Interfaz y automatización de Telegram
│
├── tests/
│   ├── test_bot.py              # Suite de verificación completa
│   └── test_telegram.py         # Test de conectividad Telegram
│
├── .env.example                 # Template de variables de entorno
├── .gitignore                   # Exclusiones de Git
├── requirements.txt             # Dependencias del proyecto
├── collect_data.py              # Script CLI de recolección de datos
├── run_backtest.py              # Script CLI de backtesting y Monte Carlo
├── main.py                      # ✅ Entry point orquestador principal
└── README.md                    # Documento principal y portada
```

---

## 📚 ÍNDICE DE DOCUMENTACIÓN

Todos los manuales y guías del proyecto se encuentran organizados en la carpeta [`docs/`](docs/):

| Documento | Descripción |
| :--- | :--- |
| [GUIA_USUARIO_COMPLETA.md](docs/GUIA_USUARIO_COMPLETA.md) | Guía paso a paso para operar el bot, alertas y flujos diarios. |
| [QUICKSTART.md](docs/QUICKSTART.md) | Inicio rápido en 5 minutos para simulación y backtest. |
| [QUICKSTART_TELEGRAM.md](docs/QUICKSTART_TELEGRAM.md) | Configuración paso a paso del bot de Telegram en minutos. |
| [TELEGRAM_INTERFACE.md](docs/TELEGRAM_INTERFACE.md) | Documentación completa de comandos interactivos y dashboards. |
| [ARQUITECTURA.md](docs/ARQUITECTURA.md) | Diseño detallado de componentes, módulos y flujo de datos. |
| [DATA_COLLECTION.md](docs/DATA_COLLECTION.md) | Protocolo de captura de libro de órdenes y precios de Ripio. |
| [TESTING_GUIDE.md](docs/TESTING_GUIDE.md) | Guía para ejecutar suites de verificación y pruebas unitarias. |
| [INTER_EXCHANGE_ROUTING.md](docs/INTER_EXCHANGE_ROUTING.md) | Documentación sobre enrutamiento inteligente entre Ripio y Binance. |
| [STRATEGY_DEGRADATION.md](docs/STRATEGY_DEGRADATION.md) | Métricas y alertas ante pérdida de cointegración y alfa. |
| [ESTADO_PROYECTO.md](docs/ESTADO_PROYECTO.md) | Auditoría de componentes implementados y roadmap. |
| [MEJORAS_IMPLEMENTADAS.md](docs/MEJORAS_IMPLEMENTADAS.md) | Registro de optimizaciones técnicas y cambios arquitectónicos. |

---

## 🚀 INSTALACIÓN

### **Acceso Rápido en Windows (Recomendado):**
Haz doble clic en [`BOT_TRADING_RIPIO_BINANCE_V2.bat`](BOT_TRADING_RIPIO_BINANCE_V2.bat) para acceder al panel de control interactivo con opciones directas para correr la Demo en vivo, Backtesting o Tests unitarios sin tipear comandos.

### **Instalación Manual / Multiplataforma (Linux / macOS):**

### **1. Clonar/Copiar archivos**
```bash
cd "Bot Trading Ripio Binance V2"
```

### **2. Crear entorno virtual**
```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
```

### **3. Instalar dependencias**
```bash
pip install -r requirements.txt
```

### **4. Configurar credenciales**
```bash
# Copiar template
copy .env.example .env

# Editar .env con tus credenciales:
# - TELEGRAM_BOT_TOKEN (Control remoto - opcional)
# - TELEGRAM_AUTHORIZED_USERS (Tu User ID)
# - RIPIO_API_TOKEN
# - RIPIO_SECRET_KEY
```

**Telegram Bot (Opcional pero Recomendado)**:
1. Habla con [@BotFather](https://t.me/botfather) en Telegram
2. Crea un nuevo bot: `/newbot`
3. Copia el token que te da
4. Obtén tu User ID de [@userinfobot](https://t.me/userinfobot)
5. Agrega ambos a `.env`:
   ```
   TELEGRAM_BOT_TOKEN=tu_telegram_bot_token_aqui
   TELEGRAM_AUTHORIZED_USERS=123456789
   ```

Ver [TELEGRAM_INTERFACE.md](docs/TELEGRAM_INTERFACE.md) para más detalles.

### **5. Ejecutar suite de pruebas unitarias (14 tests)**
```bash
pytest tests/ -v
```

### **6. Ajustar configuración** (opcional)
Editar `config/trading_config.yaml` para ajustar:
- Límites de riesgo
- Parámetros de estrategias
- Umbrales de ejecución

---

## 📊 USO

### **FASE 1: Data Collection (30 días)**
```bash
python main.py --mode collect --days 30
```
**Objetivo:** Recolectar datos históricos de orderbook cada 5 min

**Output:** `data/historical/orderbook_snapshots.csv`

---

### **FASE 2: Backtesting**

#### Backtest Básico
```bash
# Con datos sintéticos (para testing)
python run_backtest.py --mode basic --synthetic --days 30 --strategy mean_reversion

# Con datos históricos reales
python run_backtest.py --mode basic --data historical_data.csv --strategy mean_reversion
```

#### Walk-Forward Analysis
```bash
python run_backtest.py --mode walk_forward --synthetic --days 90 \
    --train-window 30 --test-window 7 --num-folds 4
```

#### Monte Carlo Simulation
```bash
python run_backtest.py --mode monte_carlo --synthetic --days 30 --simulations 1000
```

#### Luck vs Skill Analysis
```bash
python run_backtest.py --mode luck_vs_skill --synthetic --days 30 --permutations 1000
```

#### Full Analysis Suite
```bash
# Ejecuta backtest + Monte Carlo + Luck vs Skill
python run_backtest.py --mode full --synthetic --days 30 \
    --capital 10000 --simulations 1000 --permutations 1000 --export
```

**Criterios de aprobación:**
- ✅ Sharpe > 1.5
- ✅ Win Rate > 55%
- ✅ Max DD < 15%
- ✅ P-value < 0.05
- ✅ Consistencia > 75%

**Output:** `reports/backtest_report_*.txt`, `reports/trades.csv`, `reports/equity_curve.csv`

---

### **FASE 3: Paper Trading (7 días mínimo)**
```bash
python main.py --mode paper
```

**Ejecuta:**
- Simulación en tiempo real (órdenes NO reales)
- Monitoreo de Sharpe live
- Alertas de oportunidades
- Tracking de P&L simulado

**Condiciones para pasar a LIVE:**
- ✅ Sharpe > 2.0
- ✅ Win Rate > 60%
- ✅ Min 100 trades
- ✅ Max DD < 10%

---

### **FASE 4: Live Trading**
```bash
python main.py --mode live --capital 100
```

**IMPORTANTE:**
- Inicia con capital **MUY pequeño** ($100 USD)
- Escala gradualmente cada semana si Sharpe > 2.0
- Monitorea degradación vs backtest

**Escalamiento sugerido:**
```
Semana 1: $100
Semana 2: $250
Semana 3: $500
Semana 4: $1,000
Semana 5+: $2,500+
```

---

## 📱 CONTROL REMOTO VÍA TELEGRAM

El bot incluye una **interfaz completa de Telegram** para controlar y monitorear desde tu celular.

### Comandos Principales

#### Información en Tiempo Real
```
/status       - Estado del bot (running/stopped)
/stats        - Estadísticas (Sharpe, P&L, Win Rate)
/pnl          - Profit & Loss breakdown
/positions    - Posiciones actuales
/trades       - Últimos 5 trades
/strategies   - Estado de cada estrategia
```

#### Control del Bot
```
/startbot     - Iniciar bot
/stopbot      - Detener bot
/pause        - Pausar todas las estrategias
/resume       - Reanudar estrategias
```

#### Gestión de Estrategias
```
/enable stat_arb          - Activar Statistical Arbitrage
/disable market_making    - Desactivar Market Making
```

#### Data & Config
```
/reload       - Recargar configuración
/backtest     - Ejecutar backtest remoto
/collect      - Instrucciones de data collection
```

#### Alertas
```
/alerts       - Toggle alertas on/off
/alertson     - Activar alertas
/alertsoff    - Desactivar alertas
```

### Ejemplo de Uso

```
Mañana:
  /status       # Verificar que el bot está corriendo
  /stats        # Ver métricas del día anterior
  /alertson     # Activar alertas periódicas

Durante el día:
  [Recibes alertas automáticas cada 60 min]
  /positions    # Ver posiciones actuales si quieres
  /trades       # Ver últimos trades

Si algo va mal:
  /pause        # Pausar estrategias
  /stopbot      # Detener completamente

Noche:
  /pnl          # Revisar ganancias/pérdidas del día
  /alertsoff    # Desactivar alertas para dormir
```

### Alertas Automáticas

El bot envía resúmenes cada 60 minutos:

```
[PERIODIC UPDATE]

Sharpe (7d): 2.1
Total P&L: $156.78
Today P&L: $12.34
Today Trades: 3
```

---

## 🔬 VALIDACIÓN CIENTÍFICA

### **Monte Carlo Walk-Forward**
```python
# Ejecuta 1000 simulaciones con bootstrap
# Calcula distribución de Sharpe ratio
# Verifica: P(Sharpe > 1.5) > 70%
```

**Ejemplo output:**
```
Monte Carlo Results (1000 simulaciones):
├─ Sharpe promedio: 2.35
├─ Sharpe 5th percentile: 1.62
├─ Sharpe 95th percentile: 3.18
├─ P(Sharpe > 1.5): 89.2% ✅
└─ P(Profitable): 94.7% ✅
```

---

### **Temporal Cross-Validation**
```python
# Divide datos en 4 folds temporales
# Entrena en cada fold, testea en siguiente
# Promedia resultados
```

**Ejemplo output:**
```
Cross-Validation Results:
├─ Fold 1: Sharpe 2.1
├─ Fold 2: Sharpe 2.4
├─ Fold 3: Sharpe 1.9
├─ Fold 4: Sharpe 2.3
├─ Promedio: 2.18
├─ Std: 0.21
└─ Consistencia: 100% (todos > 1.0) ✅
```

---

### **Luck vs Skill Detector**
```python
# Permutation test: Permuta señales aleatoriamente
# Si sigue ganando → Es suerte
# Si deja de ganar → Es skill
```

**Ejemplo output:**
```
Luck vs Skill Analysis:
├─ T-statistic: 3.42 ✅
├─ P-value (bootstrap): 0.003 ✅
├─ P-value (permutation): 0.008 ✅
├─ Hurst exponent: 0.58
└─ Veredicto: ALTA CONFIANZA - Ventaja estadística real
```

---

## 🎯 ESTRATEGIAS EN DETALLE

### **1. Statistical Arbitrage**
**Fundamento:** USDT/ARS y USDC/ARS están cointegradas (relación de largo plazo estable)

**Señales:**
```python
Z-score > +2.0 → VENDER USDT, COMPRAR USDC
Z-score < -2.0 → COMPRAR USDT, VENDER USDC
-0.5 < Z-score < +0.5 → CERRAR POSICIONES
```

**Métricas esperadas:**
- Sharpe: 3.0+
- Win Rate: 70%+
- Trades/día: 2-5

---

### **2. Market Making**
**Fundamento:** Captura spread bid-ask sin direccionalidad

**Modelo Avellaneda-Stoikov:**
```python
# Precio de reserva ajustado por inventario
reservation_price = mid - inventory_penalty
bid = reservation_price - spread / 2
ask = reservation_price + spread / 2

inventory_penalty = γ × q × σ²
```

**Métricas esperadas:**
- Sharpe: 2.5+
- Win Rate: 60%+
- Trades/día: 10-20

---

## 🛡️ GESTIÓN DE RIESGO

### **Límites Automáticos**
```yaml
risk:
  max_perdida_por_operacion: 2%
  max_posicion_individual: 20%
  max_exposicion_simultanea: 50%
  max_perdida_diaria: 5%
  max_drawdown: 15%
  var_limite: 2%
```

### **Portfolio Rebalancing**
```
Target: 50% USDT / 50% USDC / 0% ARS

Si desviación > 10% → Rebalanceo automático:
  - ARS > 10% → Convertir a stables
  - USDT > 65% → Convertir a USDC
  - USDC > 65% → Convertir a USDT
```

---

## 📈 MONITOREO EN TIEMPO REAL

### **Dashboard Telegram**
```
📊 PORTFOLIO STATUS
━━━━━━━━━━━━━━━━━━
💰 Valor Total: $10,543 USD
📈 P&L Día: +$127 (+1.2%)
📊 Sharpe (7d): 2.35

💼 Exposición:
├─ USDT: 48% ✅
├─ USDC: 47% ✅
├─ ARS: 3% ✅
└─ BTC: 2% ✅

🎯 Estrategias Activas:
├─ Stat Arb: +$45 (3 trades)
├─ Market Making: +$82 (15 trades)
└─ Triangular: +$0 (0 trades)

⚠️ Riesgos:
├─ VaR 95%: 1.2% ✅
├─ Max DD: 4.3% ✅
└─ Exposición: 47% ✅
```

---

## ⚠️ ADVERTENCIAS IMPORTANTES

### **1. Mercado Argentino - Limitaciones**
❌ **Solo 2 pares de stablecoins** (USDT, USDC)
❌ **Datos históricos limitados** (1-2 años)
❌ **Régimen único** (inflación alta constante)

**Solución:** Estándares de validación MÁS altos
- P-value < **0.01** (vs 0.05 típico)
- Sharpe > **2.0** (vs 1.5 típico)
- Consistency > **80%** (vs 75% típico)

---

### **2. Riesgo de Degradación**
**Problema:** Performance live < backtest (overfitting)

**Monitoreo:**
```python
if sharpe_live_7d < sharpe_backtest * 0.5:
    PAUSA_AUTOMÁTICA()
    ALERTA_CRÍTICA()
```

---

### **3. Competencia**
**Otros bots también operan este mercado**

**Estrategia:**
- Adaptive Timing (delays aleatorios)
- Iceberg Orders (ocultar intención)
- Fragmentación TWAP (no mover precio)

---

## 🔧 TROUBLESHOOTING

### **Error: Rate Limit 429**
```
⚠️ Rate limit alcanzado (public). Esperando 45.2s...
```
**Solución:** El bot espera automáticamente. Si es frecuente, reduce `check_interval` en config.

---

### **Error: Cointegración No Válida**
```
❌ RECHAZADO: P-value cointegración = 0.12 (> 0.05)
```
**Solución:** Necesitas más datos históricos (min 30 días). Ejecuta primero data collection.

---

### **Error: Balance Insuficiente**
```
❌ Balance insuficiente: Requiere 1234 ARS, disponible 500 ARS
```
**Solución:** Verifica balance en Ripio Trade y ajusta `capital_inicial` en .env

---

## 📞 SOPORTE

### **Logs**
```bash
# Ver logs en tiempo real
tail -f data/logs/bot.log

# Ver errores críticos
grep "CRITICAL\|ERROR" data/logs/bot.log
```

### **Estado del Bot**
```bash
# Ver estado guardado
cat data/state/bot_state.json
```

### **Health Check**
```python
python main.py --mode health
```
**Output:**
```
✅ Ripio API: OK (latencia 120ms)
✅ Binance API: OK (latencia 45ms)
✅ Database: OK
✅ Config: OK
✅ Credentials: OK
```

---

## 📚 REFERENCIAS

### **Papers Implementados**
1. Avellaneda & Stoikov (2008) - "High-frequency trading in a limit order book"
2. Engle & Granger (1987) - "Co-integration and Error Correction"
3. Fama & French (2010) - "Luck versus Skill in the Cross-Section"

### **Documentación API**
- [Ripio Trade API v4](https://developers.ripiotrade.co/)
- [Binance Public API](https://binance-docs.github.io/apidocs/)

---

## 📊 ROADMAP / FUTURAS IMPLEMENTACIONES

### **Estrategias Cuantitativas Planificadas**
- [ ] **Triangular Arbitrage (Intra-Exchange)**:
  - Rutas sin transferencias on-chain: `USDC → BTC → USDT → ARS` y `USDC → ETH → USDT → ARS`
  - Modelo de costos integral: comisiones acumuladas (0.3% × 3) y fees de red
  - Target: Sharpe 5.0+, 5-10 oportunidades/día
- [ ] **Volatility Harvesting (Gamma Scalping)**:
  - Explotación de regímenes de alta volatilidad con rebalanceo sistemático para capturar primas de volatilidad en stablecoins.

### **Algoritmos de Ejecución Planificados**
- [ ] **TWAP (Time-Weighted Average Price)**:
  - Fragmentación temporal determinística para ejecutar volumen institucional sin mover el precio de mercado.
- [ ] **VWAP (Volume-Weighted Average Price)**:
  - Ponderación de trades según el perfil intradiario de volumen para optimizar el precio promedio ponderado.
- [ ] **Iceberg Orders**:
  - Ocultamiento de tamaño real de órdenes limit en el orderbook para evitar señales a otros algoritmos.

### **Implementado en Producción ✅**
- [x] Professional Ripio API con rate limiting, autenticación segura y backoff exponencial
- [x] Smart Order Sizing y triple validación anti-taker (garantiza tarifas maker de 0.13%)
- [x] Portfolio Manager multi-moneda (USDT / USDC / ARS / BTC / ETH) con VaR y control de exposición
- [x] Statistical Arbitrage (Pairs Trading) con prueba de cointegración Engle-Granger
- [x] Market Making cuantitativo con modelo Avellaneda-Stoikov y ajuste dinámico por inventario
- [x] Framework de Backtesting riguroso: Monte Carlo Walk-Forward, cross-validation temporal y test de Luck vs Skill
- [x] Interfaz de control remoto y monitoreo en tiempo real vía Telegram modular
- [x] Soporte CLI multi-modo en `main.py` (`--mode paper`, `--mode live`, `--mode backtest`, `--mode collect`, `--mode health`)

### **Próximos Pasos 📅**
- [ ] Machine Learning para calibración adaptativa de umbrales Z-score
- [ ] Conectores multi-exchange adicionales (Buenbit, Lemon Cash, Binance Futures)
- [ ] Dashboard web interactivo con métricas en tiempo real (Plotly / React)

---

## ⚖️ LICENCIA

Uso personal. No redistribuir sin permiso.

---

## 🙏 CRÉDITOS

Desarrollado con fundamentos cuantitativos rigurosos y validación estadística científica.

**Tecnologías:**
- Python 3.10+
- aiohttp (async HTTP)
- numpy/pandas (análisis)
- statsmodels (cointegración)
- python-telegram-bot (UI)

---

**💡 Última actualización:** 2026-01-15
**📧 Contacto:** Perfil de GitHub / Issues del Repositorio
**⭐ Versión:** 2.0.0-beta
