import io
import re
import logging
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from utils.exceptions import MissingColumnsError
except ImportError:
    from compat.exceptions import MissingColumnsError

try:
    from .base_parser import (
        _normalize_text, parse_date, clean_decimal,
        find_column_fuzzy, is_cancelled_transaction,
        normalize_exchange_name, create_transaction, get_usd_ars_rate
    )
except ImportError:
    from parsers.base_parser import (
        _normalize_text, parse_date, clean_decimal,
        find_column_fuzzy, is_cancelled_transaction,
        normalize_exchange_name, create_transaction, get_usd_ars_rate
    )

def process_dynamic_csv(df, exchange_name, mapping, date_format="%d/%m/%Y %H:%M:%S"):
    """Generic CSV parser driven by user-configured mapping."""
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.rename(columns=lambda c: str(c).lower().strip())
    clean_mapping = {k: str(v).lower().strip() for k, v in mapping.items() if v}

    records = []
    for idx, row in df.iterrows():
        if is_cancelled_transaction(row):
            continue
        raw_date = row.get(clean_mapping.get("fecha", ""), "")
        raw_tipo_val = row.get(clean_mapping.get("tipo_operacion", ""), "")
        raw_tipo = str(raw_tipo_val).strip() if raw_tipo_val and str(raw_tipo_val).strip() not in ('nan', 'none', 'null') else ""
        raw_moneda = row.get(clean_mapping.get("moneda", ""), "USDT")
        raw_compra = row.get(clean_mapping.get("monto_compra_cripto", ""), 0)
        raw_venta = row.get(clean_mapping.get("monto_venta_cripto", ""), 0)
        raw_cot_compra = row.get(clean_mapping.get("cotizacion_compra", ""), 0)
        raw_cot_venta = row.get(clean_mapping.get("cotizacion_venta", ""), 0)
        raw_ars = row.get(clean_mapping.get("monto_ars", ""), 0)
        raw_notes = row.get(clean_mapping.get("comentarios", ""), "")

        try:
            parsed_date = parse_date(raw_date, exchange_name)
            if (parsed_date is None or pd.isna(parsed_date)) and date_format:
                try:
                    parsed_date = pd.to_datetime(raw_date, format=date_format)
                except Exception:
                    pass
            if parsed_date is None or pd.isna(parsed_date):
                try:
                    parsed_date = pd.to_datetime(raw_date, errors='coerce')
                except Exception:
                    pass
            if parsed_date is not None and not pd.isna(parsed_date) and hasattr(parsed_date, 'strftime'):
                formatted_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
            else:
                logger.warning(f"process_dynamic_csv: Fecha inválida '{raw_date}' para {exchange_name} en fila {idx}. Asignando fecha estándar ISO.")
                formatted_date = "1970-01-01 00:00:00"
        except Exception as e:
            logger.warning(f"process_dynamic_csv: Error al procesar fecha '{raw_date}' en fila {idx}: {e}. Asignando fecha estándar ISO.")
            formatted_date = "1970-01-01 00:00:00"

        m_compra = clean_decimal(raw_compra)
        m_venta = clean_decimal(raw_venta)
        c_compra = clean_decimal(raw_cot_compra)
        c_venta = clean_decimal(raw_cot_venta)
        m_ars = clean_decimal(raw_ars)

        if not raw_tipo:
            raw_tipo = "COMPRA" if (m_compra > 0 and m_venta == 0) else ("VENTA" if (m_venta > 0 and m_compra == 0) else "Movimiento Desconocido")

        from models.transaction_models import compute_canonical_tx_hash, canonicalize_ticker
        clean_coin = canonicalize_ticker(str(raw_moneda).upper())
        ref = str(raw_notes).strip() if raw_notes and str(raw_notes).strip() not in ('nan', 'none', 'null') else ""
        tx_hash = compute_canonical_tx_hash(formatted_date, exchange_name, raw_tipo, clean_coin, m_compra, m_venta, m_ars, ref)

        records.append({
            "tx_hash": tx_hash, "fecha": formatted_date, "exchange": exchange_name,
            "tipo_operacion": str(raw_tipo).upper(), "moneda": clean_coin,
            "monto_compra_cripto": m_compra, "monto_venta_cripto": m_venta,
            "cotizacion_compra": c_compra, "cotizacion_venta": c_venta,
            "monto_ars": m_ars, "comentarios": ref
        })

    return pd.DataFrame(records)

