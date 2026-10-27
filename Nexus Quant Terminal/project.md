# Documentación Maestra del Proyecto: Nexus Quant Terminal

## 1. Propósito del Sistema y Filosofía Cuantitativa

**Nexus Quant Terminal** es una estación de investigación cuantitativa, simulación de campañas multi-activo, optimización genética híbrida (Python + Rust) y ejecución algorítmica dual (*Paper Trading* y *Live Trading* en futuros perpetuos USDT-M de Binance).

El sistema implementa una filosofía **Barbell / Asimetría Convexa (Nassim Taleb)** diseñada para capturar eventos de cola (*Black Swans* positivos) mientras acota estrictamente el riesgo de ruina mediante *bullets* diarios independientes y dimensionamiento fraccional de Kelly con progresión Paroli sobre ganancias de la casa (*house money*).

> **Nota sobre Propiedad Intelectual (Alpha Protection):**
> Las estrategias incluidas en este repositorio corresponden a implementaciones base y académicas (modelos de Markov, cruces institucionales, reversión a la media y estructuras de volumen) diseñadas para demostrar la capacidad de procesamiento, simulación por eventos y optimización genética del motor **Nexus Quant Terminal**. Las estrategias propietarias de generación de *Alpha* en producción han sido excluidas por razones de confidencialidad financiera.

---

## 2. Modos de Operación (Zero-API Demo Mode vs Live Mode)

El proyecto está diseñado para ejecutarse **out-of-the-box sin requerir claves de API (`BINANCE_API_KEY` ni `TELEGRAM_BOT_TOKEN`)**:

1. **Modo Demo Web / Zero-API (`NEXUS_QUANT_TERMINAL.bat` -> Opción 1):**
   - Levanta el servidor Flask en `http://127.0.0.1:5001` utilizando datasets históricos OHLCV locales (`data/*.csv`) con caché LRU en memoria (`src/engine/services/runtime_context.py`).
   - Los motores de ejecución (`BinanceFuturesClient` y `TelegramBotClient`) detectan automáticamente la ausencia de credenciales y operan en modo simulado seguro (*Paper Trading* / sin llamadas externas bloqueantes).
2. **Modo Demostración Cuantitativa en Consola (`NEXUS_QUANT_TERMINAL.bat` -> Opción 2):**
   - Ejecuta un pipeline reproducible en terminal: carga de series temporales, inferencia de regímenes de Markov, simulación Triple-Barrier con campañas Barbell/Paroli y reporte de métricas institucionales (Win Rate, Profit Factor, Expectancy, Sharpe, Sortino y Max Drawdown).
3. **Modo Live / Paper Dual Bot (con `.env` configurado):**
   - Cuando se proveen credenciales en `.env` (basado en `.env.example`), el `DualBotManager` sincroniza velas en tiempo real y despacha órdenes `MARKET`, `STOP_MARKET` (Stop-Loss protegido) y `TAKE_PROFIT_MARKET` hacia Binance Futures.

---

## 3. Arquitectura Modular del Sistema

El repositorio cumple estrictamente con el principio de **Responsabilidad Única (SRP)** y el límite duro de **< 500 líneas de código por archivo**, organizándose en capas desacopladas sin dependencias circulares:

