"""
Bank statement parser compatibility module for Argentine Banks and Fintechs.
Delegates to bank_parsers.py for Mercado Pago, Lemon Cash, and traditional banks.
"""
from typing import List, Tuple
from parsers.bank_parsers import (
    parse_bank_statement,
    parse_mercado_pago_statement,
    parse_lemon_cash_statement,
    clean_ars_amount
)
from models.operational_models import BankTransaction

def parse_bank_statement_file(file_obj, filename: str) -> Tuple[str, List[BankTransaction]]:
    """
    Parses a bank statement file (CSV or Excel) and returns (bank_name, transactions).
    """
    return parse_bank_statement(file_obj, filename)

__all__ = [
    'parse_bank_statement_file',
    'parse_bank_statement',
    'parse_mercado_pago_statement',
    'parse_lemon_cash_statement',
    'clean_ars_amount',
    'BankTransaction'
]
