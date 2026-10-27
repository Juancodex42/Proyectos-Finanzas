# CryptoTax Pro - Sistema Contable de Criptomonedas

Este proyecto es un motor y sistema contable para el procesamiento de transacciones financieras de criptomonedas provenientes de diferentes exchanges (Binance, Bitso, Fiwind, Ripio, Lemon, Bybit, etc.), con cálculo de costos FIFO e impuestos (Ganancias e IIBB) para Argentina.

---

## 📦 Requisitos e Instalación Inicial

### Requisitos Previos
* **Python 3.10 o superior**
* **Node.js 18 o superior** y **npm**

### 1. Clonar el Repositorio
```bash
git clone <URL_DEL_REPOSITORIO>
cd "Motor Programa Contable"
```

### 2. Configurar Entorno Backend (Python)
```bash
python -m venv .venv
# En Windows (PowerShell / CMD):
.venv\Scripts\activate
# En Linux / macOS:
source .venv/bin/activate

pip install -r webapp/backend/requirements.txt
```

### 3. Configuración de Variables de Entorno (Opcional)
Para sincronización en vivo con APIs de exchanges:
```bash
# Copiar plantilla segura
copy webapp\backend\.env.example webapp\backend\.env
# Completar las claves deseadas en webapp/backend/.env
```

### 4. Instalar Dependencias Frontend (React + Vite)
```bash
cd webapp/frontend
npm install
cd ../..
```

---

## 🚀 Cómo Iniciar la Aplicación

Tienes tres formas de iniciar el sistema desde la raíz del proyecto:

1. **Modo Silencioso (Recomendado para uso diario):**
   * Haz doble clic en el archivo [launch_silent.vbs](launch_silent.vbs) o ejecuta `python start_system.py`.
   * Iniciará el Backend (`webapp/backend/app.py`) y el Frontend (`webapp/frontend`) en segundo plano y abrirá automáticamente la interfaz visual en tu navegador predeterminado.
   * **Para cerrarlo:** Haz doble clic en [stop_app.bat](stop_app.bat) o ejecuta `python stop_system.py`.

2. **Modo Consola (Recomendado para desarrollo/depuración):**
   * Haz doble clic en [run_app.bat](run_app.bat).
   * Iniciará el Backend y el Frontend mostrando las consolas para ver logs y posibles errores en tiempo real.

3. **Inicio Manual por Terminal:**
   * **Backend:** `python webapp/backend/app.py`
   * **Frontend:** `npm --prefix webapp/frontend run dev`

---

## 📁 Estructura del Proyecto

* **[webapp/](webapp):** Contiene el código fuente productivo de la aplicación:
  * `webapp/backend/`: API modular construida en Python (Flask), encargada de la lógica contable, base de datos (`transactions.db`) y procesamiento:
    * `db/`: Conexión SQLite (`connection.py`), esquema (`schema.py`) y migraciones (`migrations.py`).
    * `models/`: Modelos canónicos, hashing determinista (`canonical_hash.py`), normalización de exchanges (`exchange_names.py`) y excepciones (`exceptions.py`).
    * `services/`: Servicios de dominio (`transactions_service.py`, `certifications_service.py`, `tax_service.py`, `kpi_service.py`, `gap_service.py`, `fifo_engine.py`, `reconciliation_engine.py`, `operational_excel_service.py`, `config_service.py`, `pdf_table_extractor.py`).
    * `parsers/`: Detectores y parsers especializados por exchange (`exchange_detector.py`, `binance_parser.py`, `bitso_parser.py`, `fiwind_parser.py`, `ripio_parser.py`, `universal_parser.py`).
    * `api_clients/`: Clientes de sincronización con exchanges (`ccxt_client.py`, `binance_client.py`, `fiwind_client.py`, `lemon_client.py`).
    * `routes/`: Flask Blueprints (`transactions_bp.py`, `certifications_bp.py`, `reports_bp.py`, `reconciliation_bp.py`, `stats_bp.py`, `taxes_bp.py`, `exchanges_bp.py`, `system_bp.py`).
    * `compat/`: Fachadas retrocompatibles (`db_manager.py`, `processor_lib.py`, `api_manager.py`, `models_v2.py`, `fifo_engine.py`, `reconciliation.py`).
    * `utils/`: Utilidades transversales (`async_helper.py`, `status_cache.py`, `pdf_cert_helper.py`).
    * `tests/`: Suite de tests automatizados (`pytest webapp/backend/tests/ -v`).
  * `webapp/frontend/`: Interfaz visual web construida en React + Vite.