```text
Nexus Quant Terminal/
├── NEXUS_QUANT_TERMINAL.bat      # Lanzador interactivo (5 opciones: Web Demo, CLI Demo, Pytest, Stop, Exit)
├── app.py                        # Punto de entrada Flask y registro de Blueprints HTTP/SSE
├── config.py                     # Configuración centralizada y lectura segura de variables de entorno
├── project.md                    # Especificación técnica y funcional maestra del proyecto
├── docs/
│   ├── ARQUITECTURA.md           # Diseño arquitectónico detallado, contratos de dominio y diagramas
│   └── PROJECT.md                # Copia de referencia de la especificación del sistema
├── src/
│   ├── domain/
│   │   └── models.py             # Entidades y contratos tipados (@dataclass): TradeSignal, SimulatedTrade, etc.
│   ├── engine/
│   │   ├── services/
│   │   │   ├── runtime_context.py          # Contexto de ejecución, caché LRU de CSVs, singletons y utilidades
│   │   │   ├── smart_optimizer_service.py  # Orquestador SSE de optimización multi-activo (Python + Rust)
│   │   │   └── smart_portfolio_evaluator.py# Evaluación In-Sample / Out-of-Sample, métricas y ranking de carteras
│   │   ├── simulators/
│   │   │   ├── binary.py                   # Simulador de eventos discretos (Binary / Fixed Horizon)
│   │   │   ├── binary_campaigns.py         # Simulación de campañas multi-activo para horizontes binarios
│   │   │   ├── triple_barrier.py           # Simulador Triple-Barrier (SL/TP por ATR, Time Barrier y Paroli)
│   │   │   └── triple_barrier_multi.py     # Motor multi-activo con dimensionamiento proporcional de bullets
│   │   ├── optimizers/
│   │   │   ├── capital.py                  # Optimizador de capital (Kelly, Martingala acotada, Interés Compuesto)
│   │   │   ├── barbell_montecarlo.py       # Simulador Monte Carlo de duplicación patrimonial y Barbell
│   │   │   └── parallel.py                 # Evaluación multiproceso de grillas paramétricas
│   │   ├── execution/
│   │   │   ├── binance_client.py           # Adaptador CCXT para Binance USDT-M Futures con protección de SL
│   │   │   ├── dual_bot_manager.py         # Orquestador de Bot 1 (Paper) y Bot 2 (Live) con estado persistente
│   │   │   ├── bot_worker_tasks.py         # Tareas de escaneo de radar, reconciliación y despacho de señales
│   │   │   ├── signal_dispatcher.py        # Ranking y filtrado de señales candidatas multi-activo
│   │   │   ├── telegram_bot.py             # Cliente bidireccional de Telegram (comandos y alertas)
│   │   │   └── telegram_views.py           # Renderizado de gráficos PNG (velas y curva de capital) y menús
│   │   ├── exporters/
│   │   │   ├── pinescript.py               # Exportador de estrategias a TradingView Pine Script v5
│   │   │   ├── pinescript_templates.py     # Plantillas Pine Script v5 para las 13 estrategias
│   │   │   ├── python_standalone.py        # Generador de bots autónomos en Python (CCXT + Pandas)
│   │   │   └── python_templates.py         # Plantillas de código Python para estrategias exportadas
│   │   ├── comparative_engine.py           # Motor de comparación multi-activo y ranking de regímenes
│   │   ├── comparative_metrics.py          # Cálculo de métricas comparativas y simulación de duplicación
│   │   ├── markov_regime.py                # Cadenas de Markov discretas y Hidden Markov Models (HMM)
│   │   ├── statistics.py                   # Estadística avanzada (Sharpe, Sortino, Kelly, rachas, Monte Carlo)
│   │   ├── optimizer_optuna.py             # Optimización bayesiana TPE con validación Walk-Forward (IS/OOS)
│   │   ├── auto_tuner.py                   # Sintonizador automático de hiperparámetros por activo
│   │   └── genetic_optimizer/              # Motor evolutivo nativo en Rust (Rayon + Serde)
│   └── routes/
│       ├── backtest_routes.py              # Endpoints de simulación, comparación y exportación
│       ├── bot_routes.py                   # API REST de control y telemetría para DualBotManager
│       ├── genetic_routes.py               # Streaming SSE para el optimizador genético en Rust
│       ├── market_routes.py                # Catálogo de activos, estrategias y sincronización de velas
│       ├── plan_routes.py                  # Generación de planes de trading y señales en vivo
│       └── smart/
│           ├── optimizer.py                # Rutas HTTP/SSE de Smart Optimization v1 y v2
│           ├── stream_v1.py                # Pipeline híbrido SSE v1 (Rust + validación cruzada Python)
│           └── formatters.py               # Formateadores de payloads de telemetría y matrices de correlación
├── strategies/                   # Catálogo de 13 estrategias cuantitativas vectorizadas
├── static/                       # Frontend SPA (Vanilla JS modular + Chart.js + CSS Glassmorphism)
└── tests/                        # Suite de pruebas automatizadas (Tiers 1 a 5 + Integridad Arquitectónica)
```

---

## 4. Catálogo de 13 Estrategias Cuantitativas (`strategies/`)

| ID | Clase | Fundamento Cuantitativo |
| :--- | :--- | :--- |
| `markov` | `MarkovStrategy` | Probabilidades de transición empíricas con suavizado de Laplace sobre estados discretos. |
| `rsi_ema` | `RsiEmaStrategy` | Reversión a la media condicionada por tendencia estructural (EMA 200 + RSI extremo). |
| `bb_mean_rev` | `BollingerMeanReversionStrategy` | Retorno al equilibrio estadístico tras perforación de bandas de desviación estándar. |
| `macd_stoch` | `MacdStochasticStrategy` | Confluencia de momentum tendencial (MACD) y agotamiento de ciclo corto (Stochastic). |
| `supertrend_adx` | `SupertrendAdxStrategy` | Ruptura de volatilidad dinámica (ATR Supertrend) filtrada por fuerza direccional ADX. |
| `donchian_breakout` | `DonchianBreakoutStrategy` | Ruptura de canales de máximos/mínimos de $N$ períodos (inspirado en *Turtle Traders*). |
| `vwap_inst` | `VwapInstitutionalStrategy` | Desviación estándar respecto al precio promedio ponderado por volumen (VWAP) con filtro de volumen. |
| `kalman_pairs` | `KalmanPairsStrategy` | Estimación recursiva de precio justo mediante Filtro de Kalman 1D y disparo por Z-Score del residual. |
| `hurst_regime` | `HurstRegimeStrategy` | Clasificación fractal de memoria de serie temporal ($H < 0.45$ reversión, $H > 0.55$ persistencia). |
| `ou_mean_rev` | `OrnsteinUhlenbeckStrategy` | Proceso estocástico estacionario de Ornstein-Uhlenbeck con filtro de vida media (*half-life*). |
| `evt_tail` | `ExtremeValueTailStrategy` | Teoría de Valores Extremos (POT / GPD) para capturar colas pesadas y cascadas de liquidación. |
| `order_flow_vpin` | `OrderFlowVpinStrategy` | Toxicidad de flujo de órdenes (VPIN) mediante clasificación Bulk Volume (BVC). |
| `hawkes_cascade` | `HawkesProcessStrategy` | Proceso puntual auto-excitado de Hawkes para modelar agrupamiento de choques de volatilidad. |
