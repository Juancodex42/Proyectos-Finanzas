"""
db_manager.py - Modular Database & Domain Services Facade.
Provides backwards-compatible entry points into db and domain services.
"""

# Connection & Schema Management
from db.connection import (
    DB_PATH,
    get_connection,
    init_db,
)

# Transactions Service
from services.transactions_service import (
    deduplicate_existing_database,
    insert_transactions,
    get_all_transactions_df,
    get_all_transactions,
    get_transactions_by_filenames,
    clear_db,
    delete_transactions_by_exchange,
    get_transactions,
    get_latest_transaction_info,
)

# Certifications Service
from services.certifications_service import (
    AUTHENTIC_CERTIFICATIONS,
    _normalize_cert_boundary,
    _parse_cert_datetime,
    sync_certified_transactions_status,
    cleanup_and_deduplicate_certifications,
    fix_corrupted_certifications,
    get_certifications,
    get_last_certification_end_datetime,
    add_certification,
    get_certification_by_id,
    delete_certification,
    get_last_cpa_name,
    count_provisional_transactions_in_range,
    apply_certified_period_replacement,
)

# Gap Analysis Service
from services.gap_service import (
    check_history_gaps,
    enrich_gaps_with_clues,
    group_gaps_into_root_intervals,
    _generate_recommended_action,
)

# Tax & Inflation Service
from services.tax_service import (
    get_tax_settings,
    save_tax_settings,
    update_tax_settings,
    get_tax_report,
    get_ars_inflation_indexes,
    get_crypto_prices,
)

# Exchanges Configuration Service
from services.exchanges_service import (
    get_all_exchanges,
    add_custom_exchange,
    update_exchange_mapping,
    update_exchange_apikeys,
    delete_exchange,
    get_exchange_last_tx_date,
    get_latest_transaction_timestamp,
)

# Analytical & Dashboard Queries Service
from services.analytics_service import (
    _build_filter_sql,
    _clean_df_for_json,
    get_kpis,
    get_daily_volume,
    get_exchange_distribution,
    get_equity_curve,
    get_modal_spread,
    get_processing_history,
    get_uploaded_files_history,
    delete_transactions_by_filename,
)
from services.fifo_service import recalculate_fifo_costs_db

__all__ = [
    "DB_PATH",
    "get_connection",
    "init_db",
    "deduplicate_existing_database",
    "insert_transactions",
    "get_all_transactions_df",
    "get_all_transactions",
    "get_transactions_by_filenames",
    "clear_db",
    "delete_transactions_by_exchange",
    "get_transactions",
    "get_latest_transaction_info",
    "AUTHENTIC_CERTIFICATIONS",
    "_normalize_cert_boundary",
    "_parse_cert_datetime",
    "sync_certified_transactions_status",
    "cleanup_and_deduplicate_certifications",
    "fix_corrupted_certifications",
    "get_certifications",
    "get_last_certification_end_datetime",
    "add_certification",
    "get_certification_by_id",
    "delete_certification",
    "get_last_cpa_name",
    "count_provisional_transactions_in_range",
    "apply_certified_period_replacement",
    "check_history_gaps",
    "enrich_gaps_with_clues",
    "group_gaps_into_root_intervals",
    "_generate_recommended_action",
    "get_tax_settings",
    "save_tax_settings",
    "update_tax_settings",
    "get_tax_report",
    "get_ars_inflation_indexes",
    "get_crypto_prices",
    "get_all_exchanges",
    "add_custom_exchange",
    "update_exchange_mapping",
    "update_exchange_apikeys",
    "delete_exchange",
    "get_exchange_last_tx_date",
    "get_latest_transaction_timestamp",
    "_build_filter_sql",
    "_clean_df_for_json",
    "get_kpis",
    "get_daily_volume",
    "get_exchange_distribution",
    "get_equity_curve",
    "get_modal_spread",
    "get_processing_history",
    "get_uploaded_files_history",
    "delete_transactions_by_filename",
    "recalculate_fifo_costs_db",
]