* **[docs/](docs):** Documentación técnica y arquitectónica en profundidad. Consulta [docs/LOGICA_CORE_FIFO_MATCHING_SANEAMIENTO.md](docs/LOGICA_CORE_FIFO_MATCHING_SANEAMIENTO.md) para el desglose detallado de módulos, funciones, imports y algoritmos del motor FIFO, matching bancario/inter-exchange, saneamiento y auditoría de ledger.
* **[scripts/](scripts):** Utilidades CLI, auditoría de arquitectura y herramientas de verificación (`audit_deep_system.py`, `enforce_clean_roots.py`, `verify_fifo_cli.py`, `verify_operational_excel_cli.py`, `verify_real_flow_cli.py`).
* **Archivos Raíz:** Únicamente archivos de configuración (`mappings.json`), documentación (`README.md`, `PROJECT.md`, `TEST_READY.md`, `TEST_INFRA.md`), lanzadores (`.vbs`, `.bat`, `start_system.py`, `stop_system.py`) y recursos visuales (`app.ico`).

---

## 🧹 Directrices para Código de Prueba y Gobernanza

Para mantener la raíz del proyecto **limpia y ordenada**, se establece la siguiente regla obligatoria:

> [!IMPORTANT]
> * **Todos los tests automatizados (`test_*.py`)** deben residir exclusivamente dentro de `webapp/backend/tests/`.
> * **Todo script CLI de verificación, auditoría o mantenimiento** debe guardarse dentro de `scripts/` utilizando el prefijo `verify_*` o nombre descriptivo (nunca `test_*.py`).
> * Puedes validar el cumplimiento en cualquier momento ejecutando:
>   ```bash
>   python scripts/enforce_clean_roots.py
>   pytest webapp/backend/tests/test_architecture_governance.py -v
>   ```

---

## 🏗️ Arquitectura y Flujo del Sistema

El sistema está diseñado bajo una arquitectura cliente-servidor modular (Frontend-Backend). Esta sección se genera **dinámicamente** escaneando los paquetes modulares reales de `webapp/backend/` (`db/`, `models/`, `parsers/`, `routes/`, `services/`, `api_clients/`, `compat/`, `utils/`, `workers/`) y analizando las dependencias de importación del código fuente.

### 📊 Diagrama de Dependencias y Flujo de Control

