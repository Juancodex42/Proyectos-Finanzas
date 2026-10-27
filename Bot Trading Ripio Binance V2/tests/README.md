# Suite de Pruebas Unitarias — Bot Trading Ripio Binance V2

## Filosofía de Testing
Esta suite está diseñada para ejecutarse de forma **100% offline, determinista y sin dependencias externas** (red, APIs ni credenciales). Utiliza `unittest.mock` y series sintéticas calibradas para verificar la integridad de la microestructura matemática y la lógica de enrutamiento.

## Estructura de Tests
- `test_bot.py`:
  - `test_project_structure_and_engineering_guidelines`: Valida existencia de arquitectura limpia y límites de líneas.
  - `test_config_loader_without_env_file`: Verifica que el cargador de configuración funcione limpiamente aun sin archivo `.env`.
  - `test_domain_models_and_pure_quant_math`: Valida cálculos puros: Sharpe, Sortino, Max Drawdown, Half-Life OU, Z-Score, Avellaneda-Stoikov y Cointegración ADF.
  - `test_ripio_api_hmac_query_params_and_429_max_retries`: Valida firmas criptográficas HMAC SHA256 y política de reintentos exponenciales ante HTTP 429.
  - `test_state_manager_isolation_and_dual_keys`: Valida atomicidad y claves duales en el gestor de estado.
  - `test_portfolio_manager_offline`: Valida cálculos de exposición y respeto de límites de riesgo de inventario.
  - `test_avellaneda_stoikov_inventory_shift_and_yaml_keys`: Valida sesgo de precios de reserva según inventario $q$.
  - `test_statistical_arbitrage_signal_and_trade_recording`: Valida generación de señal, apertura y cierre con cálculo de PnL.
  - `test_inter_exchange_router_inverse_pair_and_optimal_route`: Valida comparación entre ruta directa y rutas de puente multicadena (TRC20, BEP20, ERC20).
  - `test_backtester_real_fees_mtm_drawdown_and_luck_vs_skill`: Valida motor de simulación con comisiones reales de maker/taker y test de significancia estadística.
  - `test_data_loader_collector_csv_compatibility`: Valida compatibilidad con datasets históricos.
- `test_telegram.py`:
  - `test_telegram_authorization_fail_closed`: Valida protección y autenticación de usuarios por Chat ID.
  - `test_telegram_state_keys_and_commands`: Valida respuestas de comandos (`/status`, `/stats`, `/balance`).
  - `test_automation_manager_health_and_real_backtest`: Valida tareas automatizadas de salud y backtest.

## Ejecución
```bash
python -m pytest tests -v
```
