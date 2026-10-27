# Suite de Pruebas Unitarias — Bot P2P Binance ARS

## Filosofía de Testing
Esta suite está diseñada para garantizar la resiliencia y seguridad financiera del bot en escenarios de alta volatilidad y competencia agresiva. Todos los tests se ejecutan de manera **100% offline y determinista**, empleando `unittest.mock` y bases de datos SQLite en memoria (`:memory:`).

## Cobertura de Pruebas (210 tests)
- **Cálculo de Precios y Reposicionamiento (`test_core_units.py`, `test_sell_repositioner.py`):**
  - Reposicionamiento de compras con colchón de seguridad.
  - Escalera de ventas Opción A (High Rotation Ladder): G1 (Base Puesto #1) < G3 (Base + $0.35) < G2 (Base + $0.70).
  - Cumplimiento de la Regla 5.1 de Binance (separación anti-colisión > $0.15 ARS, Error 187055).
- **Protección de Break-Even y Guardarraíles (`test_sell_profit_cushion_guardrail.py`, `test_sell_guardrails.py`):**
  - Blindaje estricto contra ventas a pérdida sobre costo promedio ponderado WAC.
  - Ajuste automático al piso de seguridad ante caídas del libro de órdenes.
  - Validación de desvío máximo vs oráculo Fiwind.
- **Microestructura y Red (`test_market_scanner.py`, `test_p2p_filters_and_merchants.py`):**
  - Concurrencia con semáforos en escaneo de carteleras.
  - Filtrado de comerciantes verificados (`publisherType='merchant'`).
  - Filtrado por tamaño de ticket de competidores.
- **Antiban y Cooldowns (`test_audit_critical_5_fixes.py`, `test_audit_fixes.py`):**
  - Respeto de tiempos de cooldown entre creaciones de anuncios (15s para evitar error 187000).
  - Detección de guerras de precios y circuit breaker de 10 minutos ante errores de API.
- **Inventario Compartido y Liquidez (`test_sell_shared_inventory_sync.py`, `test_incident_liquidity_fix.py`):**
  - Sincronización del 100% del stock libre en Fondos para todos los anuncios de venta.
  - Límites transaccionales dinámicos (50% a 100% de la capacidad).
  - Tracking de órdenes y cálculo de saldo auditado.

## Ejecución
```bash
python -m pytest tests -v
```
