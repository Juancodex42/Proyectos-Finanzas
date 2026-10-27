# Bot Trading Ripio Binance V2 — Quantitative Trading Platform

## Descripción General
Plataforma algorítmica institucional para trading cuantitativo en pares de criptomonedas y stablecoins (USDT/ARS, USDC/ARS, USDT/USDC, BTC, ETH) conectando **Ripio Trade** y **Binance**. Implementa estrategias de vanguardia en microestructura de mercado: **Market Making Dinámico (Avellaneda & Stoikov, 2008)** y **Arbitraje Estadístico con Reversión a la Media (Ornstein-Uhlenbeck & Test de Cointegración ADF)**, junto con un enrutador inteligente de órdenes multicadena y un motor de validación estadística (Walk-Forward, Monte Carlo y Luck vs Skill).

---

## Arquitectura del Proyecto

```
Bot Trading Ripio Binance V2/
├── config/                             # Configuración YAML (estrategias, riesgo, fees)
│   └── trading_config.yaml
├── docs/                               # Documentación técnica y cuantitativa
├── src/
│   ├── domain/                         # Capa de Dominio (Modelos inmutables y matemática pura)
│   │   ├── models.py                   # Dataclasses de órdenes, cotizaciones y señales
│   │   └── quant_math.py               # Fórmulas puras (Avellaneda-Stoikov, OU, ADF, Sharpe)
│   ├── core/                           # Clientes API, configuración y persistencia
│   │   ├── config_loader.py            # Carga segura con fallback a .env.example
│   │   ├── ripio_api.py                # Cliente async con HMAC SHA256 y rate-limiting resiliente
│   │   ├── binance_api.py              # Cliente async para Binance REST API
│   │   ├── state_manager.py            # Estado atómico de balances y trades
│   │   └── demo_runner.py              # Modo Demo Zero-API sin credenciales
│   ├── strategies/                     # Lógica de Estrategias Cuantitativas
│   │   ├── market_making.py            # Modelo Avellaneda-Stoikov con sesgo de inventario
│   │   └── statistical_arbitrage.py    # StatArb con Z-score, ADF cointegration y half-life
│   ├── execution/                      # Enrutamiento y Ejecución
│   │   └── inter_exchange_router.py    # Comparador multi-ruta (Ripio Directo vs Puente Binance TRC20/BEP20/ERC20)
│   ├── analytics/                      # Backtesting y Métricas Institucionales
│   │   ├── backtester.py               # Simulación event-driven, Walk-Forward, Monte Carlo
│   │   ├── data_loader.py              # Ingesta y generación sintética de datos
│   │   ├── portfolio_manager.py        # Control de exposición, límites y desbalances
│   │   └── reporting.py                # Generación de reportes y exportación
│   └── telegram_bot/                   # Interfaz de telemetría y comandos
├── tests/                              # Suite de pruebas unitarias 100% offline
│   ├── test_bot.py
│   ├── test_telegram.py
│   └── README.md
├── BOT_TRADING_RIPIO_V2.bat            # Lanzador interactivo 1-Click con Modo Demo
├── main.py                             # Orquestador central CLI
├── requirements.txt                    # Dependencias pip
└── .env.example                        # Plantilla de credenciales seguras
```

---

## Modos de Ejecución

### 1. Modo Demo Zero-API (Recomendado para evaluadores y recruiters)
No requiere cuentas en Ripio ni en Binance ni saldo en dinero real. Ejecuta una simulación completa de cotizaciones, precios de reserva Avellaneda-Stoikov, señales StatArb Ornstein-Uhlenbeck y backtesting Walk-Forward:
```bash
python main.py --mode demo
# O simplemente haciendo doble clic en BOT_TRADING_RIPIO_V2.bat y eligiendo opción [1]
```

### 2. Ejecución de Pruebas Unitarias
```bash
python -m pytest tests -v
# O vía BOT_TRADING_RIPIO_V2.bat opción [5]
```

### 3. Modo Backtesting Cuantitativo
```bash
python main.py --mode backtest --days 30 --capital 10000
```

---

## Políticas de Seguridad & Alpha Protection
- **Zero Hardcoded Secrets:** Las credenciales se cargan exclusivamente desde variables de entorno o archivo `.env`. El repositorio únicamente incluye `.env.example`.
- **Alpha Sanitization:** Parámetros propietarios y umbrales de alta frecuencia han sido abstraídos o calibrados con valores sintéticos de demostración para proteger la propiedad intelectual de la estrategia comercial.
