import os
import io
import re
import pandas as pd
from utils.exceptions import MissingColumnsError

try:
    from .base_parser import (
        _normalize_text, parse_date, clean_decimal,
        limpiar_numero_binance, is_cancelled_transaction,
        create_transaction, get_usd_ars_rate
    )
except ImportError:
    from parsers.base_parser import (
        _normalize_text, parse_date, clean_decimal,
        limpiar_numero_binance, is_cancelled_transaction,
        create_transaction, get_usd_ars_rate
    )


def find_binance_column(df, candidates):
    """Finds best matching column for Binance exports with accent and case normalization."""
    cols = [_normalize_text(c) for c in df.columns]
    cand_clean_list = [_normalize_text(c) for c in candidates]
    for cand_clean in cand_clean_list:
        for idx, col in enumerate(cols):
            if col == cand_clean:
                return df.columns[idx]
    for cand_clean in cand_clean_list:
        if cand_clean == 'id':
            continue
        for idx, col in enumerate(cols):
            if any(ign in col for ign in ('user', 'client', 'account', 'sub', 'contraparte', 'counterparty')):
                continue
            if 'fee' in col and 'fee' not in cand_clean:
                continue
            if len(cand_clean) < 4:
                if cand_clean in col.split():
                    return df.columns[idx]
                continue
            if cand_clean in col:
                return df.columns[idx]
    return None


def calculate_ars_metrics(base_asset, quote_asset, monto_compra, monto_venta, precio=0.0, fecha=None):
    """Calculates ARS valuation metrics for a Binance trade given base and quote assets."""
    usd_ars_rate = get_usd_ars_rate(fecha)
    base_asset = str(base_asset or '').upper().strip()
    quote_asset = str(quote_asset or '').upper().strip()
    if quote_asset == 'ARS':
        monto_ars = (monto_compra * precio) if monto_compra > 0 and monto_venta == 0 else (monto_venta if monto_compra > 0 else max(monto_compra, monto_venta))
    elif quote_asset in ('USD', 'USDT', 'USDC', 'FDUSD', 'BUSD', 'DAI'):
        fiat_amt = monto_venta if monto_compra > 0 and monto_venta > 0 else ((monto_compra * precio) if monto_compra > 0 and precio > 0 else max(monto_compra, monto_venta))
        monto_ars = fiat_amt * usd_ars_rate
    elif base_asset == 'ARS':
        monto_ars = monto_venta if monto_compra > 0 and monto_venta > 0 else (monto_compra if monto_venta > 0 and monto_compra > 0 else max(monto_compra, monto_venta))
    elif base_asset == 'USD':
        fiat_amt = monto_venta if monto_compra > 0 and monto_venta > 0 else max(monto_compra, monto_venta)
        monto_ars = fiat_amt * usd_ars_rate
    else:
        from models.transaction_models import get_quote_usd_value
        amt = monto_compra if monto_compra > 0 else monto_venta
        usd_val = get_quote_usd_value(base_asset, amt, fecha=fecha)
        monto_ars = usd_val * usd_ars_rate
    return monto_ars


calculate_ars_Metrics = calculate_ars_metrics


