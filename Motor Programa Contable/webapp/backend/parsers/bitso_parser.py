import pandas as pd
try:
    from services import config_service as config_manager
except ImportError:
    import config_manager
from utils.exceptions import MissingColumnsError

try:
    from .base_parser import (
        _normalize_text, parse_date, clean_decimal,
        is_cancelled_transaction, create_transaction, get_usd_ars_rate
    )
except ImportError:
    from parsers.base_parser import (
        _normalize_text, parse_date, clean_decimal,
        is_cancelled_transaction, create_transaction, get_usd_ars_rate
    )

def process_bitso(file_obj, filename):
    """Processes Bitso and Bitso Alpha CSV / Excel reports for trades, conversions, deposits, and withdrawals."""
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
                try:
                    df = pd.read_excel(file_obj)
                except Exception:
                    pass

        if df is None or df.empty:
            return [], []

        df.columns = [str(c).lower().strip() for c in df.columns]
        raw_sample = df.head(10).fillna('').astype(str).to_dict(orient='records')
        
        c_date = str(config_manager.get_column('bitso', 'datetime')).lower().strip()
        c_date_fallback = str(config_manager.get_column('bitso', 'date_fallback')).lower().strip()
        c_type = str(config_manager.get_column('bitso', 'type')).lower().strip()
        c_major = str(config_manager.get_column('bitso', 'major')).lower().strip()
        c_minor = str(config_manager.get_column('bitso', 'minor')).lower().strip()
        c_amt = str(config_manager.get_column('bitso', 'amount')).lower().strip()
        c_val = str(config_manager.get_column('bitso', 'value')).lower().strip()
        c_rate = str(config_manager.get_column('bitso', 'rate')).lower().strip()
        
        def _get_val(row, primary, candidates):
            if primary and primary in row.index and not pd.isna(row[primary]) and str(row[primary]).strip() != '':
                return row[primary]
            for cand in candidates:
                cand_clean = str(cand).lower().strip()
                for col in row.index:
                    if str(col).lower().strip() == cand_clean and not pd.isna(row[col]) and str(row[col]).strip() != '':
                        return row[col]
            return ''

        for index, row in df.iterrows():
            if is_cancelled_transaction(row):
                continue
            try:
                fecha_str = _get_val(row, c_date, [c_date_fallback, 'datetime', 'date', 'fecha', 'timestamp', 'created_at'])
                fecha = parse_date(fecha_str, 'bitso')
                
                tipo_raw = str(_get_val(row, c_type, ['type', 'tipo', 'side', 'operation'])).lower().strip()
                major = str(_get_val(row, c_major, ['major', 'asset', 'moneda', 'cripto', 'coin', 'symbol'])).upper().strip()
                minor = str(_get_val(row, c_minor, ['minor', 'fiat', 'quote', 'currency'])).upper().strip()
                cant_cripto = abs(clean_decimal(_get_val(row, c_amt, ['amount', 'cantidad', 'monto', 'qty'])))
                monto_fiat = abs(clean_decimal(_get_val(row, c_val, ['value', 'total', 'monto_ars', 'monto total', 'val'])))
                rate = clean_decimal(_get_val(row, c_rate, ['rate', 'price', 'precio', 'cotizacion', 'cotización']))

                if rate == 0 and cant_cripto > 0 and monto_fiat > 0:
                    rate = monto_fiat / cant_cripto
                elif monto_fiat == 0 and cant_cripto > 0 and rate > 0:
                    monto_fiat = cant_cripto * rate

                is_buy = 'buy' in tipo_raw or 'compra' in tipo_raw
                is_sell = 'sell' in tipo_raw or 'venta' in tipo_raw
                is_deposit = any(k in tipo_raw for k in ['deposit', 'deposito', 'funding', 'ingreso'])
                is_withdrawal = any(k in tipo_raw for k in ['withdraw', 'retiro', 'withdrawal', 'envio'])

                row_id = _get_val(row, '', ['order_id', 'order id', 'order id / oid', 'oid', 'id', 'txid', 'operation id', 'operacion'])
                actual_uid = str(row_id).strip() if row_id and str(row_id).strip().lower() not in ('', 'nan', 'none') else None

                row_ex = _get_val(row, '', ['exchange', 'plataforma', 'entidad', 'broker'])
                row_ex_str = str(row_ex).strip() if row_ex and str(row_ex).strip().lower() not in ['', 'nan', 'none'] else ''
                ex_name = row_ex_str if row_ex_str else 'Bitso Alpha'

                if is_deposit or is_withdrawal:
                    target_coin = major if major else (minor if minor else '')
                else:
                    target_coin = major if major else (minor if minor and minor != 'ARS' else 'USDT')

                usd_ars_rate = get_usd_ars_rate(fecha)
                if minor == 'ARS' or not minor:
                    monto_ars = monto_fiat
                    rate_ars = rate
                elif minor in ('USD', 'USDT', 'USDC', 'DAI', 'BUSD', 'UXD'):
                    monto_ars = monto_fiat * usd_ars_rate
                    rate_ars = rate * usd_ars_rate
                elif minor == 'EUR':
                    monto_ars = monto_fiat * 1.08 * usd_ars_rate
                    rate_ars = rate * 1.08 * usd_ars_rate
                else:
                    from models.transaction_models import get_quote_usd_value
                    usd_val = get_quote_usd_value(minor, monto_fiat, base_coin=target_coin, base_amount=cant_cripto, fecha=fecha)
                    monto_ars = usd_val * usd_ars_rate
                    rate_ars = monto_ars / cant_cripto if cant_cripto > 0 else (rate * usd_ars_rate)

                if is_buy:
                    processed.append(create_transaction(
                        fecha, ex_name, 'Compra', target_coin,
                        cant_cripto, 0, rate_ars, 0, monto_ars, 'Bitso Trade', unique_id=actual_uid
                    ))
                    if minor and minor != 'ARS' and target_coin != minor and monto_fiat > 0:
                        cot_v = monto_ars / monto_fiat if monto_fiat > 0 else 0.0
                        processed.append(create_transaction(
                            fecha, ex_name, 'Venta', minor,
                            0, monto_fiat, 0, cot_v, monto_ars, f'Bitso Trade | [INTERCAMBIO: {minor}->{target_coin}]', unique_id=f"{actual_uid}_quote" if actual_uid else None
                        ))
                elif is_sell:
                    processed.append(create_transaction(
                        fecha, ex_name, 'Venta', target_coin,
                        0, cant_cripto, 0, rate_ars, monto_ars, 'Bitso Trade', unique_id=actual_uid
                    ))
                    if minor and minor != 'ARS' and target_coin != minor and monto_fiat > 0:
                        cot_c = monto_ars / monto_fiat if monto_fiat > 0 else 0.0
                        processed.append(create_transaction(
                            fecha, ex_name, 'Compra', minor,
                            monto_fiat, 0, cot_c, 0, monto_ars, f'Bitso Trade | [INTERCAMBIO: {target_coin}->{minor}]', unique_id=f"{actual_uid}_quote" if actual_uid else None
                        ))
                elif is_deposit:
                    if not target_coin or target_coin in ('ARS', 'USD', 'EUR') or (minor == 'ARS' and not major):
                        continue
                    from models.transaction_models import get_quote_usd_value
                    usd_val = get_quote_usd_value(target_coin, cant_cripto, fecha=fecha)
                    m_ars = monto_ars if monto_ars > 0 else (usd_val * usd_ars_rate)
                    c_ars = rate_ars if rate_ars > 0 else (m_ars / cant_cripto if cant_cripto > 0 else usd_ars_rate)
                    processed.append(create_transaction(
                        fecha, ex_name, 'Ingreso Cripto', target_coin,
                        cant_cripto, 0, 0.0, 0, m_ars, 'Bitso Deposit', unique_id=f"{actual_uid}_dep" if actual_uid else None
                    ))
                elif is_withdrawal:
                    if not target_coin or target_coin in ('ARS', 'USD', 'EUR') or (minor == 'ARS' and not major):
                        continue
                    from models.transaction_models import get_quote_usd_value
                    usd_val = get_quote_usd_value(target_coin, cant_cripto, fecha=fecha)
                    m_ars = monto_ars if monto_ars > 0 else (usd_val * usd_ars_rate)
                    c_ars = rate_ars if rate_ars > 0 else (m_ars / cant_cripto if cant_cripto > 0 else usd_ars_rate)
                    processed.append(create_transaction(
                        fecha, ex_name, 'Retiro Cripto', target_coin,
                        0, cant_cripto, 0, c_ars, m_ars, 'Bitso Withdrawal', unique_id=f"{actual_uid}_ret" if actual_uid else None
                    ))
                elif any(k in tipo_raw for k in ['fee', 'comision', 'comisión', 'tax', 'impuesto']):
                    if cant_cripto > 0 and target_coin not in ('ARS', 'USD', 'EUR'):
                        processed.append(create_transaction(
                            fecha, ex_name, 'Comisión Cripto', target_coin,
                            0, cant_cripto, 0, rate_ars, monto_ars, f'Bitso Fee: {tipo_raw}', unique_id=f"{actual_uid}_fee" if actual_uid else None
                        ))
                    else:
                        continue
                elif cant_cripto > 0 or monto_fiat > 0:
                    t_desc = tipo_raw.title() if tipo_raw else 'Operacion'
                    processed.append(create_transaction(
                        fecha, ex_name, 'Otro', target_coin,
                        cant_cripto, 0, rate_ars, 0, monto_ars, f'Bitso {t_desc}', unique_id=actual_uid
                    ))
            except Exception as e:
                print(f"Error procesando fila en Bitso: {e}")
                continue
    except MissingColumnsError:
        raise
    except Exception as e:
        print(f"Error Bitso: {e}")
        return [], []
    return processed, raw_sample

# Backwards compatibility alias
parse_bitso_csv = process_bitso
