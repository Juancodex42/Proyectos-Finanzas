import re
import pandas as pd
try:
    from services import config_service as config_manager
except ImportError:
    import config_manager
from exceptions import MissingColumnsError

try:
    from .base_parser import (_normalize_text, parse_date, clean_decimal, find_column_fuzzy, validate_columns, is_cancelled_transaction, create_transaction, get_usd_ars_rate)
except ImportError:
    from parsers.base_parser import (_normalize_text, parse_date, clean_decimal, find_column_fuzzy, validate_columns, is_cancelled_transaction, create_transaction, get_usd_ars_rate)

from .ripio_helpers import process_api_trades, _calc_monto_ars


def process_ripio_trade(file_obj, filename):
    """
    Processes Ripio Trade / Select CSV files.
    Handles two formats:
      1. Modern Account Ledger Format: Contains 'Descripción' column, explicit deposits,
         withdrawals, buys, sells, and multi-fill executions.
      2. Legacy Paired Format: Pairs ARS and Crypto (or fiat/crypto) sharing codigo_operacion.
    """
    processed = []
    raw_sample = []
    try:
        df = None
        if str(filename).lower().endswith(('.xlsx', '.xls')):
            try:
                file_obj.seek(0)
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
        validate_columns(df, 'ripio_trade')

        col_fecha = find_column_fuzzy(df, [config_manager.get_column('ripio_trade', 'fecha'), 'fecha y hora de la operación', 'fecha y hora', 'fecha', 'date', 'created_at', 'timestamp'])
        col_monto = find_column_fuzzy(df, [config_manager.get_column('ripio_trade', 'monto'), 'monto de la operación', 'monto', 'amount', 'cantidad', 'total'])
        col_moneda = find_column_fuzzy(df, [config_manager.get_column('ripio_trade', 'moneda'), 'moneda', 'currency', 'asset', 'symbol'])
        col_cod = find_column_fuzzy(df, [config_manager.get_column('ripio_trade', 'codigo_operacion'), 'código de operación', 'codigo de operacion', 'codigo_operacion', 'order_id', 'id_operacion'])
        col_desc = find_column_fuzzy(df, ['descripción', 'descripcion', 'description', 'type', 'tipo'])
        col_id = find_column_fuzzy(df, ['identificador', 'id', 'identifier'])

        FIAT_STABLES = {'ARS', 'USD', 'USDT', 'USDC', 'DAI', 'BUSD', 'EUR', 'UXD'}
        FIAT_CURRENCIES = {'ARS', 'USD', 'EUR'}

        # FORMAT 1: Modern Ledger format with explicit "Descripción"
        if col_desc and col_desc in df.columns:
            df = df[~df.apply(is_cancelled_transaction, axis=1)].copy()
            desc_series = df[col_desc].astype(str).str.lower()
            fee_mask = desc_series.str.contains('comisi|fee|tax|gasto', na=False)
            trade_mask = desc_series.str.contains('compra|venta|buy|sell|trade|intercambio|swap', na=False) & ~fee_mask

            # Find order IDs that have trade executions so fees can be netted directly into the order
            trade_orders_set = set(df[trade_mask][col_cod].dropna().astype(str).unique()) if col_cod and col_cod in df.columns else set()

            # Process orphan crypto fees (not attached to any trade order) as Comisión Cripto
            fees_df = df[fee_mask].copy()
            for idx, row in fees_df.iterrows():
                moneda = str(row[col_moneda]).strip().upper()
                raw_monto = clean_decimal(row[col_monto])
                if abs(raw_monto) <= 1e-9 or moneda in FIAT_CURRENCIES:
                    continue
                op_id = str(row[col_cod]) if col_cod and not pd.isna(row.get(col_cod)) else str(row.get(col_id, ''))
                if op_id and op_id in trade_orders_set:
                    continue

                fecha = parse_date(str(row[col_fecha]), 'ripio_trade')
                unique_id = str(row.get(col_id, '')) or op_id
                m_ars = _calc_monto_ars(moneda, raw_monto, fecha)
                c_ars = m_ars / abs(raw_monto) if abs(raw_monto) > 0 else 0.0
                desc = str(row[col_desc]).strip()
                processed.append(create_transaction(fecha, 'Ripio Trade', 'Comisión Cripto', moneda, 0.0, abs(raw_monto), 0.0, c_ars, m_ars, f"ID: {op_id} | {desc}", unique_id=unique_id))

            # 1A. Process single-row transfers (Deposits and Withdrawals)
            non_trades = df[~trade_mask & ~fee_mask].copy()
            for idx, row in non_trades.iterrows():
                desc = str(row[col_desc]).strip()
                moneda = str(row[col_moneda]).strip().upper()
                raw_monto = clean_decimal(row[col_monto])
                if abs(raw_monto) <= 1e-9:
                    continue

                fecha = parse_date(str(row[col_fecha]), 'ripio_trade')
                op_id = str(row[col_cod]) if col_cod and not pd.isna(row.get(col_cod)) else str(row.get(col_id, ''))
                unique_id = str(row.get(col_id, '')) or op_id
                desc_lower = desc.lower()
                is_explicit_dep = any(k in desc_lower for k in ('depósito', 'deposito', 'ingreso', 'recepcion', 'recepción', 'entrada', 'abono'))
                is_explicit_out = any(k in desc_lower for k in ('retiro', 'envio', 'envío', 'salida', 'extraccion', 'extracción', 'egreso'))

                if is_explicit_out:
                    is_in, is_out = False, True
                elif is_explicit_dep:
                    is_in, is_out = True, False
                else:
                    is_in, is_out = raw_monto > 0, raw_monto < 0
                if not is_in and not is_out:
                    continue
                tipo_op = ('Ingreso Fiat' if moneda in FIAT_CURRENCIES else 'Ingreso') if is_in else ('Retiro Fiat' if moneda in FIAT_CURRENCIES else 'Retiro')
                m_compra, m_venta = (abs(raw_monto), 0.0) if is_in else (0.0, abs(raw_monto))
                m_ars = _calc_monto_ars(moneda, raw_monto, fecha)
                processed.append(create_transaction(fecha, 'Ripio Trade', tipo_op, moneda, m_compra, m_venta, 0.0, 0.0, m_ars, f"ID: {op_id} | {desc}", unique_id=unique_id))

            # 1B. Process trades grouped by col_cod (aggregating all partial fills and netting order fees)
            trades_df = df[trade_mask].copy()
            if col_cod and col_cod in trades_df.columns:
                fees_df_map = {}
                if fee_mask.any():
                    for f_cod, f_grp in df[fee_mask].groupby(col_cod):
                        fees_df_map[str(f_cod)] = f_grp

                for nombre, grupo in trades_df.groupby(col_cod):
                    f_grp = fees_df_map.get(str(nombre))
                    fee_cripto, fee_ars = 0.0, 0.0
                    if f_grp is not None and not f_grp.empty:
                        fee_cripto = abs(f_grp[f_grp[col_moneda].astype(str).str.upper() != 'ARS'][col_monto].apply(clean_decimal).sum())
                        fee_ars = abs(f_grp[f_grp[col_moneda].astype(str).str.upper() == 'ARS'][col_monto].apply(clean_decimal).sum())

                    row_ars = grupo[grupo[col_moneda].astype(str).str.upper() == 'ARS']
                    row_cripto = grupo[grupo[col_moneda].astype(str).str.upper() != 'ARS']

                    if not row_ars.empty and not row_cripto.empty:
                        total_ars = abs(row_ars[col_monto].apply(clean_decimal).sum())
                        total_cripto = abs(row_cripto[col_monto].apply(clean_decimal).sum())
                        mon_cripto = str(row_cripto.iloc[0][col_moneda]).upper()
                        fecha = parse_date(str(grupo.iloc[0][col_fecha]), 'ripio_trade')
                        first_desc = str(grupo.iloc[0][col_desc]).strip().lower()
                        is_buy = 'compra' in first_desc or clean_decimal(row_ars.iloc[0][col_monto]) < 0

                        if is_buy:
                            net_cripto = max(0.0, total_cripto - fee_cripto)
                            total_ars_cost = total_ars + fee_ars
                            cot = total_ars_cost / net_cripto if net_cripto > 0 else 0.0
                            fee_info = f" | Fee: {fee_cripto} {mon_cripto}" if fee_cripto > 0 else (f" | Fee: {fee_ars} ARS" if fee_ars > 0 else "")
                            processed.append(create_transaction(fecha, 'Ripio Trade', 'Compra', mon_cripto, net_cripto, 0.0, cot, 0.0, total_ars_cost, f"ID: {nombre} | Compra ({len(row_cripto)} fills){fee_info}", unique_id=nombre))
                        else:
                            net_ars = max(0.0, total_ars - fee_ars)
                            cot = net_ars / total_cripto if total_cripto > 0 else 0.0
                            fee_info = f" | Fee: {fee_ars} ARS" if fee_ars > 0 else (f" | Fee: {fee_cripto} {mon_cripto}" if fee_cripto > 0 else "")
                            processed.append(create_transaction(fecha, 'Ripio Trade', 'Venta', mon_cripto, 0.0, total_cripto, 0.0, cot, net_ars, f"ID: {nombre} | Venta ({len(row_cripto)} fills){fee_info}", unique_id=nombre))
                    else:
                        row_neg = grupo[grupo[col_monto].apply(clean_decimal) < 0]
                        row_pos = grupo[grupo[col_monto].apply(clean_decimal) > 0]
                        if not row_neg.empty and not row_pos.empty:
                            m_sold = str(row_neg.iloc[0][col_moneda]).upper()
                            t_sold = abs(row_neg[col_monto].apply(clean_decimal).sum())
                            m_bought = str(row_pos.iloc[0][col_moneda]).upper()
                            t_bought = abs(row_pos[col_monto].apply(clean_decimal).sum())
                            fecha = parse_date(str(grupo.iloc[0][col_fecha]), 'ripio_trade')
                            usd_rate = get_usd_ars_rate(fecha)
                            from models.transaction_models import get_quote_usd_value
                            usd_val = get_quote_usd_value(m_sold, t_sold, base_coin=m_bought, base_amount=t_bought, fecha=fecha)
                            m_ars = usd_val * usd_rate
                            cot_b = m_ars / t_bought if t_bought > 0 else 0.0
                            cot_s = m_ars / t_sold if t_sold > 0 else 0.0
                            comm = f"ID: {nombre} | [INTERCAMBIO: {m_sold}->{m_bought}]"
                            processed.append(create_transaction(fecha, 'Ripio Trade', 'Compra', m_bought, t_bought, 0.0, cot_b, 0.0, m_ars, comm, unique_id=f"{nombre}_c"))
                            processed.append(create_transaction(fecha, 'Ripio Trade', 'Venta', m_sold, 0.0, t_sold, 0.0, cot_s, m_ars, comm, unique_id=f"{nombre}_v"))
                        else:
                            for idx, (_, r) in enumerate(grupo.iterrows()):
                                t_desc = str(r[col_desc]).strip().lower()
                                t_mon = str(r[col_moneda]).strip().upper()
                                t_monto = abs(clean_decimal(r[col_monto]))
                                t_fecha = parse_date(str(r[col_fecha]), 'ripio_trade')
                                t_is_buy = 'compra' in t_desc or 'buy' in t_desc or clean_decimal(r[col_monto]) > 0
                                t_ars = _calc_monto_ars(t_mon, t_monto, t_fecha)
                                cot = t_ars / t_monto if t_monto > 0 else 0.0
                                processed.append(create_transaction(t_fecha, 'Ripio Trade', 'Compra' if t_is_buy else 'Venta', t_mon, t_monto if t_is_buy else 0.0, 0.0 if t_is_buy else t_monto, cot if t_is_buy else 0.0, 0.0 if t_is_buy else cot, t_ars, f"ID: {nombre} | {t_desc}", unique_id=f"{nombre}_{idx}"))

            return processed, raw_sample

        # FORMAT 2: Legacy Paired format without "Descripción"
        if col_cod and col_cod in df.columns:
            grupos = df.groupby(col_cod)
            for nombre, grupo in grupos:
                if any(is_cancelled_transaction(r) for _, r in grupo.iterrows()):
                    continue
                
                row_ars = grupo[grupo[col_moneda].astype(str).str.upper() == 'ARS']
                if not row_ars.empty:
                    row_quote = row_ars
                    row_cripto = grupo[grupo[col_moneda].astype(str).str.upper() != 'ARS']
                    quote_currency = 'ARS'
                else:
                    row_stables = grupo[grupo[col_moneda].astype(str).str.upper().isin(FIAT_STABLES)]
                    if not row_stables.empty:
                        row_quote = row_stables.iloc[[0]]
                        row_cripto = grupo[~grupo.index.isin(row_quote.index)]
                        quote_currency = str(row_quote.iloc[0][col_moneda]).upper()
                    else:
                        row_quote = grupo.iloc[[0]]
                        row_cripto = grupo.iloc[[1]] if len(grupo) > 1 else grupo
                        quote_currency = str(row_quote.iloc[0][col_moneda]).upper()

                if not row_quote.empty and not row_cripto.empty:
                    try:
                        m_quote = abs(row_quote[col_monto].apply(clean_decimal).sum())
                        m_cripto = abs(row_cripto[col_monto].apply(clean_decimal).sum())
                        mon_cripto = str(row_cripto.iloc[0][col_moneda]).upper()
                        fecha = parse_date(str(row_quote.iloc[0][col_fecha]), 'ripio_trade')
                        m_ars = _calc_monto_ars(quote_currency, m_quote, fecha, base_coin=mon_cripto, base_amount=m_cripto)

                        raw_q_sign = clean_decimal(row_quote.iloc[0][col_monto])
                        is_c = (raw_q_sign < 0)
                        cot = m_ars / m_cripto if m_cripto != 0 else 0
                        comm = f"[INTERCAMBIO: {mon_cripto}/{quote_currency}] ID: {nombre}" if quote_currency != 'ARS' else f"ID: {nombre}"
                        processed.append(create_transaction(
                            fecha, 'Ripio Trade', 'Compra' if is_c else 'Venta', mon_cripto,
                            m_cripto if is_c else 0, 0 if is_c else m_cripto,
                            cot if is_c else 0, 0 if is_c else cot, m_ars, comm,
                            unique_id=f"{nombre}_c" if quote_currency != 'ARS' and is_c else (f"{nombre}_v" if quote_currency != 'ARS' else nombre)
                        ))
                        if quote_currency in ('USDT', 'USDC', 'DAI', 'BUSD', 'UXD') and mon_cripto not in ('ARS', 'USD', 'EUR') and m_quote > 0:
                            cot_q = m_ars / m_quote if m_quote > 0 else 0.0
                            q_comm = f"[INTERCAMBIO: {quote_currency}->{mon_cripto}] ID: {nombre}" if is_c else f"[INTERCAMBIO: {mon_cripto}->{quote_currency}] ID: {nombre}"
                            processed.append(create_transaction(fecha, 'Ripio Trade', 'Venta' if is_c else 'Compra', quote_currency, 0 if is_c else m_quote, m_quote if is_c else 0, 0 if is_c else cot_q, cot_q if is_c else 0, m_ars, q_comm, unique_id=f"{nombre}_quote"))
                    except Exception as e:
                        print(f"Error procesando grupo de Ripio Trade ({nombre}): {e}")
                        continue
    except MissingColumnsError:
        raise
    except Exception as e:
        print(f"Error Ripio: {e}")
        return [], []
    return processed, raw_sample

