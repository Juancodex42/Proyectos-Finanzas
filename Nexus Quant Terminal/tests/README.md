# Suite de Pruebas Unitarias — Nexus Quant Terminal

## Filosofía de Testing
Esta suite está diseñada para garantizar la exactitud matemática, la robustez ante datos corruptos o anómalos y la estabilidad de los motores cuantitativos. Todas las pruebas (516 tests) son **100% deterministas, reproducibles y offline**, ejecutándose sin dependencias de red externa ni necesidad de API keys de Binance ni de Telegram.

## Cobertura de la Suite (516 tests)
- **Simuladores de Campaña Cuantitativa (`test_barbell_*.py`, `test_triple_barrier_simulator.py`, `test_simulator_integrity.py`):**
  - Simulación de rachas y gestión de capital Barbell.
  - Método de Barrera Triple de Marcos López de Prado (Profit Taking, Stop Loss, Expiración temporal).
  - Cálculo de Sharpe, Sortino, Calmar, Max Drawdown y tasa de aciertos Out-of-Sample.
- **Estrategias y Exportadores (`test_pinescript_all_13_strategies.py`, `test_strategies_8_to_13_validation.py`):**
  - Validación de las 13 estrategias algorítmicas (ISLG, Bollinger Mean-Reversion, Supertrend, etc.).
  - Generación fiel de scripts en PineScript v5 y código Python standalone.
- **Microestructura y Dual-Bot (`test_binance_dual_bot.py`, `test_signal_dispatcher.py`, `test_telegram_bot.py`):**
  - Ejecución en Binance Futures en modo sandbox/mock.
  - Desplazamiento seguro de Stop Loss a Breakeven.
  - Telemetría asíncrona de alertas y reportes para Telegram.
- **Hardening y Stress Testing (`test_adversarial_stress_and_fuzz.py`, `test_tier1_to_tier5_*.py`):**
  - Pruebas de fuzzing y resiliencia ante inputs maliciosos o corruptos.
  - Validación de sanitización de símbolos y TimeFrames contra inyecciones de comandos.
  - Respeto de encabezados de endurecimiento HTTP (CSP, nosniff, Frame Options).
- **Interfaz Gráfica y Visual System (`test_ui_visual_system.py`, `test_m1_to_m3_*.py`):**
  - Verificación de consistencia de clases CSS, paletas de colores y layouts responsive.

## Ejecución
```bash
python -m pytest tests -v
```
