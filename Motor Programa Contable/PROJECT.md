# Project: CryptoTax Pro

## Architecture
El backend en `webapp/backend/` sigue una arquitectura limpia y modular donde ningún archivo productivo supera las 500 líneas:

- `webapp/backend/app.py`: Punto de entrada Flask, configuración de CORS y registro de Blueprints.
- `webapp/backend/db/`: Capa de base de datos SQLite (`transactions.db`):
  - `connection.py`: Gestión de conexiones SQLite con WAL y timeouts.
  - `schema.py`: Definición e inicialización de tablas e índices.
  - `migrations.py`: Migraciones incrementales e idempotentes de esquema.
- `webapp/backend/models/`: Modelos de dominio e invariantes contables:
  - `canonical_hash.py`: `compute_canonical_tx_hash` con normalización UTC y extracción determinista de Order IDs.
  - `exchange_names.py`: `get_canonical_exchange_root` y normalización de nombres de exchanges.
  - `exceptions.py`: Excepciones de dominio (`CertifiedPeriodLockError`, `DuplicateTransactionError`, etc.).
- `webapp/backend/services/`: Motores de negocio y servicios de aplicación:
  - `transactions_service.py`: Persistencia transaccional, filtros, deduplicación y guardias de períodos certificados.
  - `certifications_service.py`: Gestión de certificaciones contables y reemplazo atómico de períodos certificados.
  - `fifo_engine.py`: Motor de costeo FIFO, valuación ARS en swaps cripto-cripto, ajustes sintéticos de brechas y desempate determinista de timestamps.
  - `reconciliation_engine.py`: Motor de conciliación contable y auditoría de anomalías sin efecto cascada.
  - `tax_service.py`: Motor impositivo argentino (Ganancias e IIBB).
  - `kpi_service.py` y `gap_service.py`: Cálculo de KPIs, spreads, curvas de capital y detección de brechas temporales.
  - `operational_excel_service.py`: Generación de libros Excel operativos con fórmulas vivas.
  - `pdf_table_extractor.py`: Extractor vectorial de tablas desde certificaciones PDF.
  - `config_service.py`: Gestión de configuraciones y credenciales `.env`.
- `webapp/backend/parsers/`: Parsers de archivos por exchange (`exchange_detector.py`, `base_parser.py`, `binance_parser.py`, `bitso_parser.py`, `fiwind_parser.py`, `ripio_parser.py`, `universal_parser.py`).
- `webapp/backend/api_clients/`: Conectores de APIs externas (`ccxt_client.py`, `binance_client.py`, `fiwind_client.py`, `lemon_client.py`).
- `webapp/backend/routes/`: Endpoints HTTP organizados en Flask Blueprints (`transactions_bp.py`, `certifications_bp.py`, `reports_bp.py`, `reconciliation_bp.py`, `stats_bp.py`, `taxes_bp.py`, `exchanges_bp.py`, `system_bp.py`).
- `webapp/backend/compat/`: Fachadas retrocompatibles (`db_manager.py`, `processor_lib.py`, `api_manager.py`, `models_v2.py`, `fifo_engine.py`, `reconciliation.py`).
- `webapp/backend/utils/`: Utilidades de soporte (`async_helper.py`, `status_cache.py`, `pdf_cert_helper.py`).
- `webapp/backend/tests/`: Suite unificada de tests (`test_*.py` y `conftest.py`) con aislamiento estricto de base de datos.
- `scripts/`: Herramientas CLI de auditoría, gobernanza y verificación (`audit_deep_system.py`, `enforce_clean_roots.py`, `verify_fifo_cli.py`, `verify_operational_excel_cli.py`, `verify_real_flow_cli.py`).