def get_binance_dataframes(file_obj, filename):
    file_obj.seek(0)
    ext = filename.lower()
    raw_dfs = []
    
    if ext.endswith('.xlsx') or ext.endswith('.xls'):
        try:
            sheets_dict = pd.read_excel(file_obj, sheet_name=None)
            if isinstance(sheets_dict, dict):
                for sheet_name, df_sheet in sheets_dict.items():
                    if df_sheet is not None and not df_sheet.empty:
                        raw_dfs.append(df_sheet)
            elif isinstance(sheets_dict, pd.DataFrame):
                raw_dfs.append(sheets_dict)
        except Exception:
            file_obj.seek(0)
            try:
                raw_dfs.append(pd.read_excel(file_obj))
            except Exception:
                pass
    else:
        for enc in ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'utf-16']:
            for sep in [None, ',', ';', '\t']:
                file_obj.seek(0)
                try:
                    kwargs = {'encoding': enc}
                    if sep is None:
                        kwargs['sep'] = None
                        kwargs['engine'] = 'python'
                    else:
                        kwargs['sep'] = sep
                    df_csv = pd.read_csv(file_obj, **kwargs)
                    if df_csv is not None and not df_csv.empty and len(df_csv.columns) > 1:
                        raw_dfs.append(df_csv)
                        break
                except Exception:
                    pass
            if raw_dfs:
                break
        if not raw_dfs:
            file_obj.seek(0)
            try:
                sheets_dict = pd.read_excel(file_obj, sheet_name=None)
                if isinstance(sheets_dict, dict):
                    raw_dfs.extend(sheets_dict.values())
                elif isinstance(sheets_dict, pd.DataFrame):
                    raw_dfs.append(sheets_dict)
            except Exception:
                pass

    final_dfs = []
    for df in raw_dfs:
        if df is None or df.empty:
            continue
        cols_str = " ".join([str(c).lower() for c in df.columns])
        is_known = any(k in cols_str for k in [
            'order', 'orden', 'fiat', 'asset', 'activo', 'side', 'executed', 'ejecutado',
            'created', 'creación', 'status', 'estado', 'tipo', 'precio', 'monto', 'cantidad',
            'convert', 'auto-invest', 'pay', 'deposit', 'depósito', 'deposito', 'withdraw',
            'withdrawal', 'retiro', 'txid', 'change'
        ])
        if is_known:
            final_dfs.append(df)
        else:
            found_skip = False
            for skip in range(1, min(26, len(df))):
                try:
                    row_vals = " ".join([str(v).lower() for v in df.iloc[skip-1].values])
                    if any(k in row_vals for k in [
                        'order', 'orden', 'pedido', 'fiat', 'asset', 'activo', 'side', 'lado',
                        'executed', 'ejecutado', 'created', 'creación', 'status', 'estado', 'tipo',
                        'precio', 'monto', 'cantidad', 'par', 'pair', 'tarifa'
                    ]):
                        raw_cols = [str(v).strip() for v in df.iloc[skip-1].values]
                        seen = {}
                        unique_cols = []
                        for idx, c in enumerate(raw_cols):
                            c_clean = c if c and c.lower() not in ('nan', 'none', '') else f"unnamed_{idx}"
                            if c_clean in seen:
                                seen[c_clean] += 1
                                unique_cols.append(f"{c_clean}_{seen[c_clean]}")
                            else:
                                seen[c_clean] = 0
                                unique_cols.append(c_clean)
                        new_df = df.iloc[skip:].copy()
                        new_df.columns = unique_cols
                        final_dfs.append(new_df)
                        found_skip = True
                        break
                except Exception:
                    pass
            if not found_skip:
                final_dfs.append(df)
                
    return final_dfs


