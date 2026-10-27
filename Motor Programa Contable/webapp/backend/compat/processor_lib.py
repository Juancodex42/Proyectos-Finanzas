"""
processor_lib.py - Thin Backward-Compatibility Facade for parsers package.
"""

import os
import sys

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from parsers import (
    process_uploaded_file,
    process_file,
    parse_pdf_Visual_or_text,
    extract_tables_from_pdf,
    _normalize_text,
    _NEGATIVE_STATUS_KEYWORDS,
    _NEGATIVE_STATUS_REGEX,
    get_usd_ars_rate,
    KEY_CANDIDATES,
    find_column_fuzzy,
    validate_columns,
    _normalize_tz_to_utc,
    parse_date,
    clean_decimal,
    limpiar_numero_binance,
    is_cancelled_transaction,
    normalize_exchange_name,
    create_transaction,
    find_binance_column,
    get_binance_dataframes,
    process_binance_csv,
    process_binance_zip,
    process_fiwind,
    process_bitso,
    process_api_trades,
    process_ripio_trade,
    procesar_ripio_comun_txt,
    process_bitget,
    process_dynamic_csv,
    process_other_exchange,
    generate_master_excel,
    generate_excel_bytes,
    process_multi_exchange_excel,
    process_archive,
    extract_preview_columns,
    detect_exchange,
    process_okx_file,
    process_okx_p2p,
    extract_info_from_pdf_stream,
    extract_transactions_from_pdf_stream,
    ParallelPageExtractor,
    deskew_image,
    detect_page_orientation_fast,
    AngleMemory,
    ocr_pdf_page,
    ocr_pdf_pages,
    parse_bank_statement,
    parse_bank_statement_file,
    __all__,
)