## Feature Inventory
Every feature from the Survey phase is enumerated here with its assigned milestone:
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Certified Range & Overwrite Protection | Prevent insertions into certified date ranges; prevent deletion/update of certified records | M1 | survey |
| 2 | Timezone & Canonical Hash Normalization | UTC conversion before canonical hash generation; fix order ID extraction & exchange root resolution | M1 | survey |
| 3 | Exchange Parser Robustness & Column Tolerance | Status candidate recognition ('Resultado', 'Condition'), Fiwind English aliases ('SWAP', 'DEPOSIT'), Ripio non-ARS fiat pairs, fuzzy column matching | M1 | survey |
| 4 | Reconciliation Path & Immutability Integration | Fix reconciliation DB path (point to transactions.db), verify deduplication across API vs CSV imports | M1 | survey |
| 5 | Crypto-Crypto Swaps ARS Valuation | Prevent $0.0 cost basis in FIFO for crypto-crypto swaps; compute ARS valuation via intermediate rate/quote | M2 | survey |
| 6 | Synthetic Balance Gap Valuation | Synthetic adjustments for unmatched sales assigned proper valuation to prevent $0.0 cost basis inflation | M2 | survey |
| 7 | Deterministic Timestamp Collision Sorting | Secondary/tertiary deterministic sorting for same-second transactions beyond random hash | M2 | survey |
| 8 | Argentina Tax Engine Deductions & Accuracy | Fix double-deduction in `ganancias_deduccion` across sub-reports, exact Ganancias & IIBB calculations | M2 | survey |
| 9 | Test Infrastructure & Isolated Fixtures | `conftest.py` with isolated temp DB, fix discovery of `run_tests`/`run_real_flow_test` | M3 | survey |
| 10 | Corrupted & Edge Case Test Suite | Test malformed/corrupted CSVs/Excels/ZIPs, boundary inputs, missing headers | M3 | survey |
| 11 | High-Volume Stress Benchmarks | 10k to 100k transaction benchmark stress tests, performance assertion | M3 | survey |
| 12 | End-to-End Accounting Verification Suite | Full E2E test suite covering all features Tier 1-4 | M-E2E | survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Dynamic Parsing & Certified Protection | R1 parsing/deduplication hardening & R2 DB immutability guards | none | DONE |
| 2 | FIFO Accounting & Argentina Tax Engine | R3 FIFO cost basis, crypto swaps, balance gap valuation, tax calculations | M1 | DONE |
| 3 | Test Infra, Corrupted Files & Stress Suite | R4 Pytest infrastructure, corrupted/malformed files, stress benchmarks | M1, M2 | DONE |
| M-E2E | E2E Testing Suite Track | Requirement-driven E2E test suite across Tiers 1-4 | none | DONE |

## Interface Contracts
### `parsers/` & `models/` ↔ `services/` & `db/`
- `compute_canonical_tx_hash(tx_dict)`: Returns deterministic 32-char hex hash after converting timestamps to UTC ISO format (`YYYY-MM-DD THH:MM:SSZ`) and extracting full order IDs (alphanumeric/short).
- `get_canonical_exchange_root(exchange_str)`: Normalizes exchange string to canonical root.
- `is_certified` protection in `services/transactions_service.py`: `insert_transactions()` rejects/ignores transactions falling in certified date ranges. `delete_transactions_by_exchange()` and `recalculate_fifo_costs_db()` skip rows where `is_certified == 1`.

### `services/fifo_engine.py` ↔ `services/transactions_service.py` / `routes/`
- `calculate_fifo(transactions)`: Processes FIFO queue without modifying `cotizacion_compra` of certified rows. Resolves same-second order by (`fecha ASC`, `tx_type_priority ASC`, `id ASC`).
- Crypto-crypto swap valuation: assign ARS value to quote asset at swap timestamp.

## Code Layout
- Main backend packages: `webapp/backend/{db,models,services,parsers,api_clients,routes,compat,utils,domain,workers}/`
- Database: `webapp/backend/transactions.db` (accedida mediante `webapp/backend/db/connection.py`)
- Frontend application: `webapp/frontend/src/{pages,components,utils}/`
- Test suite: `webapp/backend/tests/test_*.py`, `webapp/backend/tests/conftest.py`
- Verification & governance CLI scripts: `scripts/{audit_deep_system.py,enforce_clean_roots.py,verify_fifo_cli.py,verify_operational_excel_cli.py,verify_real_flow_cli.py}`
