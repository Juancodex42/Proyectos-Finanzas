import os
import re
import logging
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from dotenv import load_dotenv
from models.transaction_models import TransactionModel

ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=ENV_FILE, override=True)


def get_exchange_pairs(exchange_id, default_pairs):
    try:
        from db.connection import get_connection
        import json
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT mapping_json FROM exchanges_config WHERE id=? OR LOWER(name)=?", (exchange_id, str(exchange_id).lower()))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            mapping = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            pairs = mapping.get('pairs')
            if pairs and isinstance(pairs, list):
                return pairs
    except Exception as e:
        print(f"Error fetching dynamic pairs for {exchange_id}: {e}")
    return default_pairs


@lru_cache(maxsize=32)
def _cached_exchange_rate(year):
    try:
        from services.tax_service import get_tax_settings
        settings = get_tax_settings(year)
        if settings and isinstance(settings, dict):
            return float(settings.get('usd_ars_exchange_rate', 1000.0))
    except Exception:
        pass
    return 1000.0


def get_exchange_rate_for_date(year):
    try:
        return _cached_exchange_rate(year)
    except Exception as e:
        logging.getLogger(__name__).warning(
            f"Falló la consulta de tax_settings para el año {year}: {e}. Usando fallback 1000.0 sin cachear."
        )
        return 1000.0


def clear_exchange_rate_cache():
    _cached_exchange_rate.cache_clear()


get_exchange_rate_for_date.cache_clear = _cached_exchange_rate.cache_clear


def get_exchange_rate_from_obj(date_obj):
    year = date_obj.year if hasattr(date_obj, 'year') else 2026
    return get_exchange_rate_for_date(year)


def convert_cost_to_ars(cost, pair, date_obj, amount=0.0):
    pair_upper = str(pair).upper()
    if pair_upper.endswith('/ARS') or pair_upper.endswith('_ARS') or pair_upper.endswith('ARS'):
        return cost
    parts = pair_upper.replace('_', '/').split('/')
    base_coin = parts[0] if len(parts) >= 1 else ""
    quote_coin = parts[1] if len(parts) >= 2 else ""
    rate = get_exchange_rate_from_obj(date_obj)
    from models.transaction_models import get_quote_usd_value
    usd_val = get_quote_usd_value(quote_coin, cost, base_coin=base_coin, base_amount=amount, fecha=date_obj)
    return usd_val * rate