```mermaid
graph TD
    %% Entidades Externas y Frontend
    User((Usuario))
    Browser[Navegador Web<br/>Frontend React/Vite]

    subgraph "Backend Modular (Flask)"
        app["app.py<br/>(API Principal)"]
        conftest["conftest.py"]
        exceptions["exceptions.py"]
        db_connection["db/connection.py"]
        models_cpa_seed_data["models/cpa_seed_data.py"]
        models_operational_models["models/operational_models.py"]
        models_transaction_models["models/transaction_models.py"]
        parsers_archive_processor["parsers/archive_processor.py"]
        parsers_bank_parsers["parsers/bank_parsers.py"]
        parsers_bank_statement_parser["parsers/bank_statement_parser.py"]
        parsers_base_parser["parsers/base_parser.py"]
        parsers_binance_helpers["parsers/binance_helpers.py"]
        parsers_binance_parser["parsers/binance_parser.py"]
        parsers_bitget_parser["parsers/bitget_parser.py"]
        parsers_bitso_parser["parsers/bitso_parser.py"]
        parsers_deskew_helper["parsers/deskew_helper.py"]
        parsers_dispatcher["parsers/dispatcher.py"]
        parsers_excel_multi_processor["parsers/excel_multi_processor.py"]
        parsers_exchange_detector["parsers/exchange_detector.py"]
        parsers_file_preview["parsers/file_preview.py"]
        parsers_fiwind_parser["parsers/fiwind_parser.py"]
        parsers_ocr_helper["parsers/ocr_helper.py"]
        parsers_okx_parser["parsers/okx_parser.py"]
        parsers_other_exchanges_parser["parsers/other_exchanges_parser.py"]
        parsers_parallel_extractor["parsers/parallel_extractor.py"]
        parsers_pdf_cert_helper["parsers/pdf_cert_helper.py"]
        parsers_pdf_table_extractor["parsers/pdf_table_extractor.py"]
        parsers_ripio_helpers["parsers/ripio_helpers.py"]
        parsers_ripio_parser["parsers/ripio_parser.py"]
        routes_api_sync_bp["routes/api_sync_bp.py"]
        routes_audit_declarations_bp["routes/audit_declarations_bp.py"]
        routes_certifications_bp["routes/certifications_bp.py"]
        routes_reconciliation_bp["routes/reconciliation_bp.py"]
        routes_reports_bp["routes/reports_bp.py"]
        routes_reports_helpers["routes/reports_helpers.py"]
        routes_settings_bp["routes/settings_bp.py"]
        routes_transactions_bp["routes/transactions_bp.py"]
        services_analytics_service["services/analytics_service.py"]
        services_auto_sync_daemon["services/auto_sync_daemon.py"]
        services_bank_persistence_service["services/bank_persistence_service.py"]
        services_bank_reconciliation_service["services/bank_reconciliation_service.py"]
        services_cache_service["services/cache_service.py"]
        services_certifications_service["services/certifications_service.py"]
        services_config_service["services/config_service.py"]
        services_exchanges_service["services/exchanges_service.py"]
        services_fifo_service["services/fifo_service.py"]
        services_gap_enrichment_service["services/gap_enrichment_service.py"]
        services_gap_service["services/gap_service.py"]
        services_monthly_custody_service["services/monthly_custody_service.py"]
        services_operational_excel_service["services/operational_excel_service.py"]
        services_orphan_transfer_service["services/orphan_transfer_service.py"]
        services_price_lookup_service["services/price_lookup_service.py"]
        services_reconciliation_service["services/reconciliation_service.py"]
        services_source_declarations_service["services/source_declarations_service.py"]
        services_source_freshness_service["services/source_freshness_service.py"]
        services_tax_anomaly_service["services/tax_anomaly_service.py"]
        services_tax_service["services/tax_service.py"]
        services_transaction_dedup_service["services/transaction_dedup_service.py"]
        services_transactions_service["services/transactions_service.py"]
        api_clients_binance_client["api_clients/binance_client.py"]
        api_clients_bitget_client["api_clients/bitget_client.py"]
        api_clients_bitso_client["api_clients/bitso_client.py"]
        api_clients_bybit_client["api_clients/bybit_client.py"]
        api_clients_common["api_clients/common.py"]
        api_clients_date_chunker["api_clients/date_chunker.py"]
        api_clients_manager["api_clients/manager.py"]
        api_clients_other_clients["api_clients/other_clients.py"]
        compat_api_manager["compat/api_manager.py"]
        compat_async_helper["compat/async_helper.py"]
        compat_config_manager["compat/config_manager.py"]
        compat_db_manager["compat/db_manager.py"]
        compat_exceptions["compat/exceptions.py"]
        compat_fifo_engine["compat/fifo_engine.py"]
        compat_models_v2["compat/models_v2.py"]
        compat_pdf_cert_helper["compat/pdf_cert_helper.py"]
        compat_pdf_table_extractor["compat/pdf_table_extractor.py"]
        compat_processor_lib["compat/processor_lib.py"]
        compat_reconciliation["compat/reconciliation.py"]
        compat_status_cache["compat/status_cache.py"]
        utils_async_helper["utils/async_helper.py"]
        utils_exceptions["utils/exceptions.py"]
        utils_status_cache["utils/status_cache.py"]
        workers_auto_sync_worker["workers/auto_sync_worker.py"]
        DB[(transactions.db<br/>SQLite)]
    end

    User -- "Interacciona" --> Browser
    Browser -- "Llamadas HTTP API" --> app
    db_connection --> DB
    %% Relaciones Dinámicas de Código
    api_clients_binance_client -.-> compat_db_manager
    api_clients_binance_client -.-> models_transaction_models
    api_clients_binance_client -.-> parsers_base_parser
    api_clients_bitget_client -.-> compat_db_manager
    api_clients_bitget_client -.-> models_transaction_models
    api_clients_bitget_client -.-> parsers_base_parser
    api_clients_bitso_client -.-> models_transaction_models
    api_clients_bybit_client -.-> compat_db_manager
    api_clients_bybit_client -.-> models_transaction_models
    api_clients_common -.-> db_connection
    api_clients_common -.-> models_transaction_models
    api_clients_common -.-> services_tax_service
    api_clients_manager -.-> compat_db_manager
    api_clients_manager -.-> db_connection
    api_clients_manager -.-> services_fifo_service
    api_clients_manager -.-> utils_async_helper
    api_clients_other_clients -.-> compat_db_manager
    api_clients_other_clients -.-> models_transaction_models
    app -.-> compat_db_manager
    app -.-> parsers_pdf_cert_helper
    app -.-> services_auto_sync_daemon
    compat_async_helper -.-> utils_async_helper
    compat_config_manager -.-> services_config_service
    compat_db_manager -.-> db_connection
    compat_db_manager -.-> services_analytics_service
    compat_db_manager -.-> services_certifications_service
    compat_db_manager -.-> services_exchanges_service
    compat_db_manager -.-> services_fifo_service
    compat_db_manager -.-> services_gap_service
    compat_db_manager -.-> services_tax_service
    compat_db_manager -.-> services_transactions_service
    compat_exceptions -.-> utils_exceptions
    compat_fifo_engine -.-> services_fifo_service
    compat_models_v2 -.-> models_transaction_models
    compat_pdf_cert_helper -.-> parsers_pdf_cert_helper
    compat_pdf_table_extractor -.-> parsers_pdf_table_extractor
    compat_reconciliation -.-> services_reconciliation_service
    compat_status_cache -.-> utils_status_cache
    db_connection -.-> models_transaction_models
    db_connection -.-> services_certifications_service
    exceptions -.-> utils_exceptions
    models_transaction_models -.-> models_cpa_seed_data
    models_transaction_models -.-> services_price_lookup_service
    parsers_archive_processor -.-> compat_processor_lib
    parsers_bank_parsers -.-> models_operational_models
    parsers_bank_parsers -.-> parsers_base_parser
    parsers_bank_statement_parser -.-> models_operational_models
    parsers_bank_statement_parser -.-> parsers_bank_parsers
    parsers_base_parser -.-> compat_config_manager
    parsers_base_parser -.-> compat_exceptions
    parsers_base_parser -.-> models_transaction_models
    parsers_base_parser -.-> services_config_service
    parsers_base_parser -.-> services_tax_service
    parsers_base_parser -.-> utils_exceptions
    parsers_binance_helpers -.-> compat_exceptions
    parsers_binance_helpers -.-> models_transaction_models
    parsers_binance_helpers -.-> parsers_base_parser
    parsers_binance_parser -.-> compat_db_manager
    parsers_binance_parser -.-> compat_exceptions
    parsers_binance_parser -.-> models_transaction_models
    parsers_binance_parser -.-> parsers_archive_processor
    parsers_binance_parser -.-> parsers_base_parser
    parsers_binance_parser -.-> parsers_binance_helpers
    parsers_bitget_parser -.-> compat_exceptions
    parsers_bitget_parser -.-> models_transaction_models
    parsers_bitget_parser -.-> parsers_base_parser
    parsers_bitso_parser -.-> compat_config_manager
    parsers_bitso_parser -.-> compat_exceptions
    parsers_bitso_parser -.-> models_transaction_models
    parsers_bitso_parser -.-> parsers_base_parser
    parsers_bitso_parser -.-> services_config_service
    parsers_dispatcher -.-> compat_db_manager
    parsers_dispatcher -.-> compat_exceptions
    parsers_dispatcher -.-> utils_exceptions
    parsers_excel_multi_processor -.-> models_transaction_models
    parsers_excel_multi_processor -.-> parsers_base_parser
    parsers_exchange_detector -.-> db_connection
    parsers_exchange_detector -.-> parsers_base_parser
    parsers_fiwind_parser -.-> compat_config_manager
    parsers_fiwind_parser -.-> compat_exceptions
    parsers_fiwind_parser -.-> models_transaction_models
    parsers_fiwind_parser -.-> parsers_base_parser
    parsers_fiwind_parser -.-> services_config_service
    parsers_ocr_helper -.-> parsers_deskew_helper
    parsers_okx_parser -.-> parsers_base_parser
    parsers_okx_parser -.-> parsers_other_exchanges_parser
    parsers_other_exchanges_parser -.-> compat_exceptions
    parsers_other_exchanges_parser -.-> models_transaction_models
    parsers_other_exchanges_parser -.-> parsers_base_parser
    parsers_other_exchanges_parser -.-> utils_exceptions
    parsers_parallel_extractor -.-> parsers_deskew_helper
    parsers_parallel_extractor -.-> parsers_ocr_helper
    parsers_pdf_cert_helper -.-> compat_db_manager
    parsers_pdf_cert_helper -.-> parsers_ocr_helper
    parsers_pdf_table_extractor -.-> models_transaction_models
    parsers_pdf_table_extractor -.-> parsers_ocr_helper
    parsers_pdf_table_extractor -.-> parsers_parallel_extractor
    parsers_ripio_helpers -.-> compat_exceptions
    parsers_ripio_helpers -.-> models_transaction_models
    parsers_ripio_helpers -.-> parsers_base_parser
    parsers_ripio_parser -.-> compat_config_manager
    parsers_ripio_parser -.-> compat_exceptions
    parsers_ripio_parser -.-> models_transaction_models
    parsers_ripio_parser -.-> parsers_base_parser
    parsers_ripio_parser -.-> services_config_service
    routes_api_sync_bp -.-> compat_api_manager
    routes_api_sync_bp -.-> compat_async_helper
    routes_api_sync_bp -.-> compat_db_manager
    routes_api_sync_bp -.-> compat_status_cache
    routes_api_sync_bp -.-> services_cache_service
    routes_api_sync_bp -.-> services_fifo_service
    routes_audit_declarations_bp -.-> services_source_declarations_service
    routes_certifications_bp -.-> compat_db_manager
    routes_certifications_bp -.-> compat_pdf_cert_helper
    routes_certifications_bp -.-> compat_pdf_table_extractor
    routes_certifications_bp -.-> parsers_pdf_table_extractor
    routes_certifications_bp -.-> services_cache_service
    routes_reconciliation_bp -.-> compat_db_manager
    routes_reconciliation_bp -.-> compat_reconciliation
    routes_reconciliation_bp -.-> parsers_bank_parsers
    routes_reconciliation_bp -.-> parsers_base_parser
    routes_reconciliation_bp -.-> services_bank_persistence_service
    routes_reconciliation_bp -.-> services_bank_reconciliation_service
    routes_reconciliation_bp -.-> services_cache_service
    routes_reconciliation_bp -.-> services_certifications_service
    routes_reports_bp -.-> compat_api_manager
    routes_reports_bp -.-> compat_db_manager
    routes_reports_bp -.-> compat_processor_lib
    routes_reports_bp -.-> compat_reconciliation
    routes_reports_bp -.-> services_cache_service
    routes_reports_bp -.-> services_fifo_service
    routes_reports_helpers -.-> compat_config_manager
    routes_reports_helpers -.-> compat_db_manager
    routes_reports_helpers -.-> compat_processor_lib
    routes_reports_helpers -.-> models_transaction_models
    routes_reports_helpers -.-> services_bank_persistence_service
    routes_reports_helpers -.-> services_operational_excel_service
    routes_reports_helpers -.-> utils_status_cache
    routes_settings_bp -.-> compat_config_manager
    routes_settings_bp -.-> compat_db_manager
    routes_settings_bp -.-> services_auto_sync_daemon
    routes_settings_bp -.-> services_cache_service
    routes_settings_bp -.-> utils_status_cache
    routes_transactions_bp -.-> compat_db_manager
    routes_transactions_bp -.-> compat_exceptions
    routes_transactions_bp -.-> compat_processor_lib
    routes_transactions_bp -.-> services_cache_service
    routes_transactions_bp -.-> services_fifo_service
    routes_transactions_bp -.-> services_transactions_service
    services_analytics_service -.-> db_connection
    services_analytics_service -.-> services_cache_service
    services_analytics_service -.-> services_fifo_service
    services_auto_sync_daemon -.-> compat_api_manager
    services_auto_sync_daemon -.-> compat_async_helper
    services_auto_sync_daemon -.-> compat_db_manager
    services_auto_sync_daemon -.-> services_cache_service
    services_auto_sync_daemon -.-> services_fifo_service
    services_bank_persistence_service -.-> db_connection
    services_bank_persistence_service -.-> models_operational_models
    services_bank_persistence_service -.-> models_transaction_models
    services_bank_persistence_service -.-> services_transactions_service
    services_bank_reconciliation_service -.-> db_connection
    services_bank_reconciliation_service -.-> models_operational_models
    services_bank_reconciliation_service -.-> services_bank_persistence_service
    services_certifications_service -.-> db_connection
    services_certifications_service -.-> models_cpa_seed_data
    services_certifications_service -.-> services_cache_service
    services_certifications_service -.-> services_fifo_service
    services_certifications_service -.-> services_transactions_service
    services_exchanges_service -.-> compat_config_manager
    services_exchanges_service -.-> db_connection
    services_exchanges_service -.-> services_config_service
    services_fifo_service -.-> compat_db_manager
    services_fifo_service -.-> db_connection
    services_fifo_service -.-> models_operational_models
    services_fifo_service -.-> models_transaction_models
    services_fifo_service -.-> services_gap_service
    services_gap_enrichment_service -.-> db_connection
    services_gap_enrichment_service -.-> models_transaction_models
    services_gap_enrichment_service -.-> services_monthly_custody_service
    services_gap_enrichment_service -.-> services_orphan_transfer_service
    services_gap_enrichment_service -.-> services_source_declarations_service
    services_gap_enrichment_service -.-> services_source_freshness_service
    services_gap_service -.-> db_connection
    services_gap_service -.-> models_transaction_models
    services_gap_service -.-> services_gap_enrichment_service
    services_gap_service -.-> services_transactions_service
    services_monthly_custody_service -.-> models_transaction_models
    services_monthly_custody_service -.-> services_source_declarations_service
    services_monthly_custody_service -.-> services_source_freshness_service
    services_operational_excel_service -.-> models_operational_models
    services_operational_excel_service -.-> services_bank_persistence_service
    services_orphan_transfer_service -.-> db_connection
    services_orphan_transfer_service -.-> models_transaction_models
    services_orphan_transfer_service -.-> services_monthly_custody_service
    services_orphan_transfer_service -.-> services_source_declarations_service
    services_orphan_transfer_service -.-> services_source_freshness_service
    services_price_lookup_service -.-> db_connection
    services_price_lookup_service -.-> services_tax_service
    services_reconciliation_service -.-> compat_db_manager
    services_reconciliation_service -.-> db_connection
    services_reconciliation_service -.-> models_operational_models
    services_reconciliation_service -.-> models_transaction_models
    services_reconciliation_service -.-> parsers_base_parser
    services_reconciliation_service -.-> services_fifo_service
    services_reconciliation_service -.-> services_transactions_service
    services_source_declarations_service -.-> db_connection
    services_source_declarations_service -.-> models_transaction_models
    services_source_declarations_service -.-> services_cache_service
    services_source_freshness_service -.-> db_connection
    services_source_freshness_service -.-> utils_status_cache
    services_tax_anomaly_service -.-> db_connection
    services_tax_service -.-> db_connection
    services_tax_service -.-> services_cache_service
    services_tax_service -.-> services_fifo_service
    services_tax_service -.-> services_tax_anomaly_service
    services_transaction_dedup_service -.-> db_connection
    services_transaction_dedup_service -.-> models_transaction_models
    services_transactions_service -.-> compat_db_manager
    services_transactions_service -.-> db_connection
    services_transactions_service -.-> models_transaction_models
    services_transactions_service -.-> parsers_base_parser
    services_transactions_service -.-> services_cache_service
    services_transactions_service -.-> services_certifications_service
    services_transactions_service -.-> services_fifo_service
    services_transactions_service -.-> services_reconciliation_service
    services_transactions_service -.-> services_transaction_dedup_service
    utils_status_cache -.-> compat_api_manager
    workers_auto_sync_worker -.-> compat_api_manager
    workers_auto_sync_worker -.-> compat_db_manager
    workers_auto_sync_worker -.-> services_fifo_service
```