def process_other_exchange(file_obj, filename, exchange_hint=None):
    """
    Parses transactions from Lemon, Bybit, OKX, Belo, Buenbit, Kraken,
    or generic exchange files.
    """
    file_obj.seek(0)
    ext = filename.lower()
    df = None
    if ext.endswith('.xlsx') or ext.endswith('.xls'):
        try:
            df = pd.read_excel(file_obj)
        except Exception:
            pass
    else:
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

    clean_fn = filename.lower()
    cols_joined = " ".join(df.columns)
    detected_ex = exchange_hint
    if not detected_ex:
        for kw, ex_label in (('lemon', 'Lemon Cash'), ('bybit', 'Bybit'), ('okx', 'OKX'), ('belo', 'Belo'), ('buenbit', 'Buenbit'), ('kraken', 'Kraken')):
            if kw in clean_fn or kw in cols_joined:
                detected_ex = ex_label
                break
        if not detected_ex:
            detected_ex = 'Otros'

    processed = []
    c_date = find_column_fuzzy(df, ['fecha', 'date', 'created_at', 'time', 'timestamp', 'datetime', 'filled time', 'trade time'])
    c_type = find_column_fuzzy(df, ['tipo', 'type', 'operacion', 'operación', 'action', 'side'])
    c_coin = find_column_fuzzy(df, ['moneda', 'asset', 'currency', 'coin', 'crypto', 'symbol', 'pair'])
    c_pair = find_column_fuzzy(df, ['par', 'pair', 'market', 'mercado', 'instrument', 'symbol', 'simbolo'])
    c_quote = find_column_fuzzy(df, ['quote', 'quote_currency', 'contraparte', 'moneda_cotizacion', 'moneda_origen', 'source_currency', 'destino'])
    c_amount = find_column_fuzzy(df, ['monto', 'amount', 'cantidad', 'qty', 'volume', 'executed', 'size', 'contracts', 'filled qty'])
    c_quote_amt = find_column_fuzzy(df, ['monto_origen', 'monto origen', 'source_amount', 'quote_amount', 'filled value'])
    c_price = find_column_fuzzy(df, ['precio', 'price', 'cotizacion', 'cotización', 'rate', 'unit price', 'avg price', 'order price'])
    c_fiat = find_column_fuzzy(df, ['monto ars', 'monto_ars', 'total', 'fiat', 'total_price', 'value', 'subtotal', 'filled value'])
    c_id = find_column_fuzzy(df, ['order id', 'order_id', 'id', 'txid', 'hash', 'operacion', 'codigo', 'reference', 'referencia', 'order no', 'order no.'])

    for index, row in df.iterrows():
        if is_cancelled_transaction(row):
            continue
        try:
            fecha_raw = row.get(c_date) if c_date else None
            fecha = parse_date(fecha_raw, detected_ex)
            raw_tipo_val = row.get(c_type) if c_type else None
            tipo_raw = str(raw_tipo_val).upper().strip() if raw_tipo_val is not None and not pd.isna(raw_tipo_val) else ''
            raw_coin_val = row.get(c_coin) if c_coin else None
            coin_str = str(raw_coin_val).upper().strip() if raw_coin_val is not None and not pd.isna(raw_coin_val) else ''

            raw_pair_val = row.get(c_pair) if (c_pair and c_pair != c_coin) else None
            pair_str = str(raw_pair_val).upper().strip() if raw_pair_val is not None and not pd.isna(raw_pair_val) else ''

            target_pair = pair_str or coin_str
            base_coin, quote_coin = "", ""
            is_stable_pair = False
            STABLE_COINS = ('USDT', 'USDC', 'DAI', 'BUSD', 'USD', 'USDP', 'FDUSD', 'PYUSD', 'UXD')

            for sep in ('/', '_', '-'):
                if sep in target_pair:
                    parts = target_pair.split(sep)
                    if len(parts) == 2:
                        p0, p1 = parts[0].strip(), parts[1].strip()
                        if p1 in ('TRC20', 'ERC20', 'BEP20', 'TRX', 'BSC', 'POLYGON', 'POL', 'SOL', 'AVAX', 'ARB', 'OP'):
                            continue
                        base_coin, quote_coin = p0, p1
                        break

            if not quote_coin:
                for st in STABLE_COINS + ('BTC', 'ETH', 'BNB'):
                    if target_pair.endswith(st) and len(target_pair) > len(st):
                        base_coin, quote_coin = target_pair[:-len(st)], st
                        break
                if not quote_coin and target_pair.endswith('ARS') and len(target_pair) > 3:
                    base_coin, quote_coin = target_pair[:-3], 'ARS'

            if not quote_coin and c_quote and c_quote != c_coin and c_quote != c_pair:
                raw_q = str(row.get(c_quote, '')).upper().strip()
                if raw_q and raw_q not in ('NAN', 'NONE', 'NULL'):
                    quote_coin = raw_q

            if (quote_coin in STABLE_COINS and quote_coin != coin_str) or any(
                f"/{st}" in target_pair or f"_{st}" in target_pair or f"-{st}" in target_pair or
                (target_pair.endswith(st) and len(target_pair) > len(st))
                for st in STABLE_COINS
            ):
                is_stable_pair = True

            coin_raw = base_coin if (base_coin and (coin_str == target_pair or '/' in coin_str or '_' in coin_str or '-' in coin_str)) else coin_str
            from models.transaction_models import canonicalize_ticker
            coin = canonicalize_ticker(coin_raw) if coin_raw and coin_raw not in ('NAN', 'NONE', 'NULL') else 'USDT'
            q_coin = canonicalize_ticker(quote_coin) if quote_coin and quote_coin not in ('NAN', 'NONE', 'NULL') else ''
            is_swap = bool(
                q_coin
                and q_coin not in ('ARS', 'PESO', 'PESOS', '$', 'USD', 'EUR', 'BRL', 'CLP', 'UYU', 'MXN', 'COP', 'PEN', 'GBP')
                and q_coin != coin
            )

            amount = abs(clean_decimal(row.get(c_amount, 0))) if c_amount else 0.0
            price = clean_decimal(row.get(c_price, 0)) if c_price else 0.0
            fiat = abs(clean_decimal(row.get(c_fiat, 0))) if c_fiat else 0.0
            quote_amt_col = abs(clean_decimal(row.get(c_quote_amt, 0))) if (c_quote_amt and c_quote_amt != c_amount) else 0.0
            raw_price = price
            is_fiat_explicitly_ars = bool(c_fiat and any(k in str(c_fiat).lower() for k in ('ars', 'peso', '$')))
            raw_total = fiat if not is_fiat_explicitly_ars else 0.0
            total_val = raw_total if raw_total > 0 else ((amount * raw_price) if (amount > 0 and raw_price > 0) else quote_amt_col)
            raw_id = str(row.get(c_id, '')).strip() if c_id else ''
            row_uid = raw_id if raw_id and raw_id.lower() not in ('nan', 'none', 'null', '') else None

            clean_text = _normalize_text
            raw_type = clean_text(tipo_raw)
            type_mappings = {
                'Ingreso Cripto': ['receive', 'recepcion', 'recepción', 'ingreso', 'deposit', 'deposito', 'depósito', 'entrada', 'abono'],
                'Retiro Cripto': ['send', 'envio', 'envío', 'retiro', 'withdrawal', 'withdraw', 'egreso', 'salida', 'extraccion', 'extracción'],
                'Compra': ['compra', 'buy', 'swap', 'convert', 'conversion', 'conversión', 'intercambio'],
                'Venta': ['venta', 'sell', 'consumo', 'pago', 'payment'],
            }
            op_type = None
            for mapped_type, words in type_mappings.items():
                if any(clean_text(w) in raw_type for w in words):
                    op_type = mapped_type
                    break
            if not op_type and any(x in raw_type for x in ['fee', 'commission', 'comision', 'tax']):
                op_type = 'Comisión'

            is_deposit = op_type == 'Ingreso Cripto'
            is_withdrawal = op_type == 'Retiro Cripto'
            is_buy = op_type == 'Compra'
            is_sell = op_type == 'Venta'

            if coin in ('ARS', 'PESO', 'PESOS', '$') and (is_deposit or is_withdrawal):
                continue

            usd_ars_rate = get_usd_ars_rate(fecha)
            from models.transaction_models import CRYPTO_REF_PRICES_USD, get_quote_usd_value
            FALLBACK_CRYPTO_REF_PRICES_USD = {
                'BTC': 60000.0, 'ETH': 3000.0, 'SOL': 150.0, 'BNB': 600.0,
                'AVAX': 30.0, 'LINK': 15.0, 'DOT': 7.0, 'XRP': 0.6, 'ADA': 0.5,
                'MATIC': 0.5, 'POL': 0.5, 'LTC': 70.0, 'BCH': 350.0, 'DOGE': 0.1,
                'SHIB': 0.00002, 'TRX': 0.12, 'NEAR': 5.0, 'ATOM': 5.0, 'UNI': 7.0
            }
            all_ref_prices = {**FALLBACK_CRYPTO_REF_PRICES_USD, **CRYPTO_REF_PRICES_USD}
            ex_lower = str(detected_ex).lower()
            is_intl_ex = ex_lower in ('bybit', 'okx', 'kraken', 'binance', 'kucoin', 'gate.io', 'coinbase', 'bitfinex')

            if price == 0 and fiat > 0 and amount > 0:
                price = fiat / amount

            ref_usd = all_ref_prices.get(coin, 0.0)
            if not ref_usd and fecha:
                try:
                    ref_usd = get_quote_usd_value(coin, 1.0, fecha=fecha)
                except Exception as e:
                    logger.warning(f"No se pudo resolver cotización USD para {coin} en fecha {fecha}: {e}")
                    ref_usd = 0.0
            if not ref_usd or ref_usd <= 0:
                logger.warning(f"Cotización USD de referencia no disponible para {coin} ({detected_ex}, fila {index})")

            has_usd_header = bool(c_price and any(k in str(c_price).lower() for k in ('usd', 'usdt', 'usdc')))
            if has_usd_header or is_stable_pair:
                is_usd_price = True
            elif coin in STABLE_COINS:
                is_usd_price = bool(price > 0 and (price <= 5.0 or abs(price - 1.0) < abs(price - usd_ars_rate)))
            elif ref_usd > 0 and price > 0:
                ref_ars = ref_usd * usd_ars_rate
                is_usd_price = abs(price - ref_usd) < abs(price - ref_ars)
            elif is_intl_ex:
                is_usd_price = True
            else:
                is_usd_price = False

            if is_swap and q_coin not in STABLE_COINS and not is_fiat_explicitly_ars:
                t_val = total_val if total_val > 0 else (amount * raw_price)
                usd_val = get_quote_usd_value(q_coin, t_val, base_coin=coin, base_amount=amount, fecha=fecha)
                fiat = usd_val * usd_ars_rate
            elif fiat == 0 and amount > 0:
                if price > 0:
                    fiat = amount * price * usd_ars_rate if is_usd_price else amount * price
                else:
                    usd_val = get_quote_usd_value(coin, amount, fecha=fecha)
                    fiat = usd_val * usd_ars_rate
            elif fiat > 0 and amount > 0 and is_usd_price:
                if not is_fiat_explicitly_ars:
                    if price > 0 and abs(fiat - (amount * price)) / max(fiat, 0.001) < 0.05:
                        fiat = fiat * usd_ars_rate
                    elif ref_usd > 0 and fiat < (amount * ref_usd * usd_ars_rate * 0.1):
                        fiat = fiat * usd_ars_rate

            cot = fiat / amount if amount > 0 else (price * usd_ars_rate if (price > 0 and is_usd_price) else (price if price > 0 else usd_ars_rate))
            comment = f"{tipo_raw} | ID: {row_uid}" if raw_id and raw_id.lower() not in ('nan', 'none', 'null', '') else tipo_raw

            if is_deposit:
                processed.append(create_transaction(
                    fecha, detected_ex, 'Ingreso Cripto', coin,
                    amount, 0, 0.0, 0, fiat, comment, unique_id=row_uid
                ))
            elif is_withdrawal:
                processed.append(create_transaction(
                    fecha, detected_ex, 'Retiro Cripto', coin,
                    0, amount, 0, cot, fiat, comment, unique_id=row_uid
                ))
            elif is_buy:
                is_explicit_swap = is_swap and any(clean_text(w) in raw_type for w in ['swap', 'convert', 'conversion', 'conversión', 'intercambio', 'canje'])
                raw_pair = target_pair
                is_pair_swap = is_swap and (is_explicit_swap or ('/' in raw_pair or '-' in raw_pair))
                uid_c = f"{row_uid}_c" if (is_pair_swap and total_val > 0 and row_uid) else row_uid
                swap_c_comment = f"[INTERCAMBIO: {q_coin}->{coin}] | {comment}" if (is_pair_swap and total_val > 0 and comment) else (f"[INTERCAMBIO: {q_coin}->{coin}]" if (is_pair_swap and total_val > 0) else comment)
                processed.append(create_transaction(
                    fecha, detected_ex, 'Compra', coin,
                    amount, 0, cot, 0, fiat, swap_c_comment, unique_id=uid_c
                ))
                if is_pair_swap and q_coin and total_val > 0:
                    cot_q = fiat / total_val if total_val > 0 else 0.0
                    uid_v = f"{row_uid}_v" if row_uid else None
                    processed.append(create_transaction(
                        fecha, detected_ex, 'Venta', q_coin,
                        0, total_val, 0, cot_q, fiat, swap_c_comment, unique_id=uid_v
                    ))
            elif is_sell:
                is_explicit_swap = is_swap and any(clean_text(w) in raw_type for w in ['swap', 'convert', 'conversion', 'conversión', 'intercambio', 'canje'])
                raw_pair = target_pair
                is_pair_swap = is_swap and (is_explicit_swap or ('/' in raw_pair or '-' in raw_pair))
                uid_v = f"{row_uid}_v" if (is_pair_swap and total_val > 0 and row_uid) else row_uid
                swap_v_comment = f"[INTERCAMBIO: {coin}->{q_coin}] | {comment}" if (is_pair_swap and total_val > 0 and comment) else (f"[INTERCAMBIO: {coin}->{q_coin}]" if (is_pair_swap and total_val > 0) else comment)
                processed.append(create_transaction(
                    fecha, detected_ex, 'Venta', coin,
                    0, amount, 0, cot, fiat, swap_v_comment, unique_id=uid_v
                ))
                if is_pair_swap and q_coin and total_val > 0:
                    cot_q = fiat / total_val if total_val > 0 else 0.0
                    uid_c = f"{row_uid}_c" if row_uid else None
                    processed.append(create_transaction(
                        fecha, detected_ex, 'Compra', q_coin,
                        total_val, 0, cot_q, 0, fiat, swap_v_comment, unique_id=uid_c
                    ))
            elif op_type == 'Comisión':
                processed.append(create_transaction(
                    fecha, detected_ex, 'Comisión Cripto', coin,
                    0, amount, 0, cot, fiat, comment, unique_id=row_uid
                ))
            elif amount > 0 or fiat > 0:
                is_reward = any(clean_text(k) in raw_type for k in ['STAKING', 'REWARD', 'EARN', 'INTERES', 'INTERÉS', 'CASHBACK', 'BONUS'])
                if is_reward:
                    processed.append(create_transaction(
                        fecha, detected_ex, 'Ingreso Cripto', coin,
                        amount, 0, cot, 0, fiat, f"Recompensa/Staking: {comment}", unique_id=row_uid
                    ))
                else:
                    processed.append(create_transaction(
                        fecha, detected_ex, 'Movimiento Desconocido', coin,
                        0, 0, cot, 0, fiat, f"Tipo no clasificado: {comment}", unique_id=row_uid
                    ))
        except Exception as e:
            logging.getLogger(__name__).warning(
                f"Error al procesar fila {index} para exchange '{detected_ex}': {e}. Fila descartada."
            )
            continue

    return processed, raw_sample
