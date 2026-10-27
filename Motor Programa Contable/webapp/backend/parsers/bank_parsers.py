"""
Parsers for Argentine Bank and Fintech statements (Mercado Pago, Lemon Cash, Traditional Banks).
Normalizes dates to Argentine standard, extracts counterparties, CUITs, amounts, and transaction IDs.
"""
import io
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple
import pandas as pd

from models.operational_models import BankTransaction
try:
    from .base_parser import clean_decimal
except ImportError:
    from parsers.base_parser import clean_decimal

def clean_ars_amount(val) -> float:
    if val is None or pd.isna(val):
        return 0.0
    return clean_decimal(val)

def parse_mercado_pago_statement(file_obj, filename: str) -> List[BankTransaction]:
    """Parses Mercado Pago official CSV or Excel account statement."""
    file_obj.seek(0)
    fn = filename.lower()
    if fn.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_obj)
    else:
        try:
            df = pd.read_csv(file_obj, encoding='utf-8')
        except Exception:
            file_obj.seek(0)
            df = pd.read_csv(file_obj, encoding='latin1', sep=None, engine='python')

    # Standardize column names (lowercase and strip)
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    date_col = next((c for c in df.columns if any(k in c for k in ['fecha', 'date', 'creation_date'])), None)
    id_col = next((c for c in df.columns if any(k in c for k in ['id', 'operacion', 'operation', 'referencia'])), None)
    desc_col = next((c for c in df.columns if any(k in c for k in ['descripcion', 'descripción', 'detalle', 'concepto', 'tipo'])), None)
    amount_col = next((c for c in df.columns if any(k in c for k in ['importe', 'monto', 'amount', 'total', 'neto'])), None)
    
    if not date_col or not amount_col:
        return []

    transactions: List[BankTransaction] = []
    for _, row in df.iterrows():
        raw_amt = clean_ars_amount(row.get(amount_col))
        if abs(raw_amt) < 1e-6:
            continue
            
        desc = str(row.get(desc_col, '') or '').strip()
        raw_date = str(row.get(date_col, '')).strip()
        op_id = str(row.get(id_col, '') or '').strip()
        
        # Determine flow type
        tipo_mov = 'CREDITO' if raw_amt > 0 else 'DEBITO'
        monto_abs = abs(raw_amt)
        
        # Extract counterparty name from description if present
        titular = ''
        cuit = ''
        cuit_match = re.search(r'\b(20|23|24|27|30|33)\d{8}\d\b', desc)
        if cuit_match:
            cuit = cuit_match.group(0)
            
        name_match = re.search(r'(?:de|a|recibida|enviada)\s+([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{3,35})', desc, re.IGNORECASE)
        if name_match:
            titular = name_match.group(1).strip()

        transactions.append(BankTransaction(
            fecha=raw_date,
            banco='MERCADO PAGO',
            tipo_movimiento=tipo_mov,
            monto_ars=monto_abs,
            descripcion=desc,
            titular_contraparte=titular,
            cuit_contraparte=cuit,
            categoria='PENDIENTE',
            raw_reference=op_id
        ))
    return transactions

def parse_lemon_cash_statement(file_obj, filename: str) -> List[BankTransaction]:
    """Parses Lemon Cash CSV or Excel activity report."""
    file_obj.seek(0)
    fn = filename.lower()
    if fn.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_obj)
    else:
        try:
            df = pd.read_csv(file_obj, encoding='utf-8')
        except Exception:
            file_obj.seek(0)
            df = pd.read_csv(file_obj, encoding='latin1', sep=None, engine='python')

    df.columns = [str(c).strip().lower() for c in df.columns]
    
    date_col = next((c for c in df.columns if any(k in c for k in ['fecha', 'date', 'created_at'])), None)
    type_col = next((c for c in df.columns if any(k in c for k in ['tipo', 'operation', 'type'])), None)
    amount_col = next((c for c in df.columns if any(k in c for k in ['importe', 'monto', 'amount', 'monto ars'])), None)
    id_col = next((c for c in df.columns if any(k in c for k in ['id', 'transaccion', 'coelsa', 'uuid'])), None)
    title_col = next((c for c in df.columns if any(k in c for k in ['razon social', 'razón social', 'titular', 'destino', 'origen', 'descripcion', 'detalle'])), None)
    
    if not date_col or not amount_col:
        return []

    transactions: List[BankTransaction] = []
    for _, row in df.iterrows():
        raw_amt = clean_ars_amount(row.get(amount_col))
        if abs(raw_amt) < 1e-6:
            continue
            
        op_type = str(row.get(type_col, '') or '').strip().upper()
        raw_date = str(row.get(date_col, '')).strip()
        op_id = str(row.get(id_col, '') or '').strip()
        titular = str(row.get(title_col, '') or '').strip()
        
        if 'RECIBID' in op_type or 'ENTRADA' in op_type or 'INGRESO' in op_type or 'CREDITO' in op_type or 'CRÉDITO' in op_type or 'CREDIT' in op_type or 'DEP' in op_type:
            tipo_mov = 'CREDITO'
        elif 'ENVIAD' in op_type or 'SALIDA' in op_type or 'RETIRO' in op_type or 'DEBITO' in op_type or 'DÉBITO' in op_type or 'DEBIT' in op_type or 'PAGO' in op_type or 'EGRESO' in op_type:
            tipo_mov = 'DEBITO'
        else:
            tipo_mov = 'CREDITO' if raw_amt > 0 else 'DEBITO'

        transactions.append(BankTransaction(
            fecha=raw_date,
            banco='LEMON CASH',
            tipo_movimiento=tipo_mov,
            monto_ars=abs(raw_amt),
            descripcion=f"{op_type} - {titular}".strip(' -'),
            titular_contraparte=titular,
            categoria='PENDIENTE',
            raw_reference=op_id
        ))
    return transactions

parse_lemon_pdf_or_csv = parse_lemon_cash_statement

def parse_bank_statement(file_obj, filename: str) -> Tuple[str, List[BankTransaction]]:
    """Auto-detects bank/fintech format and parses all movements."""
    fn = filename.lower()
    if 'lemon' in fn:
        txs = parse_lemon_cash_statement(file_obj, filename)
        return 'LEMON CASH', txs
    if 'mercado' in fn or 'mp' in fn:
        txs = parse_mercado_pago_statement(file_obj, filename)
        return 'MERCADO PAGO', txs
        
    # Content-based heuristic
    file_obj.seek(0)
    preview = file_obj.read(1024)
    file_obj.seek(0)
    try:
        preview_text = preview.decode('utf-8', errors='ignore').lower()
    except Exception:
        preview_text = ''
        
    if 'lemon' in preview_text or 'coelsa' in preview_text:
        return 'LEMON CASH', parse_lemon_cash_statement(file_obj, filename)
    if 'mercado pago' in preview_text or 'mercadopago' in preview_text:
        return 'MERCADO PAGO', parse_mercado_pago_statement(file_obj, filename)
        
    # Fallback to Mercado Pago style (most general standard with date/amount)
    txs = parse_mercado_pago_statement(file_obj, filename)
    return 'BANCO / FINTECH', txs