def decompose_api_trade(t, pair, exchange_name):
    """
    Decomposes a CCXT trade into one or two TransactionModel objects, plus fee models.
    If the trade is a swap between stablecoins/USD (e.g. USDT/USDC), 
    it splits it into a Compra and Venta in ARS with [INTERCAMBIO: ...] comment.
    Also extracts and registers fee(s) as Comisión Cripto / Comisión Fiat.
    """
    is_buy = t['side'] == 'buy'
    monto = round(float(t['amount']), 16)
    precio = float(t['price'])
    cost = round(float(t.get('cost', monto * precio)), 16)
    is_arg_ex = any(k in str(exchange_name or '').lower() for k in ('bitso', 'ripio', 'fiwind', 'lemon', 'belo', 'buenbit', 'satoshitango'))
    utc_dt = datetime.fromtimestamp(t['timestamp'] / 1000.0, tz=timezone.utc)
    tx_date = (utc_dt - timedelta(hours=3) if is_arg_ex else utc_dt).replace(tzinfo=None)
    trade_id = str(t.get('id') or '').strip()
    order_id = str(t.get('order') or '').strip()
    primary_id = order_id or trade_id
    ccxt_extra = f" | CCXT: {trade_id}" if (order_id and trade_id and order_id != trade_id) else ""
    api_ref = f"ID: {primary_id}{ccxt_extra}" if primary_id else ""
    
    parts = pair.upper().split('/')
    trade_models = []
    if len(parts) == 2:
        base_coin, quote_coin = parts[0], parts[1]
        
        # When quote asset is a crypto or stablecoin (not fiat ARS), record both legs
        if quote_coin != 'ARS':
            ars_total = convert_cost_to_ars(cost, pair, tx_date, amount=monto)
            comment = f"[INTERCAMBIO: {quote_coin}->{base_coin}]" if is_buy else f"[INTERCAMBIO: {base_coin}->{quote_coin}]"
            ref_c = f"ID: {primary_id}_c{ccxt_extra}" if primary_id else ""
            ref_v = f"ID: {primary_id}_v{ccxt_extra}" if primary_id else ""
            
            if is_buy:
                cot_c = ars_total / monto if monto > 0 else 0.0
                trade_models.append(TransactionModel(
                    fecha=tx_date, exchange=exchange_name,
                    tipo_operacion="Compra", moneda=base_coin,
                    monto_compra_cripto=monto, monto_venta_cripto=0.0,
                    cotizacion_compra=cot_c, cotizacion_venta=0.0,
                    monto_ars=ars_total, comentarios=f"{comment} | {ref_c}" if ref_c else comment
                ))
                cot_v = ars_total / cost if cost > 0 else 0.0
                trade_models.append(TransactionModel(
                    fecha=tx_date, exchange=exchange_name,
                    tipo_operacion="Venta", moneda=quote_coin,
                    monto_compra_cripto=0.0, monto_venta_cripto=cost,
                    cotizacion_compra=0.0, cotizacion_venta=cot_v,
                    monto_ars=ars_total, comentarios=f"{comment} | {ref_v}" if ref_v else comment
                ))
            else:
                cot_v = ars_total / monto if monto > 0 else 0.0
                trade_models.append(TransactionModel(
                    fecha=tx_date, exchange=exchange_name,
                    tipo_operacion="Venta", moneda=base_coin,
                    monto_compra_cripto=0.0, monto_venta_cripto=monto,
                    cotizacion_compra=0.0, cotizacion_venta=cot_v,
                    monto_ars=ars_total, comentarios=f"{comment} | {ref_v}" if ref_v else comment
                ))
                cot_c = ars_total / cost if cost > 0 else 0.0
                trade_models.append(TransactionModel(
                    fecha=tx_date, exchange=exchange_name,
                    tipo_operacion="Compra", moneda=quote_coin,
                    monto_compra_cripto=cost, monto_venta_cripto=0.0,
                    cotizacion_compra=cot_c, cotizacion_venta=0.0,
                    monto_ars=ars_total, comentarios=f"{comment} | {ref_c}" if ref_c else comment
                ))

    # Single standard transaction (e.g. against fiat ARS)
    if not trade_models:
        crypto = parts[0] if len(parts) > 0 else pair
        ars_total = convert_cost_to_ars(cost, pair, tx_date, amount=monto)
        monto_c = monto if is_buy else 0.0
        monto_v = monto if not is_buy else 0.0
        cot_c = precio if is_buy else 0.0
        cot_v = precio if not is_buy else 0.0
        trade_models.append(TransactionModel(
            fecha=tx_date,
            exchange=exchange_name,
            tipo_operacion="Compra" if is_buy else "Venta",
            moneda=crypto,
            monto_compra_cripto=monto_c,
            monto_venta_cripto=monto_v,
            cotizacion_compra=cot_c,
            cotizacion_venta=cot_v,
            monto_ars=ars_total,
            comentarios=api_ref
        ))

    # Bug 12: Extract and register fees from CCXT t['fee'] or t['fees']
    from models.transaction_models import canonicalize_ticker, get_quote_usd_value
    rate_ars = get_exchange_rate_from_obj(tx_date)
    raw_fees = []
    if t.get('fee') and isinstance(t['fee'], dict):
        raw_fees.append(t['fee'])
    if t.get('fees') and isinstance(t['fees'], list):
        for f in t['fees']:
            if isinstance(f, dict):
                raw_fees.append(f)

    seen_fees = set()
    fee_models = []
    for f in raw_fees:
        fee_cost = round(float(f.get('cost') or 0.0), 16)
        fee_curr = str(f.get('currency') or '').strip().upper()
        if fee_cost <= 0 or not fee_curr:
            continue
        clean_fee_coin = canonicalize_ticker(fee_curr)
        fee_key = (clean_fee_coin, fee_cost)
        if fee_key in seen_fees:
            continue
        seen_fees.add(fee_key)

        fee_ref = f"Comisión {clean_fee_coin} | ID: {primary_id}_fee{ccxt_extra}" if primary_id else f"Comisión {clean_fee_coin}"
        
        if clean_fee_coin == 'ARS':
            fee_models.append(TransactionModel(
                fecha=tx_date, exchange=exchange_name,
                tipo_operacion="Comisión Fiat", moneda="ARS",
                monto_compra_cripto=0.0, monto_venta_cripto=0.0,
                cotizacion_compra=0.0, cotizacion_venta=0.0,
                monto_ars=round(fee_cost, 2), comentarios=fee_ref
            ))
        else:
            fee_usd = 0.0
            if clean_fee_coin in ('USD', 'USDT', 'USDC', 'DAI', 'BUSD', 'UXD'):
                fee_usd = fee_cost
            elif len(parts) == 2 and clean_fee_coin == parts[0] and precio > 0:
                quote_part = parts[1]
                if quote_part in ('USD', 'USDT', 'USDC', 'DAI', 'BUSD', 'UXD'):
                    fee_usd = fee_cost * precio
                else:
                    fee_usd = get_quote_usd_value(clean_fee_coin, fee_cost, fecha=tx_date)
            else:
                fee_usd = get_quote_usd_value(clean_fee_coin, fee_cost, fecha=tx_date)
            fee_ars = round(fee_usd * rate_ars, 2)
            fee_cot = round(fee_ars / fee_cost, 2) if fee_cost > 0 else 0.0
            fee_models.append(TransactionModel(
                fecha=tx_date, exchange=exchange_name,
                tipo_operacion="Comisión Cripto", moneda=clean_fee_coin,
                monto_compra_cripto=0.0, monto_venta_cripto=fee_cost,
                cotizacion_compra=0.0, cotizacion_venta=fee_cot,
                monto_ars=fee_ars, comentarios=fee_ref
            ))

    return trade_models + fee_models