def _process_binance_convert_or_autoinvest(df, ex_name):
    """Processes Convert, Auto-Invest and Pay transactions within Binance dataframes."""
    records = []
    # Identify Convert columns
    c_from_coin = find_binance_column(df, ['from asset', 'sell asset', 'source asset', 'moneda origen', 'from coin', 'from'])
    c_to_coin = find_binance_column(df, ['to asset', 'buy asset', 'target asset', 'moneda destino', 'to coin', 'to'])
    c_from_amt = find_binance_column(df, ['from amount', 'sell amount', 'source amount', 'monto origen', 'from qty'])
    c_to_amt = find_binance_column(df, ['to amount', 'buy amount', 'target amount', 'monto destino', 'to qty'])
    c_date = find_binance_column(df, ['date(utc)', 'date', 'created time', 'time', 'fecha', 'timestamp'])
    c_type = find_binance_column(df, ['type', 'tipo', 'operation', 'operacion'])

    c_order_id = find_binance_column(df, [
        'order id', 'order no.', 'order no', 'order number', 'id', 'trade id',
        'transaction id', 'tran id', 'n.º de orden', 'no. de orden', 'id de orden',
        'id de transacción', 'id de transaccion', 'número de orden', 'numero de orden'
    ])

    if c_from_coin and c_to_coin and (c_from_amt or c_to_amt):
        for index, row in df.iterrows():
            if is_cancelled_transaction(row):
                continue
            try:
                fecha = parse_date(row.get(c_date), 'binance_spot')
                from_c = str(row.get(c_from_coin, '')).upper().strip()
                to_c = str(row.get(c_to_coin, '')).upper().strip()
                from_a = abs(clean_decimal(row.get(c_from_amt, 0)))
                to_a = abs(clean_decimal(row.get(c_to_amt, 0)))
                if not from_c or not to_c or (from_a == 0 and to_a == 0):
                    continue

                raw_uid = str(row.get(c_order_id, '')).strip() if c_order_id else ''
                conv_uid = raw_uid if raw_uid and raw_uid.lower() not in ('nan', 'none', '') else ""
                uid_conv = conv_uid if conv_uid else None
                uid_v = f"{conv_uid}_v" if conv_uid else None
                uid_c = f"{conv_uid}_c" if conv_uid else None

                usd_ars_rate = get_usd_ars_rate(fecha)
                if from_c == 'ARS':
                    cot = from_a / to_a if to_a > 0 else 0.0
                    records.append(create_transaction(
                        fecha, ex_name, 'Compra', to_c,
                        to_a, 0, cot, 0, from_a, 'Binance Convert', unique_id=uid_conv
                    ))
                elif to_c == 'ARS':
                    cot = to_a / from_a if from_a > 0 else 0.0
                    records.append(create_transaction(
                        fecha, ex_name, 'Venta', from_c,
                        0, from_a, 0, cot, to_a, 'Binance Convert', unique_id=uid_conv
                    ))
                else:
                    from models.transaction_models import get_quote_usd_value
                    if from_c in ('USDT', 'USDC', 'DAI', 'BUSD', 'USD'):
                        usd_val = from_a
                    elif to_c in ('USDT', 'USDC', 'DAI', 'BUSD', 'USD'):
                        usd_val = to_a
                    else:
                        usd_val = get_quote_usd_value(from_c, from_a, base_coin=to_c, base_amount=to_a, fecha=fecha)
                    m_ars = usd_val * usd_ars_rate
                    comment = f"[INTERCAMBIO: {from_c}->{to_c}]"
                    cot_v = m_ars / from_a if from_a > 0 else 0.0
                    records.append(create_transaction(
                        fecha, ex_name, 'Venta', from_c,
                        0, from_a, 0, cot_v, m_ars, comment, unique_id=uid_v
                    ))
                    cot_c = m_ars / to_a if to_a > 0 else 0.0
                    records.append(create_transaction(
                        fecha, ex_name, 'Compra', to_c,
                        to_a, 0, cot_c, 0, m_ars, comment, unique_id=uid_c
                    ))
            except Exception:
                continue
    return records


