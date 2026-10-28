"""
Helper functions for Ripio parsers and API trade normalization.
"""
import pandas as pd
from utils.exceptions import MissingColumnsError
try:
    from .base_parser import parse_date, create_transaction, get_usd_ars_rate
except ImportError:
    from parsers.base_parser import parse_date, create_transaction, get_usd_ars_rate


def _calc_monto_ars(moneda, monto, fecha, base_coin=None, base_amount=None):
    usd_rate = get_usd_ars_rate(fecha)
    if moneda == 'ARS':
        return abs(monto)
    if moneda in ('USDT', 'USDC', 'USD'):
        return abs(monto) * usd_rate
    from models.transaction_models import get_quote_usd_value
    return get_quote_usd_value(moneda, abs(monto), base_coin=base_coin, base_amount=base_amount, fecha=fecha) * usd_rate


def process_api_trades(exchange_name, trades):
    """Normalizes a list of ccxt trades or Ripio generic trades into standard internal format."""
    from models.transaction_models import get_quote_usd_value
    processed = []
    for t in trades:
        try:
            side = str(t.get('side', t.get('type', ''))).lower()
            if not side:
                continue
            if 'symbol' in t:
                symbol = str(t.get('symbol', ''))
                parts = symbol.split('/') if '/' in symbol else [symbol, 'ARS']
                dt_str = str(t.get('datetime', '')).rstrip('Z')
            elif 'pair' in t:
                pair_str = str(t['pair'])
                parts = pair_str.split('_') if '_' in pair_str else [pair_str, 'ARS']
                dt_str = t.get('date', t.get('created_at', ''))
            else:
                continue

            fecha = parse_date(dt_str, 'ripio_trade') or pd.to_datetime(dt_str, errors='coerce')
            if fecha is None or pd.isna(fecha):
                continue

            crypto = parts[0].upper()
            quote = parts[1].upper() if len(parts) > 1 else 'ARS'
            amount_crypto = float(t.get('amount', t.get('executed_amount', 0)))
            price = float(t.get('price', 0))
            cost = float(t.get('total_value', t.get('cost', t.get('total', amount_crypto * price))))
            tid = str(t.get('id', ''))

            usd_rate = get_usd_ars_rate(fecha)
            if quote == 'ARS':
                m_ars = cost
                cot = price
            else:
                usd_val = get_quote_usd_value(quote, cost, base_coin=crypto, base_amount=amount_crypto, fecha=fecha)
                m_ars = usd_val * usd_rate
                cot = m_ars / amount_crypto if amount_crypto > 0 else 0.0

            is_ripio = 'ripio' in str(exchange_name).lower()
            is_buy = 'buy' in side or 'compra' in side
            is_sell = 'sell' in side or 'venta' in side
            if is_buy:
                processed.append(create_transaction(
                    fecha, exchange_name, 'Compra', crypto,
                    amount_crypto, 0, cot, 0, m_ars, f"ID: {tid}", unique_id=tid
                ))
                if is_ripio and quote != 'ARS' and quote != crypto and cost > 0:
                    cot_q = m_ars / cost if cost > 0 else 0.0
                    processed.append(create_transaction(
                        fecha, exchange_name, 'Venta', quote,
                        0, cost, 0, cot_q, m_ars, f"ID: {tid} | [INTERCAMBIO: {quote}->{crypto}]", unique_id=f"{tid}_quote"
                    ))
            elif is_sell:
                processed.append(create_transaction(
                    fecha, exchange_name, 'Venta', crypto,
                    0, amount_crypto, 0, cot, m_ars, f"ID: {tid}", unique_id=tid
                ))
                if is_ripio and quote != 'ARS' and quote != crypto and cost > 0:
                    cot_q = m_ars / cost if cost > 0 else 0.0
                    processed.append(create_transaction(
                        fecha, exchange_name, 'Compra', quote,
                        cost, 0, cot_q, 0, m_ars, f"ID: {tid} | [INTERCAMBIO: {crypto}->{quote}]", unique_id=f"{tid}_quote"
                    ))
            else:
                processed.append(create_transaction(
                    fecha, exchange_name, 'Operacion Ripio', crypto,
                    amount_crypto, 0, cot, 0, m_ars, f"ID: {tid} Side: {side}", unique_id=tid
                ))
        except Exception as e:
            print(f"Error normalizing API trade: {e}")
            continue

    return processed
