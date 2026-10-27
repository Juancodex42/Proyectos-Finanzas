import pandas as pd
try:
    from services import config_service as config_manager
except ImportError:
    import config_manager
from exceptions import MissingColumnsError

try:
    from .base_parser import (
        _normalize_text, parse_date, clean_decimal,
        find_column_fuzzy, validate_columns,
        is_cancelled_transaction, create_transaction, get_usd_ars_rate, get_fiat_usd_rate
    )
except ImportError:
    from parsers.base_parser import (
        _normalize_text, parse_date, clean_decimal,
        find_column_fuzzy, validate_columns,
        is_cancelled_transaction, create_transaction, get_usd_ars_rate, get_fiat_usd_rate
    )

def process_fiwind(file_obj, filename):
    """Processes Fiwind trades, deposits, withdrawals, and conversions from CSV or Excel."""
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
                    try:
                        file_obj.seek(0)
                        kwargs = {'encoding': enc}
                        if sep is None:
                            kwargs['sep'] = None
                            kwargs['engine'] = 'python'
                        else:
                            kwargs['sep'] = sep
                        df_csv = pd.read_csv(file_obj, **kwargs)
                        if df_csv is not None and not df_csv.empty and len(df_csv.columns) > 1:
                            df = df_csv
                            break
                    except Exception:
                        pass
                if df is not None:
                    break
            if df is None:
                file_obj.seek(0)
                df = pd.read_csv(file_obj)
        df.columns = [str(c).lower().strip() for c in df.columns]
        raw_sample = df.head(10).fillna('').astype(str).to_dict(orient='records')
        
        validate_columns(df, 'fiwind')

        c_date = find_column_fuzzy(df, [config_manager.get_column('fiwind', 'fecha'), 'fecha', 'date', 'datetime', 'fecha/hora', 'created_at', 'timestamp'])
        c_type = find_column_fuzzy(df, [config_manager.get_column('fiwind', 'tipo'), 'tipo', 'type', 'operacion', 'operación', 'action', 'transaction type'])
        c_curr = find_column_fuzzy(df, [config_manager.get_column('fiwind', 'moneda'), 'destination currency', 'destination_currency', 'moneda_destino', 'moneda destino', 'asset', 'destino', 'moneda'])
        c_curr_orig = find_column_fuzzy(df, [config_manager.get_column('fiwind', 'moneda_origen'), 'source currency', 'source_currency', 'moneda_origen', 'moneda origen', 'origen', 'from_currency'])
        c_amt = find_column_fuzzy(df, [config_manager.get_column('fiwind', 'monto'), 'destination amount', 'destination_amount', 'monto_destino', 'monto destino', 'amount', 'monto'])
        c_amt_orig = find_column_fuzzy(df, [config_manager.get_column('fiwind', 'monto_origen'), 'source amount', 'source_amount', 'monto_origen', 'monto origen', 'monto_inicial'])
        c_price = find_column_fuzzy(df, [config_manager.get_column('fiwind', 'precio'), 'precio', 'price', 'rate', 'cotizacion', 'cotización'])
        c_id = find_column_fuzzy(df, ['id', 'id_operacion', 'codigo_operacion', 'codigo de operacion', 'operation_id', 'order_id', 'txid', 'referencia', 'reference', 'numero'])

        FIAT_COINS = ('ARS', 'USD', 'EUR')
        records = df.to_dict('records')
        for index, row in enumerate(records):
            if is_cancelled_transaction(row):
                continue
            try:
                fecha = parse_date(row.get(c_date), 'fiwind')
                tipo_raw = str(row.get(c_type, '')).upper()
                raw_id = str(row.get(c_id, '')).strip() if c_id else ''
                row_uid = raw_id if raw_id and raw_id.lower() not in ('nan', 'none', 'null', '') else None
                row_comment = tipo_raw

                raw_dest = row.get(c_curr, '')
                moneda_destino = '' if pd.isna(raw_dest) else str(raw_dest).strip().upper()
                if moneda_destino in ('NAN', 'NONE', 'NULL'):
                    moneda_destino = ''

                raw_orig = row.get(c_curr_orig, '')
                moneda_origen = '' if pd.isna(raw_orig) else str(raw_orig).strip().upper()
                if moneda_origen in ('NAN', 'NONE', 'NULL'):
                    moneda_origen = ''
                monto_destino = clean_decimal(row.get(c_amt, 0))
                monto_origen = clean_decimal(row.get(c_amt_orig, 0))
                cotizacion = clean_decimal(row.get(c_price, 0))

                tipo_normalized = _normalize_text(tipo_raw)

                is_conversion = any(kw in tipo_normalized for kw in [
                    'conversion', 'convert', 'swap', 'exchange', 'trade', 'buy', 'sell', 'compra', 'venta'
                ])
                is_deposit = any(kw in tipo_normalized for kw in [
                    'deposito', 'deposit', 'ingreso', 'incoming', 'received', 'receive',
                    'rendimiento', 'reward', 'staking', 'earn', 'interes', 'interest'
                ])
                is_withdrawal = any(kw in tipo_normalized for kw in [
                    'retiro', 'withdrawal', 'envio', 'transfer', 'sent', 'send', 'outgoing'
                ])

                if is_conversion:
                    if moneda_origen in FIAT_COINS and moneda_destino and moneda_destino not in FIAT_COINS:
                        if moneda_origen == 'ARS':
                            m_ars = abs(monto_origen)
                            cot_ars = cotizacion
                        else:
                            fiat_rate = get_fiat_usd_rate(moneda_origen) * get_usd_ars_rate(fecha)
                            m_ars = abs(monto_origen) * fiat_rate
                            cot_ars = (cotizacion * fiat_rate) if cotizacion > 0 else (m_ars / abs(monto_destino) if abs(monto_destino) > 0 else 0.0)
                        processed.append(create_transaction(
                            fecha, 'Fiwind', 'Compra', moneda_destino,
                            abs(monto_destino), 0, cot_ars, 0, m_ars, row_comment, unique_id=row_uid
                        ))
                    elif moneda_destino in FIAT_COINS and moneda_origen and moneda_origen not in FIAT_COINS:
                        if moneda_destino == 'ARS':
                            m_ars = abs(monto_destino)
                            cot_ars = cotizacion
                        else:
                            fiat_rate = get_fiat_usd_rate(moneda_destino) * get_usd_ars_rate(fecha)
                            m_ars = abs(monto_destino) * fiat_rate
                            cot_ars = (cotizacion * fiat_rate) if cotizacion > 0 else (m_ars / abs(monto_origen) if abs(monto_origen) > 0 else 0.0)
                        processed.append(create_transaction(
                            fecha, 'Fiwind', 'Venta', moneda_origen,
                            0, abs(monto_origen), 0, cot_ars, m_ars, row_comment, unique_id=row_uid
                        ))
                    elif moneda_origen and moneda_destino and moneda_origen not in FIAT_COINS and moneda_destino not in FIAT_COINS:
                        usd_ars_rate = get_usd_ars_rate(fecha)
                        from models.transaction_models import get_quote_usd_value
                        if moneda_origen in ('USD', 'USDT', 'USDC', 'DAI', 'BUSD'):
                            usd_val = abs(monto_origen)
                        elif moneda_destino in ('USD', 'USDT', 'USDC', 'DAI', 'BUSD'):
                            usd_val = abs(monto_destino)
                        else:
                            usd_val = get_quote_usd_value(moneda_origen, abs(monto_origen), base_coin=moneda_destino, base_amount=abs(monto_destino), fecha=fecha)
                        ars_value = usd_val * usd_ars_rate

                        comment = f"[INTERCAMBIO: {moneda_origen}->{moneda_destino}]"
                        
                        cot_v = ars_value / abs(monto_origen) if abs(monto_origen) > 0 else 0.0
                        processed.append(create_transaction(
                            fecha, 'Fiwind', 'Venta', moneda_origen,
                            0, abs(monto_origen), 0, cot_v, ars_value, comment, unique_id=f"{row_uid}_v" if row_uid else None
                        ))
                        
                        cot_c = ars_value / abs(monto_destino) if abs(monto_destino) > 0 else 0.0
                        processed.append(create_transaction(
                            fecha, 'Fiwind', 'Compra', moneda_destino,
                            abs(monto_destino), 0, cot_c, 0, ars_value, comment, unique_id=f"{row_uid}_c" if row_uid else None
                        ))
                elif is_deposit:
                    target_coin = ''
                    if moneda_destino and moneda_destino not in FIAT_COINS:
                        target_coin = moneda_destino
                    elif moneda_origen and moneda_origen not in FIAT_COINS:
                        target_coin = moneda_origen
                    
                    if not target_coin:
                        # Purely FIAT deposit (ARS/USD/EUR into Fiwind) -> skip from crypto inventory
                        continue

                    qty = abs(monto_destino if monto_destino > 0 else monto_origen)
                    usd_ars_rate = get_usd_ars_rate(fecha)
                    from models.transaction_models import get_quote_usd_value
                    if target_coin in ('USD', 'USDT', 'USDC', 'DAI', 'BUSD'):
                        m_ars = qty * usd_ars_rate
                        rate = usd_ars_rate
                    else:
                        usd_val = get_quote_usd_value(target_coin, qty, fecha=fecha)
                        m_ars = usd_val * usd_ars_rate
                        rate = m_ars / qty if qty > 0 else usd_ars_rate

                    processed.append(create_transaction(
                        fecha, 'Fiwind', 'Ingreso Cripto', target_coin,
                        qty, 0, 0.0, 0, m_ars, row_comment, unique_id=f"{row_uid}_dep" if row_uid else None
                    ))
                elif is_withdrawal:
                    target_coin = ''
                    if moneda_origen and moneda_origen not in FIAT_COINS:
                        target_coin = moneda_origen
                    elif moneda_destino and moneda_destino not in FIAT_COINS:
                        target_coin = moneda_destino
                        
                    if not target_coin:
                        # Purely FIAT withdrawal (ARS/USD/EUR to bank account) -> skip from crypto inventory
                        continue

                    qty = abs(monto_origen if monto_origen > 0 else monto_destino)
                    usd_ars_rate = get_usd_ars_rate(fecha)
                    from models.transaction_models import get_quote_usd_value
                    if target_coin in ('USD', 'USDT', 'USDC', 'DAI', 'BUSD'):
                        m_ars = qty * usd_ars_rate
                        rate = usd_ars_rate
                    else:
                        usd_val = get_quote_usd_value(target_coin, qty, fecha=fecha)
                        m_ars = usd_val * usd_ars_rate
                        rate = m_ars / qty if qty > 0 else usd_ars_rate

                    processed.append(create_transaction(
                        fecha, 'Fiwind', 'Retiro Cripto', target_coin,
                        0, qty, 0, rate, m_ars, row_comment, unique_id=f"{row_uid}_ret" if row_uid else None
                    ))
            except Exception as e:
                print(f"Error procesando fila en Fiwind: {e}")
                continue
    except MissingColumnsError:
        raise
    except Exception as e:
        print(f"Error Fiwind: {e}")
        return [], []

    return processed, raw_sample
