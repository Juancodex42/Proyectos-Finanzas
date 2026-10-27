"""Backward compatibility facade for parsers.pdf_table_extractor."""
from parsers.pdf_table_extractor import (
    extract_transactions_from_pdf_stream,
    extract_cpa_summary_table,
    resolve_amounts,
    clean_num,
    parse_date_str,
)

__all__ = [
    "extract_transactions_from_pdf_stream",
    "extract_cpa_summary_table",
    "resolve_amounts",
    "clean_num",
    "parse_date_str",
]
