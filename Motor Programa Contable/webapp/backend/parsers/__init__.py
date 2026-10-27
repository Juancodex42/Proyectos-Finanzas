"""
Specialized Parsers Package for Accounting Program.
Provides modular exchange parsers and normalization utilities.
"""

from .base_parser import (
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
    extract_preview_columns
)

from .binance_parser import (
    find_binance_column,
    get_binance_dataframes,
    process_binance_csv,
    process_binance_zip
)

from .fiwind_parser import process_fiwind
from .bitso_parser import process_bitso
from .ripio_parser import (
    process_api_trades,
    process_ripio_trade,
    procesar_ripio_comun_txt
)
from .bitget_parser import process_bitget
from .other_exchanges_parser import (
    process_dynamic_csv,
    process_other_exchange
)
from .excel_multi_processor import (
    generate_master_excel,
    generate_excel_bytes,
    process_multi_exchange_excel
)
from .archive_processor import process_archive
from .exchange_detector import detect_exchange
from .okx_parser import process_okx_file, process_okx_p2p
from .pdf_cert_helper import extract_info_from_pdf_stream
from .pdf_table_extractor import extract_transactions_from_pdf_stream
from .parallel_extractor import ParallelPageExtractor
from .deskew_helper import AngleMemory, deskew_image, detect_page_orientation_fast
from .ocr_helper import ocr_pdf_page, ocr_pdf_pages
from .bank_parsers import parse_bank_statement
from .bank_statement_parser import parse_bank_statement_file
from .dispatcher import (
    process_uploaded_file,
    process_file,
    parse_pdf_Visual_or_text,
    extract_tables_from_pdf,
)

__all__ = [
    'process_uploaded_file',
    'process_file',
    'parse_pdf_Visual_or_text',
    'extract_tables_from_pdf',
    '_normalize_text',
    '_NEGATIVE_STATUS_KEYWORDS',
    '_NEGATIVE_STATUS_REGEX',
    'get_usd_ars_rate',
    'KEY_CANDIDATES',
    'find_column_fuzzy',
    'validate_columns',
    '_normalize_tz_to_utc',
    'parse_date',
    'clean_decimal',
    'limpiar_numero_binance',
    'is_cancelled_transaction',
    'normalize_exchange_name',
    'create_transaction',
    'extract_preview_columns',
    'find_binance_column',
    'get_binance_dataframes',
    'process_binance_csv',
    'process_binance_zip',
    'process_fiwind',
    'process_bitso',
    'process_api_trades',
    'process_ripio_trade',
    'procesar_ripio_comun_txt',
    'process_bitget',
    'process_dynamic_csv',
    'process_other_exchange',
    'generate_master_excel',
    'generate_excel_bytes',
    'process_multi_exchange_excel',
    'process_archive',
    'detect_exchange',
    'process_okx_file',
    'process_okx_p2p',
    'extract_info_from_pdf_stream',
    'extract_transactions_from_pdf_stream',
    'ParallelPageExtractor',
    'deskew_image',
    'detect_page_orientation_fast',
    'AngleMemory',
    'ocr_pdf_page',
    'ocr_pdf_pages',
    'parse_bank_statement',
    'parse_bank_statement_file',
]

