# E2E Test Suite Ready

## Test Runner
- Command (Full Test Suite): `python -m pytest webapp/backend/tests/ -v`
- Command (Architecture Governance): `python -m pytest webapp/backend/tests/test_architecture_governance.py -v`
- Command (Root Cleanliness Audit): `python scripts/enforce_clean_roots.py`
- Command (Deep System AST & Route Audit): `python scripts/audit_deep_system.py`
- CLI Verification Scripts (`scripts/`):
  - `python scripts/verify_fifo_cli.py`
  - `python scripts/verify_operational_excel_cli.py`
  - `python scripts/verify_real_flow_cli.py`

## Modular Architecture Under Test
- `webapp/backend/db/`: SQLite connection, schema, and migrations (`connection.py`, `schema.py`, `migrations.py`)
- `webapp/backend/models/`: Canonical hash generation, exchange normalization, and domain exceptions
- `webapp/backend/services/`: Transactions, Certifications, FIFO Engine, Reconciliation Engine, Tax Engine, KPIs, Gaps, Operational Excel, and PDF Extractor
- `webapp/backend/parsers/`: Exchange detector and specialized parsers (Binance, Bitso, Fiwind, Ripio, Universal)
- `webapp/backend/api_clients/`: CCXT, Binance, Fiwind, and Lemon API clients
- `webapp/backend/routes/`: Modular Flask Blueprints (`transactions_bp`, `certifications_bp`, `reports_bp`, `reconciliation_bp`, `stats_bp`, `taxes_bp`, `exchanges_bp`, `system_bp`)
- `webapp/backend/compat/`: Backward-compatible thin facades (`db_manager.py`, `processor_lib.py`, `api_manager.py`, `models_v2.py`, `fifo_engine.py`, `reconciliation.py`)
- `webapp/backend/utils/`: Shared utilities (`async_helper.py`, `status_cache.py`, `pdf_cert_helper.py`)
- `webapp/backend/tests/`: Isolated pytest test suites (`conftest.py` and `test_*.py`)

## Coverage Summary
| Tier | Count | Description |
|------|------:|-------------|
| 1. Feature Coverage | 60 | 5 test cases per feature across all 12 features |
| 2. Boundary & Corner | 60 | 5 test cases per feature for edge cases & limits |
| 3. Cross-Feature | 12 | Pairwise interaction scenarios |
| 4. Real-World Application | 6 | Multi-exchange end-to-end lifecycle scenarios |
| Master Aggregator & Governance Suites | 22+ | Component discovery, DB isolation, upload robustness, architecture & root governance |
| **Total** | **160+** | **100% Pass Rate under pytest (isolated tmp_path DB)** |

## Feature Checklist
| Feature | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---------|:------:|:------:|:------:|:------:|
| 1. Certified Range & Overwrite Protection | 5 | 5 | ✓ | ✓ |
| 2. Timezone & Canonical Hash Normalization | 5 | 5 | ✓ | ✓ |
| 3. Exchange Parser Robustness & Column Tolerance | 5 | 5 | ✓ | ✓ |
| 4. Reconciliation Path & Immutability Integration | 5 | 5 | ✓ | ✓ |
| 5. Crypto-Crypto Swaps ARS Valuation | 5 | 5 | ✓ | ✓ |
| 6. Synthetic Balance Gap Valuation | 5 | 5 | ✓ | ✓ |
| 7. Deterministic Timestamp Collision Sorting | 5 | 5 | ✓ | ✓ |
| 8. Argentina Tax Engine Deductions & Accuracy | 5 | 5 | ✓ | ✓ |
| 9. Test Infrastructure & Isolated Fixtures | 5 | 5 | ✓ | ✓ |
| 10. Corrupted & Edge Case Test Suite | 5 | 5 | ✓ | ✓ |
| 11. High-Volume Stress Benchmarks | 5 | 5 | ✓ | ✓ |
| 12. End-to-End Accounting Verification Suite | 5 | 5 | ✓ | ✓ |
