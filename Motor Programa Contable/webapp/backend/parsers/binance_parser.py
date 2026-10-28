import os
import io
import re
import logging
import pandas as pd
from utils.exceptions import MissingColumnsError

logger = logging.getLogger(__name__)

try:
    from .base_parser import (
        _normalize_text, parse_date, clean_decimal,
        limpiar_numero_binance, is_cancelled_transaction,
        create_transaction, get_usd_ars_rate, get_fiat_usd_rate
    )
except ImportError:
    from parsers.base_parser import (
        _normalize_text, parse_date, clean_decimal,
        limpiar_numero_binance, is_cancelled_transaction,
        create_transaction, get_usd_ars_rate, get_fiat_usd_rate
    )

try:
    from .binance_helpers import (
        find_binance_column,
        get_binance_dataframes,
        _process_binance_convert_or_autoinvest,
        _process_binance_deposits_withdrawals
    )
except ImportError:
    from parsers.binance_helpers import (
        find_binance_column,
        get_binance_dataframes,
        _process_binance_convert_or_autoinvest,
        _process_binance_deposits_withdrawals
    )

__all__ = [
    'find_binance_column',
    'get_binance_dataframes',
    '_process_binance_convert_or_autoinvest',
    '_process_binance_deposits_withdrawals',
    'process_binance_csv',
    'process_binance_zip'
]


