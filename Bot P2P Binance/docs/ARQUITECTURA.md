# 🏛️ Documento de Arquitectura de Software — Bot P2P Binance ARS

## 1. Visión General & Estándar de Diseño
El proyecto ha sido refactorizado al estándar **`src-layout` genuino** conforme a PEP 517/518, garantizando:
- Cero acoplamiento circular.
- Imports directos (`from core...` o `from src.core...`) sin fachadas ni trampas de re-exportación estática.
- Confinamiento modular estricto: **ningún archivo de código supera las 500 líneas** (objetivo de diseño < 400 líneas).
- Separación ortogonal de responsabilidades: Red, Dominio, Repositorio, Orquestador e Interfaz.

---

## 2. Mapa de Módulos y Paquetes (`src/`)

```
Bot P2P Binance/
├── main.py                     # Entry point ejecutable (< 70 líneas)
├── pytest.ini                  # Configuración con pythonpath = src .
├── src/
│   ├── config/
│   │   └── settings.py         # Configuración inmutable, márgenes y reglas
│   ├── core/
│   │   ├── orchestrator/       # Motor orquestador desacoplado en Mixins
│   │   │   ├── __init__.py     # Exporta BotEngine
│   │   │   ├── engine.py       # BotEngine (estado, init, loop principal) (< 310 l)
│   │   │   ├── cycle_executor.py # Ejecución cíclica y watchdog (< 240 l)
│   │   │   ├── reposition_cycle.py # Bucles de reposición buy/sell (< 380 l)
│   │   │   ├── order_processor.py # Fast-path y arbitraje Fiwind (< 220 l)
│   │   │   ├── lifecycle_manager.py # Encendido, apagado, reconciliación (< 300 l)
│   │   │   ├── calibrator.py   # Calibración en frío y auditoría dry-run (< 290 l)
│   │   │   └── initializer.py  # Inicialización de DB y métodos (< 210 l)
│   │   ├── ads/                # Gestión del ciclo de vida de anuncios
│   │   │   ├── manager.py      # AdsManager facade coordinando módulos
│   │   │   ├── lifecycle.py    # Creación, pausa, activación y cierre
│   │   │   ├── mutator.py      # Modificación atómica de precios/límites
│   │   │   └── replenisher.py  # Detección y recarga de anuncios agotados
│   │   ├── pricing/            # Algoritmos cuantitativos de precios
│   │   │   ├── buy_repositioner.py # Reposicionamiento y cálculo de spreads
│   │   │   ├── sell_repositioner.py # Reposicionamiento clusters de venta
│   │   │   ├── collision_guard.py  # Guardrail anti-colisión entre grupos
│   │   │   ├── ticket_filter.py    # Detección de anuncios cebo / no confiables
│   │   │   └── amount_calculator.py# Cálculo de montos según inventario
│   │   ├── network/            # Clientes HTTP asíncronos y rate limiters
│   │   │   ├── binance_api.py  # BinanceClient (C2C SAPI v7.4 con HMAC)
│   │   │   └── rate_limiter.py # Limitador adaptativo anti-error 429
│   │   ├── liquidity/          # Gestión de caja y balances
│   │   │   ├── liquidity_manager.py # Sincronización de caja y swaps
│   │   │   └── order_tracker.py # Tracking de órdenes abiertas y appeals
│   │   ├── antiban_validator.py # Validador formal de reglas Binance
│   │   ├── fiwind_client.py    # Oráculo de precios Fiwind / CriptoYa
│   │   ├── market_scanner.py   # Escáner multihilo de libros P2P
│   │   ├── method_selector.py  # Asignación heurística de métodos a grupos
│   │   ├── profit_tracker.py   # Registro de ganancias y WAC histórico
│   │   ├── sell_advisor.py     # Asesor de venta con piso WAC y Fiwind
│   │   ├── spot_client.py      # Cliente público Spot Binance
│   │   └── war_detector.py     # Detección de guerras de precios
│   ├── data/
│   │   ├── database.py         # Database multirrepositorio (< 140 l)
│   │   ├── schema.py           # DDL y parsers de SQLite (< 250 l)
│   │   ├── models.py           # Dataclasses tipadas (< 300 l)
│   │   └── repos/              # Repositorios especializados
│   │       ├── ad_repo.py      # Repositorio de anuncios y benchmarks (< 360 l)
│   │       ├── order_repo.py   # Repositorio de órdenes y swaps (< 300 l)
│   │       ├── market_repo.py  # Repositorio de snapshots e intel (< 340 l)
│   │       └── config_repo.py  # Repositorio de configuración viva (< 100 l)
│   └── telegram_bot/           # Interfaz C2 de Telegram (< 350 l por módulo)
│       ├── bot.py              # TelegramBot core y loop de polling
│       ├── commands.py         # Enrutamiento de comandos
│       ├── callbacks.py        # Enrutamiento de callbacks interactivos
│       ├── broadcaster.py      # Despacho de alertas y broadcast
│       ├── formatters/         # Vistas y formato de mensajes Markdown
│       └── views/              # Menús y teclados interactivos
```

---

## 3. Patrones de Diseño Aplicados
1. **Mixin-Based Decomposition**: `BotEngine` y `Database` emplean composición de mixins ortogonales para preservar una interfaz unificada sin incurrir en clases monolíticas.
2. **Fast-Path Liquidity Protection**: Interrupción inmediata y pausa preventiva en lote ante órdenes de compra entrantes descapitalizantes.
3. **Collision Guardrail Pattern**: Separación matemática forzada de precios entre anuncios de diferentes grupos de liquidación.
4. **Shared Inventory Distribution**: Unificación del saldo cripto entre clusters de venta evitando sobre-compromiso de inventario.

---

## 4. Cobertura y Garantías de Testing
- **210 tests unitarios y de integración (100% GREEN)** ejecutables mediante `pytest -v`.
- Invarianza funcional completa certificada tras la migración a `src/`.