def _is_placeholder_key(key, secret):
    if not key or not secret:
        return True
    k, s = str(key).lower().strip(), str(secret).lower().strip()
    placeholders = ['your_api_key_here', 'xxx', 'test', 'your_secret_here', 'your_key', '']
    return k in placeholders or s in placeholders or 'your_' in k or 'your_' in s


def _clean_api_error(err_str):
    """Clean ccxt/API error strings for user-friendly display, prioritizing error numbers."""
    s = str(err_str)
    
    if 'timeout' in s.lower() or 'timed out' in s.lower():
        return "Error (Timeout)"
        
    code_match = re.search(r'"(?:code|retCode|status)"\s*:\s*(-?\d+)', s)
    if code_match:
        return f"Error {code_match.group(1)}"
        
    http_match = re.search(r'(?:http|status)\s*(\d{3})', s, re.IGNORECASE)
    if http_match:
        return f"Error {http_match.group(1)}"
        
    num_match = re.search(r'\b(-?\d{3,6})\b', s)
    if num_match:
        return f"Error {num_match.group(1)}"
        
    cleaned = re.sub(r'^[a-zA-Z]+ (GET|POST|PUT|DELETE|PATCH) https?://\S+\s*', '', s).strip()
    cleaned = re.sub(r'https?://\S+', '', cleaned).strip()
    cleaned = cleaned.strip('() ')
    if not cleaned:
        return "Error de conexión"
    return cleaned[:50]