def process_binance_csv(file_obj, filename):
    """Parses Binance CSV or Excel (.xlsx/.xls) file (Spot, P2P, Auto-Invest, Convert, Pay, Deposit/Withdrawal)."""
    processed = []
    raw_sample = []
    try:
        dfs = get_binance_dataframes(file_obj, filename)
        if not dfs:
            return [], []
            
        for df in dfs:
            if df is None or df.empty:
                continue
                
            df.columns = [str(c).lower().strip() for c in df.columns]
            if len(raw_sample) < 10:
                raw_sample.extend(df.head(10).fillna('').astype(str).to_dict(orient='records'))

            ex_col = find_binance_column(df, ['exchange', 'plataforma', 'entidad', 'broker', 'origen', 'cuenta', 'exchange/plataforma'])

            # Binance P2P Columns
            p2p_type = find_binance_column(df, ['tipo de orden', 'tipo de transacción', 'tipo de operación', 'tipo de operacion', 'order type', 'order_type', 'tipo', 'side', 'type', 'dirección', 'direccion'])
            p2p_fiat = find_binance_column(df, ['tipo de fiat', 'moneda fiduciaria', 'moneda fiat', 'fiat type', 'fiat_type', 'fiat currency', 'fiat', 'fiduciaria'])
            p2p_asset = find_binance_column(df, ['tipo de activo', 'activo cripto', 'criptomoneda', 'asset type', 'asset_type', 'activo', 'cripto', 'asset', 'crypto', 'moneda', 'coin', 'base asset'])
            p2p_status = find_binance_column(df, ['estado de la orden', 'order status', 'status', 'estado', 'state', 'situación', 'situacion'])
            p2p_created = find_binance_column(df, ['hora de creación', 'fecha de creación', 'fecha de la orden', 'created time', 'created_time', 'create time', 'fecha y hora', 'fecha/hora', 'fecha', 'hora', 'date', 'time', 'order time', 'utc_time', 'utc time', 'time(utc)'])
            p2p_qty = find_binance_column(df, ['monto cripto', 'cantidad cripto', 'quantity', 'cantidad', 'monto', 'amount', 'qty', 'crypto amount', 'change'])
            p2p_price = find_binance_column(df, ['precio unitario', 'unit price', 'price', 'precio', 'cotización', 'cotizacion', 'unit price (fiat)'])
            p2p_total = find_binance_column(df, ['precio total', 'monto total', 'total price', 'total_price', 'total (fiat)', 'monto (fiat)', 'importe total', 'total', 'monto fiat', 'monto total (fiat)'])

            # Binance Spot Columns
            spot_pair = find_binance_column(df, ['pair', 'par', 'instrumento', 'market', 'mercado', 'symbol'])
            spot_side = find_binance_column(df, ['side', 'lado', 'tipo', 'tipo de operación', 'type', 'tipo de operacion'])
            spot_exec = find_binance_column(df, ['executed', 'ejecutado', 'monto ejecutado', 'amount', 'cantidad'])
            spot_date = find_binance_column(df, ['date(utc)', 'date', 'fecha', 'time', 'hora', 'fecha/hora'])
            spot_price = find_binance_column(df, ['price', 'precio'])
            spot_amt = find_binance_column(df, ['total', 'monto', 'amount', 'total (fiat)'])
            if spot_exec and spot_amt and spot_exec == spot_amt:
                alt_total = find_binance_column(df, ['total', 'monto total', 'total amount'])
                if alt_total and alt_total != spot_exec:
                    spot_amt = alt_total

            p2p_order_id = find_binance_column(df, ['order number', 'número de pedido', 'numero de pedido', 'número de orden', 'numero de orden', 'order no.', 'order no', 'order id', 'order_id'])
            spot_order_id = find_binance_column(df, [
                'order id', 'order no', 'order_id', 'order number', 'order no.',
                'número de orden', 'numero de orden', 'n.º de orden', 'id de orden',
                'trade id', 'trade_id', 'id de trade', 'tradeid', 'id'
            ])

            # Disambiguate P2P vs Spot: P2P has fiat and order_id/asset, while Spot strictly requires a trading pair.
            is_p2p = (p2p_fiat is not None or (spot_pair is None and (p2p_status is not None or (p2p_asset is not None and p2p_order_id is not None))))
            is_spot = (spot_pair is not None and spot_side is not None and (spot_exec is not None or spot_price is not None)) and not is_p2p

            if not is_p2p and not is_spot:
                # Check Convert / Auto-invest
                convert_records = _process_binance_convert_or_autoinvest(df, 'Binance')
                if convert_records:
                    processed.extend(convert_records)
                    continue

                # Check Deposits / Withdrawals
                dep_with_records = _process_binance_deposits_withdrawals(df, 'Binance')
                if dep_with_records:
                    processed.extend(dep_with_records)
                    continue

            if is_p2p:
                for index, row in df.iterrows():
                    if is_cancelled_transaction(row):
                        continue
                    try:
                        p2p_uid = str(row.get(p2p_order_id, '')).strip() if p2p_order_id else ''
                        actual_uid = p2p_uid if p2p_uid and p2p_uid.lower() not in ('nan', 'none', '') else None
                        fecha_raw = row.get(p2p_created, '') if p2p_created else ''
                        fecha = parse_date(fecha_raw, 'binance_p2p')
                        
                        tipo_raw = str(row.get(p2p_type, '')).lower().strip() if p2p_type else ''
                        is_buy = tipo_raw in ('buy', 'compra', 'comprar') or 'buy' in tipo_raw or 'compra' in tipo_raw
                        
                        fiat = str(row.get(p2p_fiat, 'ARS')).upper().strip() if p2p_fiat else 'ARS'
                        asset = str(row.get(p2p_asset, 'USDT')).upper().strip() if p2p_asset else 'USDT'
                        if asset in ('ARS', '$', 'PESO', 'PESOS', 'ARGENTIN'):
                            continue
                        
                        qty = clean_decimal(row.get(p2p_qty, 0)) if p2p_qty else 0.0
                        price = clean_decimal(row.get(p2p_price, 0)) if p2p_price else 0.0
                        total = clean_decimal(row.get(p2p_total, qty * price)) if p2p_total else (qty * price)
                        
                        row_ex = str(row.get(ex_col, '')).strip() if ex_col else ''
                        ex_name = row_ex if row_ex and row_ex.lower() not in ['', 'nan', 'none'] else 'Binance P2P'

                        is_ars = any(k in fiat for k in ['ARS', 'PESO', 'ARGENTIN', '$']) or not fiat or fiat == ''
                        if is_ars:
                            total_ars = total
                            price_ars = price
                        else:
                            usd_ars_rate = get_usd_ars_rate(fecha)
                            fiat_usd = get_fiat_usd_rate(fiat)
                            total_ars = total * fiat_usd * usd_ars_rate
                            price_ars = price * fiat_usd * usd_ars_rate

                        p2p_comment = f"P2P [{fiat}]" if not is_ars else "P2P"
                        if is_buy:
                            processed.append(create_transaction(
                                fecha, ex_name, 'Compra', asset,
                                qty, 0, price_ars, 0, total_ars, p2p_comment, unique_id=actual_uid
                            ))
                        else:
                            processed.append(create_transaction(
                                fecha, ex_name, 'Venta', asset,
                                0, qty, 0, price_ars, total_ars, p2p_comment, unique_id=actual_uid
                            ))
                    except Exception as e:
                        print(f"Error procesando fila Binance P2P: {e}")
                        pass
                
            elif is_spot:
                for index, row in df.iterrows():
                    if is_cancelled_transaction(row):
                        continue
                    try:
                        spot_uid = str(row.get(spot_order_id, '')).strip() if spot_order_id else ''
                        actual_spot_uid = spot_uid if spot_uid and spot_uid.lower() not in ('nan', 'none', '') else None
                        fecha = parse_date(row.get(spot_date), 'binance_spot')
                        side = str(row.get(spot_side)).upper().strip()
                        is_buy = 'BUY' in side or 'COMPRA' in side
                        pair = str(row.get(spot_pair, '')).upper().strip()
                        precio = clean_decimal(row.get(spot_price, 0))
                        cant = limpiar_numero_binance(row.get(spot_exec, 0))
                        total = limpiar_numero_binance(row.get(spot_amt, cant * precio))
                        
                        row_ex = str(row.get(ex_col, '')).strip() if ex_col else ''
                        ex_name = row_ex if row_ex and row_ex.lower() not in ['', 'nan', 'none'] else 'Binance Spot'

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

                        if is_ars_pair:
                            m_ars = total
                            cot_compra = precio if is_buy else 0.0
                            cot_venta = precio if not is_buy else 0.0
                            if is_buy:
                                processed.append(create_transaction(
                                    fecha, ex_name, 'Compra', crypto,
                                    cant, 0, cot_compra, 0, m_ars, 'Spot', unique_id=actual_spot_uid
                                ))
                            else:
                                processed.append(create_transaction(
                                    fecha, ex_name, 'Venta', crypto,
                                    0, cant, 0, cot_venta, m_ars, 'Spot', unique_id=actual_spot_uid
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
                                    
                            import db_manager
                            year = getattr(fecha, 'year', None)
                            if fecha is None:
                                logging.getLogger(__name__).warning("Binance Spot trade no-ARS: fecha es None, usando fallback USD/ARS rate 1000.0")
                                rate = 1000.0
                            else:
                                try:
                                    settings = db_manager.get_tax_settings(year) if year else {}
                                    rate = settings.get('usd_ars_exchange_rate', 1000.0) if settings else 1000.0
                                    if rate == 1000.0 and (not settings or 'usd_ars_exchange_rate' not in settings):
                                        logging.getLogger(__name__).warning(f"Binance Spot trade no-ARS: no se encontraron tax settings para año={year} (fecha={fecha}), usando fallback USD/ARS rate 1000.0")
                                except Exception as e:
                                    logging.getLogger(__name__).warning(f"Binance Spot trade no-ARS: fallo en get_tax_settings para año={year} (fecha={fecha}): {e}, usando fallback USD/ARS rate 1000.0")
                                    rate = 1000.0
                                
                            from models.transaction_models import get_quote_usd_value
                            usd_val = get_quote_usd_value(quote_coin, total, base_coin=base_coin, base_amount=cant, fecha=fecha)
                            m_ars = usd_val * rate
                            
                            uid_str = actual_spot_uid
                            uid_c = f"{uid_str}_c" if uid_str else None
                            uid_v = f"{uid_str}_v" if uid_str else None
                            if quote_coin:
                                comment_swap = f"[INTERCAMBIO: {quote_coin}->{base_coin}]" if is_buy else f"[INTERCAMBIO: {base_coin}->{quote_coin}]"
                                if is_buy:
                                    cot_c = m_ars / cant if cant > 0 else 0.0
                                    processed.append(create_transaction(
                                        fecha, ex_name, 'Compra', base_coin,
                                        cant, 0, cot_c, 0, m_ars, comment_swap, unique_id=uid_c
                                    ))
                                    cot_v = m_ars / total if total > 0 else 0.0
                                    processed.append(create_transaction(
                                        fecha, ex_name, 'Venta', quote_coin,
                                        0, total, 0, cot_v, m_ars, comment_swap, unique_id=uid_v
                                    ))
                                else:
                                    cot_v = m_ars / cant if cant > 0 else 0.0
                                    processed.append(create_transaction(
                                        fecha, ex_name, 'Venta', base_coin,
                                        0, cant, 0, cot_v, m_ars, comment_swap, unique_id=uid_v
                                    ))
                                    cot_c = m_ars / total if total > 0 else 0.0
                                    processed.append(create_transaction(
                                        fecha, ex_name, 'Compra', quote_coin,
                                        total, 0, cot_c, 0, m_ars, comment_swap, unique_id=uid_c
                                    ))
                            else:
                                cot_compra = (precio * rate) if is_buy else 0.0
                                cot_venta = (precio * rate) if not is_buy else 0.0
                                if is_buy:
                                    processed.append(create_transaction(
                                        fecha, ex_name, 'Compra', base_coin,
                                        cant, 0, cot_compra, 0, m_ars, 'Spot', unique_id=uid_str
                                    ))
                                else:
                                    processed.append(create_transaction(
                                        fecha, ex_name, 'Venta', base_coin,
                                        0, cant, 0, cot_venta, m_ars, 'Spot', unique_id=uid_str
                                    ))
                    except Exception as e:
                        print(f"Error procesando fila Binance Spot: {e}")
                        pass

    except MissingColumnsError:
        raise
    except Exception as e:
        print(f"Error Binance CSV: {e}")
        if "binance" in filename.lower():
            raise Exception(f"Error critico procesando Binance: {str(e)}")
        return [], []
    return processed, raw_sample

def process_binance_zip(file_obj, filename):
    """Legacy wrapper for zip files, now delegated to generic archive processor."""
    try:
        from .archive_processor import process_archive
    except ImportError:
        from parsers.archive_processor import process_archive
    return process_archive(file_obj, filename)
