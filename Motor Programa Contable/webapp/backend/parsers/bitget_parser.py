import re
import pandas as pd
from exceptions import MissingColumnsError

try:
    from .base_parser import (
        _normalize_text, parse_date, clean_decimal,
        find_column_fuzzy, is_cancelled_transaction,
        create_transaction, get_usd_ars_rate, get_fiat_usd_rate
    )
except ImportError:
    from parsers.base_parser import (
        _normalize_text, parse_date, clean_decimal,
        find_column_fuzzy, is_cancelled_transaction,
        create_transaction, get_usd_ars_rate, get_fiat_usd_rate
    )

def get_col(row, candidates):
    norm_map = {_normalize_text(k): k for k in row.keys()}
    for cand in candidates:
        nc = _normalize_text(cand)
        if nc in norm_map:
            val = row.get(norm_map[nc])
            if val is not None and not pd.isna(val):
                return val
    return None


def process_bitget(file_obj, filename):
    """Parses Bitget Spot and P2P trade statements from CSV or Excel."""
    processed = []
    raw_sample = []
    try:
        file_obj.seek(0)
        ext = filename.lower()
        if ext.endswith('.xlsx') or ext.endswith('.xls'):
            df = pd.read_excel(file_obj)
        else:
            df = None
            for enc in ['utf-8-sig', 'utf-8', 'latin1', 'cp1252']:
                for sep in [None, ',', ';', '\t']:
                    file_obj.seek(0)
                    try:
                        kwargs = {'encoding': enc}
                        if sep is not None:
                            kwargs['sep'] = sep
                        df = pd.read_csv(file_obj, **kwargs)
                        if df is not None and not df.empty and len(df.columns) > 1:
                            break
                    except Exception:
                        pass
                if df is not None and not df.empty and len(df.columns) > 1:
                    break
        if df is None or df.empty:
            return [], []

        df.columns = [str(c).lower().strip() for c in df.columns]
        raw_sample = df.head(10).fillna('').astype(str).to_dict(orient='records')

        c_time = find_column_fuzzy(df, ['order time', 'time', 'fecha', 'creation time', 'create time', 'created_at', 'timestamp', 'date'])
        c_side = find_column_fuzzy(df, ['direction', 'side', 'type', 'order type', 'tipo', 'tipo de orden'])
        c_pair = find_column_fuzzy(df, ['symbol', 'trading pair', 'pair', 'par', 'mercado'])
        c_coin = find_column_fuzzy(df, ['coin', 'crypto', 'crypto asset', 'asset', 'moneda', 'activo'])
        c_fiat = find_column_fuzzy(df, ['fiat currency', 'fiat', 'moneda fiat', 'currency'])
        c_price = find_column_fuzzy(df, ['order price', 'price', 'unit price', 'precio', 'precio unitario', 'rate'])
        c_amount = find_column_fuzzy(df, ['executed quantity', 'filled', 'amount', 'quantity', 'cantidad', 'crypto amount', 'monto'])
        c_total = find_column_fuzzy(df, ['total', 'volume', 'turnover', 'total price', 'total amount', 'monto total', 'precio total'])
        c_id = find_column_fuzzy(df, ['order no.', 'order id', 'order_id', 'id', 'numero de orden'])

        is_p2p = (c_fiat is not None) or ('p2p' in filename.lower())

        for index, row in df.iterrows():
            if is_cancelled_transaction(row):
                continue
            try:
                fecha_raw = row.get(c_time) if c_time else None
                fecha = parse_date(fecha_raw, 'Bitget')
                tipo_raw = str(row.get(c_side, '')).upper().strip()
                is_buy = any(k in tipo_raw for k in ['BUY', 'COMPRA', 'IN'])

                price = clean_decimal(row.get(c_price, 0)) if c_price else 0.0
                qty = clean_decimal(row.get(c_amount, 0)) if c_amount else 0.0
                total = clean_decimal(row.get(c_total, qty * price)) if c_total else (qty * price)
                raw_order_id = str(row.get(c_id, '')).strip() if c_id else ''
                order_id = raw_order_id if raw_order_id and raw_order_id.lower() not in ('nan', 'none', 'null', '') else ""
                uid_spot = order_id if order_id else None

                if is_p2p:
                    fiat = str(row.get(c_fiat, 'ARS')).upper().strip() if c_fiat else 'ARS'
                    coin = str(row.get(c_coin, 'USDT')).upper().strip() if c_coin else 'USDT'
                    usd_ars_rate = get_usd_ars_rate(fecha)
                    if 'ARS' in fiat:
                        m_ars = total
                        price_ars = price
                    else:
                        fiat_usd = get_fiat_usd_rate(fiat)
                        m_ars = total * fiat_usd * usd_ars_rate
                        price_ars = price * fiat_usd * usd_ars_rate
                    
                    if is_buy:
                        processed.append(create_transaction(
                            fecha, 'Bitget P2P', 'Compra', coin,
                            qty, 0, price_ars, 0, m_ars, 'P2P', unique_id=uid_spot
                        ))
                    else:
                        processed.append(create_transaction(
                            fecha, 'Bitget P2P', 'Venta', coin,
                            0, qty, 0, price_ars, m_ars, 'P2P', unique_id=uid_spot
                        ))
                else:
                    pair = str(row.get(c_pair, '')).upper().strip()
                    if not pair and c_coin:
                        pair = str(row.get(c_coin, '')).upper().strip()

                    spot_comment = 'Spot'
                    is_ars_pair = False
                    crypto = pair
                    if re.search(r'[/_\-]ARS$', pair):
                        is_ars_pair = True
                        crypto = re.sub(r'[/_\-]ARS$', '', pair)
                    elif re.search(r'^ARS[/_\-]', pair):
                        is_ars_pair = True
                        crypto = re.sub(r'^ARS[/_\-]', '', pair)
                    elif pair.endswith('ARS') and len(pair) >= 5 and not pair.endswith(('BARS', 'STARS', 'WARS', 'MARS', 'PARS')):
                        is_ars_pair = True
                        crypto = pair[:-3]

                    fee = clean_decimal(get_col(row, ['Fee', 'Trading Fee', 'Comisión', 'Comision']) or 0)
                    fee_coin = str(get_col(row, ['Fee Coin', 'Fee Currency', 'Moneda Comisión', 'feeCoin']) or '').strip().upper()

                    if is_ars_pair:
                        base_coin = crypto
                        m_ars = total
                        cot_c = price if is_buy else 0.0
                        cot_v = price if not is_buy else 0.0
                        if is_buy:
                            m_compra = qty
                            if fee and (not fee_coin or fee_coin == base_coin):
                                m_compra = max(0.0, m_compra - abs(fee))
                            processed.append(create_transaction(
                                fecha, 'Bitget', 'Compra', crypto,
                                m_compra, 0, cot_c, 0, m_ars, spot_comment, unique_id=uid_spot
                            ))
                        else:
                            processed.append(create_transaction(
                                fecha, 'Bitget', 'Venta', crypto,
                                0, qty, 0, cot_v, m_ars, spot_comment, unique_id=uid_spot
                            ))
                    else:
                        clean_pair = str(pair).strip()
                        sep_match = [p for p in re.split(r'[/_\-]', clean_pair) if p]
                        if len(sep_match) == 2:
                            base_coin, quote_coin = sep_match[0].strip(), sep_match[1].strip()
                        else:
                            base_coin = clean_pair
                            quote_coin = ""
                            for quote in ['FDUSD', 'USDT', 'USDC', 'BUSD', 'TUSD', 'DAI', 'EUR', 'USD', 'ARS', 'BTC', 'ETH', 'BNB']:
                                if clean_pair.endswith(quote) and len(clean_pair) > len(quote):
                                    if quote == 'ARS' and clean_pair.endswith(('BARS', 'STARS', 'WARS', 'MARS', 'PARS')):
                                        continue
                                    base_coin = clean_pair[:-len(quote)].rstrip('/_- ')
                                    quote_coin = quote
                                    break
                        from models.transaction_models import get_quote_usd_value
                        usd_ars_rate = get_usd_ars_rate(fecha)
                        usd_val = get_quote_usd_value(quote_coin, total, base_coin=base_coin, base_amount=qty, fecha=fecha)
                        m_ars = usd_val * usd_ars_rate
                        comment = f"[INTERCAMBIO: {quote_coin}->{base_coin}]" if is_buy else f"[INTERCAMBIO: {base_coin}->{quote_coin}]"

                        uid_c = f"{order_id}_c" if order_id else None
                        uid_v = f"{order_id}_v" if order_id else None

                        if is_buy:
                            m_compra = qty
                            if fee and (not fee_coin or fee_coin == base_coin):
                                m_compra = max(0.0, m_compra - abs(fee))
                            cot_c = m_ars / m_compra if m_compra > 0 else 0.0
                            processed.append(create_transaction(
                                fecha, 'Bitget', 'Compra', base_coin,
                                m_compra, 0, cot_c, 0, m_ars, comment, unique_id=uid_c
                            ))
                            cot_v = m_ars / total if total > 0 else 0.0
                            processed.append(create_transaction(
                                fecha, 'Bitget', 'Venta', quote_coin,
                                0, total, 0, cot_v, m_ars, comment, unique_id=uid_v
                            ))
                        else:
                            cot_v = m_ars / qty if qty > 0 else 0.0
                            processed.append(create_transaction(
                                fecha, 'Bitget', 'Venta', base_coin,
                                0, qty, 0, cot_v, m_ars, comment, unique_id=uid_v
                            ))
                            cot_c = m_ars / total if total > 0 else 0.0
                            processed.append(create_transaction(
                                fecha, 'Bitget', 'Compra', quote_coin,
                                total, 0, cot_c, 0, m_ars, comment, unique_id=uid_c
                            ))
            except Exception as e:
                print(f"Error procesando fila Bitget: {e}")
                continue

    except Exception as e:
        print(f"Error Bitget Parser: {e}")
        return [], []
    return processed, raw_sample
