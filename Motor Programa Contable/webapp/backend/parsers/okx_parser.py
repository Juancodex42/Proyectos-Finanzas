"""
Specialized OKX Parser (P2P and Spot Statements).
Accurately handles OKX column conventions:
- Volume = Crypto Quantity
- Amount = Fiat Value (ARS/USD)
- Status = 'Fulfilled' vs 'Canceled'
"""

import io
import re
import logging
import pandas as pd
from typing import List, Tuple, Dict, Any

try:
    from .base_parser import (
        _normalize_text, parse_date, clean_decimal,
        is_cancelled_transaction, create_transaction,
        get_usd_ars_rate, get_fiat_usd_rate
    )
except ImportError:
    from parsers.base_parser import (
        _normalize_text, parse_date, clean_decimal,
        is_cancelled_transaction, create_transaction,
        get_usd_ars_rate, get_fiat_usd_rate
    )

logger = logging.getLogger(__name__)


def process_okx_p2p(df: pd.DataFrame, filename: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parses OKX P2P order export DataFrame."""
    processed = []
    raw_sample = []

    if df is None or df.empty:
        return [], []

    df.columns = [str(c).lower().strip() for c in df.columns]
    raw_sample = df.head(10).fillna('').astype(str).to_dict(orient='records')

    # Status column check (only accept completed/fulfilled)
    status_col = next((c for c in df.columns if c in ['status', 'estado']), None)
    order_no_col = next((c for c in df.columns if c in ['order no', 'order no.', 'order number', 'numero de orden']), None)
    type_col = next((c for c in df.columns if c in ['order type', 'tipo de orden', 'side', 'type']), None)
    crypto_col = next((c for c in df.columns if c in ['crypto', 'activo', 'coin', 'asset']), None)
    currency_col = next((c for c in df.columns if c in ['currency', 'fiat', 'moneda']), None)
    price_col = next((c for c in df.columns if c in ['price', 'precio', 'cotizacion']), None)
    volume_col = next((c for c in df.columns if c in ['volume', 'volumen', 'crypto amount', 'cantidad']), None)
    amount_col = next((c for c in df.columns if c in ['amount', 'monto', 'total', 'fiat amount']), None)
    date_col = next((c for c in df.columns if c in ['created date', 'created time', 'date', 'fecha']), None)
    method_col = next((c for c in df.columns if c in ['payment method', 'metodo de pago']), None)

    for idx, row in df.iterrows():
        if is_cancelled_transaction(row):
            continue
        # Filter cancelled/failed orders
        if status_col:
            st = str(row.get(status_col, '')).lower().strip()
            if any(term in st for term in ['cancel', 'fail', 'rechaz', 'anulad', 'anul']):
                continue

        order_no = str(row.get(order_no_col, '')).strip() if order_no_col else ''
        actual_uid = order_no if order_no and order_no.lower() not in ('nan', 'none', '') else None

        tipo_raw = str(row.get(type_col, '')).lower().strip() if type_col else 'buy'
        is_buy = tipo_raw in ('buy', 'compra', 'comprar') or 'buy' in tipo_raw or 'compra' in tipo_raw

        crypto = str(row.get(crypto_col, 'USDT')).upper().strip() if crypto_col else 'USDT'
        fiat = str(row.get(currency_col, 'ARS')).upper().strip() if currency_col else 'ARS'

        price = clean_decimal(row.get(price_col, 0)) if price_col else 0.0
        # In OKX: Volume is crypto amount; Amount is fiat ARS total
        vol = clean_decimal(row.get(volume_col, 0)) if volume_col else 0.0
        tot_fiat = clean_decimal(row.get(amount_col, vol * price)) if amount_col else (vol * price)

        raw_date = row.get(date_col, '') if date_col else ''
        fecha = parse_date(raw_date, 'okx')

        is_ars = any(k in fiat for k in ['ARS', 'PESO', 'ARGENTIN', '$']) or not fiat
        usd_ars_rate = get_usd_ars_rate(fecha)

        if is_ars:
            total_ars = tot_fiat
            price_ars = price
        else:
            fiat_usd = get_fiat_usd_rate(fiat)
            total_ars = tot_fiat * fiat_usd * usd_ars_rate
            price_ars = price * fiat_usd * usd_ars_rate

        pay_method = str(row.get(method_col, '')).strip() if method_col else ''
        comment_parts = [f"Order ID: {order_no}"] if order_no else []
        comment_parts.append(f"OKX P2P ({pay_method})" if pay_method else "OKX P2P")
        if not is_ars:
            comment_parts.append(f"[{fiat}]")
        comment = " | ".join(comment_parts)

        if is_buy:
            processed.append(create_transaction(
                fecha, 'OKX', 'Compra', crypto,
                vol, 0, price_ars, 0, total_ars, comment, unique_id=actual_uid
            ))
        else:
            processed.append(create_transaction(
                fecha, 'OKX', 'Venta', crypto,
                0, vol, 0, price_ars, total_ars, comment, unique_id=actual_uid
            ))

    return processed, raw_sample


def process_okx_file(file_obj, filename: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Dispatches OKX file to P2P or Spot processing based on content."""
    file_obj.seek(0)
    fn = str(filename).lower()
    df = None
    if fn.endswith(('.xlsx', '.xls')):
        try:
            df = pd.read_excel(file_obj)
        except Exception:
            df = None
    if df is None:
        for enc in ['utf-8-sig', 'utf-8', 'latin1', 'cp1252']:
            for sep in [None, ',', ';', '\t']:
                try:
                    file_obj.seek(0)
                    kwargs = {'encoding': enc}
                    if sep is None:
                        kwargs['sep'] = None
                        kwargs['engine'] = 'python'
                    else:
                        kwargs['sep'] = sep
                    df_try = pd.read_csv(file_obj, **kwargs)
                    if df_try is not None and not df_try.empty and len(df_try.columns) > 1:
                        df = df_try
                        break
                except Exception:
                    pass
            if df is not None:
                break
    if df is None:
        file_obj.seek(0)
        try:
            df = pd.read_excel(file_obj)
        except Exception:
            file_obj.seek(0)
            df = pd.read_csv(file_obj)

    cols = [str(c).lower().strip() for c in df.columns]
    is_p2p = ('volume' in cols and 'amount' in cols) or ('order no' in cols and 'crypto' in cols)

    if is_p2p:
        return process_okx_p2p(df, filename)

    # Spot or generic OKX fallback
    from parsers.other_exchanges_parser import process_other_exchange
    file_obj.seek(0)
    return process_other_exchange(file_obj, filename)