> [!NOTE]
> Las líneas punteadas `-.->` indican dependencias directas de importación (`import`) detectadas estáticamente en el código backend.

### 📁 Estructura Detectada del Proyecto

#### Aplicación Web (`webapp/`)
- `webapp/frontend/`: React application (Vite + TypeScript)
- `webapp/backend/`: Python API modular (Flask)

#### Inventario Técnico Modular de Backend (`webapp/backend/`)
- `app.py` - Servidor Flask principal y registro de blueprints.
- `conftest.py`
- `exceptions.py`
- **`db/`** — Conexión SQLite, inicialización de esquema, migraciones y consultas base.
  - `db/connection.py`
- **`models/`** — Modelos de dominio, normalización de exchanges y hash canónico MD5.
  - `models/cpa_seed_data.py`
  - `models/operational_models.py`
  - `models/transaction_models.py`
- **`parsers/`** — Parsers modulares por exchange (CSV/XLSX) y registro unificado de ingesta.
  - `parsers/archive_processor.py`
  - `parsers/bank_parsers.py`
  - `parsers/bank_statement_parser.py`
  - `parsers/base_parser.py`
  - `parsers/binance_helpers.py`
  - `parsers/binance_parser.py`
  - `parsers/bitget_parser.py`
  - `parsers/bitso_parser.py`
  - `parsers/deskew_helper.py`
  - `parsers/dispatcher.py`
  - `parsers/excel_multi_processor.py`
  - `parsers/exchange_detector.py`
  - `parsers/file_preview.py`
  - `parsers/fiwind_parser.py`
  - `parsers/ocr_helper.py`
  - `parsers/okx_parser.py`
  - `parsers/other_exchanges_parser.py`
  - `parsers/parallel_extractor.py`
  - `parsers/pdf_cert_helper.py`
  - `parsers/pdf_table_extractor.py`
  - `parsers/ripio_helpers.py`
  - `parsers/ripio_parser.py`