def procesar_ripio_comun_txt(file_obj, filename):
    """Processes unstructured Ripio Classic / Select text reports."""
    print(f"Procesando Ripio Común (TXT): {filename}")
    processed = []
    raw_sample = []
    
    try:
        content = file_obj.read()
        if isinstance(content, bytes):
            for enc in ('utf-8-sig', 'utf-8', 'latin1', 'cp1252'):
                try:
                    text = content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                text = content.decode('utf-8', errors='ignore')
        else:
            text = content
            
        lines = [line.strip() for line in text.replace('\r', '').split('\n') if line.strip()]
        for i in range(min(10, len(lines))):
            raw_sample.append({'Line': i+1, 'Content': lines[i]})

        i = 0
        while i < len(lines):
            line = lines[i]
            date_match = re.search(r"(\d{2}/\d{2}/\d{4})(?:[,\s]+(\d{2}:\d{2}(?::\d{2})?))?", line)
            
            if date_match:
                d_str = date_match.group(1)
                t_str = date_match.group(2)
                if not t_str and (i + 1) < len(lines):
                    tm = re.search(r"\b(\d{2}:\d{2}(?::\d{2})?)\b", lines[i+1])
                    if tm:
                        t_str = tm.group(1)
                fecha_str = f"{d_str} {t_str}" if t_str else d_str
                try:
                    fecha = pd.to_datetime(fecha_str, dayfirst=True)
                except Exception as e:
                    print(f"Error regex fecha TXT robusto '{fecha_str}': {e}")
                    i += 1
                    continue
                
                p_start = max(0, i - 3)
                for p_idx in range(i - 1, p_start - 1, -1):
                    if re.search(r"\d{2}/\d{2}/\d{4}", lines[p_idx]):
                        p_start = p_idx + 1
                        break
                n_end = min(len(lines), i + 12)
                for n_idx in range(i + 1, n_end):
                    if re.search(r"\d{2}/\d{2}/\d{4}", lines[n_idx]):
                        n_end = n_idx
                        break
                next_lines = lines[i+1:n_end]
                context_str = " ".join(lines[p_start:i] + [line] + next_lines).upper()
                raw_type = context_str
                
                if any(k in context_str for k in ("CANCELAD", "RECHAZAD", "FALLID", "ERROR")):
                    i += 1
                    continue
                
                tipo_bloque, tipo_op = "MOVIMIENTO", "MOVIMIENTO"
                has_compra, has_venta = "COMPRA" in context_str, "VENTA" in context_str
                if has_compra and has_venta:
                    near_str = (line + " " + (lines[i+1] if i+1 < len(lines) else "")).upper()
                    has_compra = ("COMPRA" in near_str) and not ("VENTA" in near_str)
                    has_venta = not has_compra
                if has_compra:
                    tipo_op, tipo_bloque = "COMPRA", "Compra Cripto"
                elif has_venta:
                    tipo_op, tipo_bloque = "VENTA", "Venta Cripto"
                elif "CVU" in context_str or "TRANSFERENCIA" in context_str:
                    is_dep = "DEPÓSITO" in context_str or "RECIBIDA" in context_str
                    tipo_op, tipo_bloque = ("INGRESO FIAT", "Depósito CVU") if is_dep else ("RETIRO FIAT", "Retiro CVU")
                elif "INTERCAMBIO" in context_str or "SWAP" in context_str:
                    tipo_op, tipo_bloque = "INTERCAMBIO", "Swap Cripto"
                elif "INGRESO DE CRIPTO" in context_str:
                    tipo_op, tipo_bloque = "INGRESO CRIPTO", "Depósito Cripto"
                elif "ENVÍO DE CRIPTO" in context_str or "ENVIO DE CRIPTO" in context_str:
                    tipo_op, tipo_bloque = "RETIRO CRIPTO", "Retiro Cripto"
                elif 'COMISION' in raw_type or 'COMISIÓN' in raw_type or 'FEE' in raw_type:
                    tipo_op, tipo_bloque = "COMISION", "Comisión Cripto"
                
                montos, monedas = [], []
                for sub in next_lines:
                    if re.search(r"\d{2}/\d{2}/\d{4}", sub):
                        break
                    sub_upper = sub.upper()
                    if "SALDO" in sub_upper or "BALANCE" in sub_upper or "DISPONIBLE" in sub_upper:
                        continue
                        
                    clean_sub = sub.replace('$', '').strip()
                    for match in re.finditer(r"([\d\.,]+)\s+([A-Z]{3,5})", clean_sub):
                        val_str, coin = match.group(1), match.group(2)
                        try:
                            val = float(clean_decimal(val_str))
                        except Exception:
                            val = 0.0
                        if val > 0:
                            montos.append(val)
                            monedas.append(coin)
                
                if montos:
                    exchange = "Ripio Trade"
                    idx_crypto = next((idx for idx, m in enumerate(monedas) if m != 'ARS'), -1)
                    max_ars = max([montos[idx] for idx, m in enumerate(monedas) if m == 'ARS'], default=0.0)
                    if idx_crypto != -1:
                        m_crypto, coin_name = montos[idx_crypto], monedas[idx_crypto]
                        if tipo_op in ("COMPRA", "VENTA"):
                            cot = max_ars / m_crypto if m_crypto > 0 else 0.0
                            is_c = (tipo_op == "COMPRA")
                            processed.append(create_transaction(fecha, exchange, tipo_op.title(), coin_name, m_crypto if is_c else 0.0, 0.0 if is_c else m_crypto, cot if is_c else 0.0, 0.0 if is_c else cot, max_ars, tipo_bloque, unique_id=i))
                        elif tipo_op in ("INGRESO CRIPTO", "RETIRO CRIPTO"):
                            usd_rate = get_usd_ars_rate(fecha)
                            if max_ars > 0:
                                cot, m_ars = (max_ars / m_crypto if m_crypto > 0 else 0.0), max_ars
                            elif coin_name in ('USDT', 'USDC', 'USD'):
                                cot, m_ars = usd_rate, m_crypto * usd_rate
                            else:
                                from models.transaction_models import get_quote_usd_value
                                m_ars = get_quote_usd_value(coin_name, m_crypto, fecha=fecha) * usd_rate
                                cot = m_ars / m_crypto if m_crypto > 0 else usd_rate
                            is_ing = (tipo_op == "INGRESO CRIPTO")
                            processed.append(create_transaction(fecha, exchange, 'Ingreso Cripto' if is_ing else 'Retiro Cripto', coin_name, m_crypto if is_ing else 0.0, 0.0 if is_ing else m_crypto, cot if is_ing else 0.0, 0.0 if is_ing else cot, m_ars, tipo_bloque, unique_id=f"{i}_{'dep' if is_ing else 'ret'}"))
                        elif tipo_op in ("INGRESO FIAT", "RETIRO FIAT"):
                            is_ing = (tipo_op == "INGRESO FIAT")
                            processed.append(create_transaction(fecha, exchange, tipo_op.title(), 'ARS', 0.0, 0.0, 0.0, 0.0, max_ars if max_ars > 0 else m_crypto, tipo_bloque, unique_id=f"{i}_{'dep_fiat' if is_ing else 'ret_fiat'}"))
                        elif tipo_op == "COMISION":
                            m_ars = _calc_monto_ars(coin_name, m_crypto, fecha)
                            cot = m_ars / m_crypto if m_crypto > 0 else 0.0
                            processed.append(create_transaction(fecha, exchange, 'Comisión Cripto', coin_name, 0.0, m_crypto, 0.0, cot, m_ars, tipo_bloque, unique_id=f"{i}_fee"))
                        elif tipo_op == "INTERCAMBIO" and len(monedas) >= 2 and len(montos) >= 2:
                            usd_rate = get_usd_ars_rate(fecha)
                            from models.transaction_models import get_quote_usd_value
                            c1, c2, a1, a2 = monedas[0], monedas[1], montos[0], montos[1]
                            swap_ars = max(get_quote_usd_value(c1, a1, fecha=fecha) * usd_rate, get_quote_usd_value(c2, a2, fecha=fecha) * usd_rate)
                            cot1, cot2 = (swap_ars / a1 if a1 > 0 else 0.0), (swap_ars / a2 if a2 > 0 else 0.0)
                            comm = f"[INTERCAMBIO: {c1}->{c2}]"
                            processed.append(create_transaction(fecha, exchange, 'Venta', c1, 0.0, a1, 0.0, cot1, swap_ars, comm, unique_id=f"{i}_v"))
                            processed.append(create_transaction(fecha, exchange, 'Compra', c2, a2, 0.0, cot2, 0.0, swap_ars, comm, unique_id=f"{i}_c"))
            i += 1
    except Exception as e:
        print(f"Error parseando Ripio TXT Robust: {e}")
        return [], []
        
    return processed, raw_sample