def _process_binance_deposits_withdrawals(df, ex_name='Binance'):
    """
    Processes Binance Deposit and Withdrawal CSVs and account statements.
    Returns list of transaction dicts or empty list if df is not deposit/withdrawal.
    """
    records = []
    op_col = find_binance_column(df, ['operation', 'operacion', 'operación', 'type', 'tipo', 'transaction type'])
    dep_col = find_binance_column(df, ['deposit', 'depósito', 'deposito'])
    with_col = find_binance_column(df, ['withdraw', 'withdrawal', 'retiro'])
    date_col = find_binance_column(df, ['date(utc)', 'utc_time', 'time(utc)', 'date', 'time', 'fecha(utc)', 'fecha', 'hora'])
    coin_col = find_binance_column(df, ['coin', 'asset', 'crypto', 'cripto', 'moneda', 'activo'])
    amt_col = find_binance_column(df, ['amount', 'change', 'cantidad', 'monto', 'qty'])
    txid_col = find_binance_column(df, ['txid', 'tx_id', 'transaction id', 'tran id', 'id', 'address', 'dirección', 'direccion'])
    status_col = find_binance_column(df, ['status', 'estado', 'state'])
    fee_col = find_binance_column(df, ['transaction fee', 'fee', 'comisión', 'comision'])

    cols_str = " ".join([str(c).lower() for c in df.columns])
    has_trade_markers = (find_binance_column(df, ['pair', 'par', 'market', 'mercado']) is not None) and (find_binance_column(df, ['price', 'precio']) is not None)
    has_p2p_markers = (find_binance_column(df, ['tipo de fiat', 'fiat type', 'precio total', 'total price', 'número de pedido', 'numero de pedido', 'tipo de orden']) is not None) and (find_binance_column(df, ['fiat', 'tipo de fiat', 'precio total', 'monto total']) is not None)
    if has_trade_markers or has_p2p_markers:
        return []
    is_dep_with_file = any(k in cols_str for k in ['deposit', 'withdraw', 'txid', 'change']) or (op_col is not None and (amt_col is not None or coin_col is not None))
    
    if not (date_col and coin_col and (amt_col or op_col) and is_dep_with_file):
        return []

    for idx, row in df.iterrows():
        if is_cancelled_transaction(row):
            continue
        try:
            status_val = str(row.get(status_col, '')).lower().strip() if status_col else ''
            if status_val in ('cancelled', 'failed', 'rejected', 'cancelado', 'fallido', 'rechazado'):
                continue
                
            raw_date = row.get(date_col)
            fecha = parse_date(raw_date, 'binance_spot')
            coin = str(row.get(coin_col, '')).upper().strip()
            if not coin or coin in ('NAN', 'NONE', 'NULL'):
                continue
                
            raw_amt = clean_decimal(row.get(amt_col, 0)) if amt_col else 0.0
            amt = abs(raw_amt)
            if amt == 0:
                continue
                
            raw_txid = str(row.get(txid_col, '')).strip() if txid_col else ''
            txid = raw_txid if raw_txid and raw_txid.lower() not in ('nan', 'none', 'null', '') else None
            
            raw_op = str(row.get(op_col, '')).strip() if op_col else ''
            op_lower = raw_op.lower()
            
            is_deposit = False
            is_withdrawal = False
            
            if op_lower:
                if any(k in op_lower for k in ['deposit', 'depósito', 'deposito', 'ingreso']):
                    is_deposit = True
                elif any(k in op_lower for k in ['withdraw', 'retiro', 'egreso']):
                    is_withdrawal = True
                elif raw_amt > 0:
                    is_deposit = True
                elif raw_amt < 0:
                    is_withdrawal = True
            elif dep_col and not with_col:
                is_deposit = True
            elif with_col and not dep_col:
                is_withdrawal = True
            elif 'deposit' in cols_str:
                is_deposit = True
            elif 'withdraw' in cols_str:
                is_withdrawal = True
            elif raw_amt > 0:
                is_deposit = True
            elif raw_amt < 0:
                is_withdrawal = True
                
            if not is_deposit and not is_withdrawal:
                continue
                
            usd_ars_rate = get_usd_ars_rate(fecha)
            from models.transaction_models import get_quote_usd_value
            usd_val = get_quote_usd_value(coin, amt, fecha=fecha)
            m_ars = usd_val * usd_ars_rate
            c_ars = m_ars / amt if amt > 0 else usd_ars_rate
            
            comment = f"Binance {'Deposit' if is_deposit else 'Withdrawal'}"
            if raw_op:
                comment += f": {raw_op}"
            if txid:
                comment += f" | TxID: {txid}"
                
            if is_deposit:
                records.append(create_transaction(
                    fecha, ex_name, 'Ingreso Cripto', coin,
                    amt, 0, 0.0, 0, m_ars, comment, unique_id=txid
                ))
            else:
                records.append(create_transaction(
                    fecha, ex_name, 'Retiro Cripto', coin,
                    0, amt, 0, c_ars, m_ars, comment, unique_id=txid
                ))
                
            if fee_col:
                raw_fee = clean_decimal(row.get(fee_col, 0))
                if raw_fee > 0:
                    fee_usd = get_quote_usd_value(coin, raw_fee, fecha=fecha)
                    fee_ars = fee_usd * usd_ars_rate
                    records.append(create_transaction(
                        fecha, ex_name, 'Comisión Cripto', coin,
                        0, raw_fee, 0, c_ars, fee_ars, f"Binance Fee | {comment}", unique_id=f"{txid}_fee" if txid else None
                    ))
        except Exception:
            continue
            
    return records