- **`routes/`** — Blueprints de Flask y endpoints HTTP REST desacoplados por dominio.
  - `routes/api_sync_bp.py`
  - `routes/audit_declarations_bp.py`
  - `routes/certifications_bp.py`
  - `routes/reconciliation_bp.py`
  - `routes/reports_bp.py`
  - `routes/reports_helpers.py`
  - `routes/settings_bp.py`
  - `routes/transactions_bp.py`
- **`services/`** — Lógica de negocio contable (FIFO, huecos, custodia mensual, conciliación, caché, impuestos).
  - `services/analytics_service.py`
  - `services/auto_sync_daemon.py`
  - `services/bank_persistence_service.py`
  - `services/bank_reconciliation_service.py`
  - `services/cache_service.py`
  - `services/certifications_service.py`
  - `services/config_service.py`
  - `services/exchanges_service.py`
  - `services/fifo_service.py`
  - `services/gap_enrichment_service.py`
  - `services/gap_service.py`
  - `services/monthly_custody_service.py`
  - `services/operational_excel_service.py`
  - `services/orphan_transfer_service.py`
  - `services/price_lookup_service.py`
  - `services/reconciliation_service.py`
  - `services/source_declarations_service.py`
  - `services/source_freshness_service.py`
  - `services/tax_anomaly_service.py`
  - `services/tax_service.py`
  - `services/transaction_dedup_service.py`
  - `services/transactions_service.py`
- **`api_clients/`** — Conectores y clientes para sincronización con APIs de exchanges.
  - `api_clients/binance_client.py`
  - `api_clients/bitget_client.py`
  - `api_clients/bitso_client.py`
  - `api_clients/bybit_client.py`
  - `api_clients/common.py`
  - `api_clients/date_chunker.py`
  - `api_clients/manager.py`
  - `api_clients/other_clients.py`
- **`compat/`** — Fachadas de compatibilidad retroactiva para módulos históricos.
  - `compat/api_manager.py`
  - `compat/async_helper.py`
  - `compat/config_manager.py`
  - `compat/db_manager.py`
  - `compat/exceptions.py`
  - `compat/fifo_engine.py`
  - `compat/models_v2.py`
  - `compat/pdf_cert_helper.py`
  - `compat/pdf_table_extractor.py`
  - `compat/processor_lib.py`
  - `compat/reconciliation.py`
  - `compat/status_cache.py`
- **`utils/`** — Utilidades transversales (normalización de fechas, símbolos y helpers).
  - `utils/async_helper.py`
  - `utils/exceptions.py`
  - `utils/status_cache.py`
- **`workers/`** — Workers de sincronización automática en segundo plano.
  - `workers/auto_sync_worker.py`
