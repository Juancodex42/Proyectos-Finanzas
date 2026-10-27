"""
Motor de costeo FIFO y recomputación de base imponible en SQLite.
Aplica colas de inventario y desempate determinista según normativa argentina.
Referencia de diseño: docs/especificacion_fifo_prioridades.md
"""

import collections
from datetime import datetime
import pandas as pd
import sqlite3

def parse_date_robust(val):
    if pd.isna(val) or val is None:
        return pd.NaT
    if isinstance(val, (datetime, pd.Timestamp)):
        ts = pd.Timestamp(val)
        if ts.tzinfo is not None:
            ts = ts.tz_convert('UTC').tz_localize(None)
        return ts
    s = str(val).strip()
    if not s or s.lower() in ('nan', 'nat', 'none'):
        return pd.NaT
    if s.isdigit():
        if len(s) == 13:
            ts = pd.to_datetime(int(s), unit='ms', errors='coerce')
        elif len(s) == 10:
            ts = pd.to_datetime(int(s), unit='s', errors='coerce')
        else:
            ts = pd.NaT
        if pd.notna(ts) and getattr(ts, 'tzinfo', None) is not None:
            ts = ts.tz_convert('UTC').tz_localize(None)
        return ts

    dayfirst = False if (len(s) >= 4 and s[:4].isdigit()) else True
    try:
        ts = pd.to_datetime(s, dayfirst=dayfirst, errors='coerce', utc=True)
        if pd.notna(ts):
            return ts.tz_convert('UTC').tz_localize(None)
    except Exception:
        pass
    try:
        ts = pd.to_datetime(s, dayfirst=not dayfirst, errors='coerce', utc=True)
        if pd.notna(ts):
            return ts.tz_convert('UTC').tz_localize(None)
    except Exception:
        pass
    return pd.NaT

def parse_dates_series_robust(series):
    if series.empty:
        return pd.Series([], dtype='datetime64[ns]')
    s = series.fillna('').astype(str).str.strip()
    is_iso = s.str.match(r'^\d{4}[-/]')
    is_lat = s.str.match(r'^\d{1,2}/\d{1,2}/\d{4}')
    res = pd.Series(pd.NaT, index=series.index, dtype='datetime64[ns]')
    if is_iso.any():
        res[is_iso] = pd.to_datetime(s[is_iso], errors='coerce', utc=True).dt.tz_convert('UTC').dt.tz_localize(None)
    if is_lat.any():
        res[is_lat] = pd.to_datetime(s[is_lat], errors='coerce', dayfirst=True, utc=True).dt.tz_convert('UTC').dt.tz_localize(None)
    unparsed = res.isna() & (s != '') & (~s.str.lower().isin(('nan', 'nat', 'none')))
    if unparsed.any():
        res[unparsed] = s[unparsed].apply(parse_date_robust)
    return res


def recalculate_fifo_costs_db():
    """
    [Decisión de diseño]: Motor FIFO de Costo Base Contable.
    Ejecuta el recálculo cronológico agrupando por criptomoneda a nivel global de la cartera.
    - Los depósitos/ingresos sin cotización ARS explícita se encolan con costo $0.0 hasta que 
      el usuario cargue el extracto de origen o el escáner de gaps (check_history_gaps) detecte la compra faltante.
    - Las ventas que exceden el saldo previo quedan registradas para subsanación mediante el sistema de conciliación.
    - Las transacciones con is_certified = 1 quedan blindadas e inmutables.
    """
    try:
        from db.connection import get_connection
    except ImportError:
        from db_manager import get_connection  # type: ignore
    
    conn = get_connection()
    try:
        # 1. Fetch all transactions sorted chronologically (COMPRA before VENTA on same date)
        query = """
            SELECT tx_hash, fecha, exchange, tipo_operacion, moneda, 
                   monto_compra_cripto, monto_venta_cripto, 
                   cotizacion_compra, cotizacion_venta, monto_ars, comentarios, is_certified 
            FROM transactions 
            ORDER BY fecha ASC, 
                     CASE 
                        WHEN (LOWER(tipo_operacion) LIKE '%compra%' OR LOWER(tipo_operacion) LIKE '%buy%') AND monto_compra_cripto > 0 THEN 1
                        WHEN (LOWER(tipo_operacion) LIKE '%retiro%' OR LOWER(tipo_operacion) LIKE '%withdraw%' OR LOWER(tipo_operacion) LIKE '%envio%' OR LOWER(tipo_operacion) LIKE '%egreso%') THEN 2
                        WHEN (LOWER(tipo_operacion) LIKE '%ingreso%' OR LOWER(tipo_operacion) LIKE '%deposit%' OR LOWER(tipo_operacion) LIKE '%recep%') THEN 3
                        ELSE 4 
                     END ASC,
                     tx_hash ASC
        """
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            return {"success": True, "message": "No transactions found.", "updated_count": 0}
            
        from models.transaction_models import canonicalize_ticker, get_canonical_exchange_root, extract_transfer_txid, CRYPTO_DUST_EPSILON
        from services.gap_service import _egress_stale_withdrawals
        from domain.operations import get_operation_priority

        def _get_op_priority(row):
            return get_operation_priority(
                row.get('tipo_operacion'),
                row.get('monto_compra_cripto'),
                row.get('monto_venta_cripto')
            )

        # Group transactions by canonical coin (moneda) and run FIFO logic for each coin
        # Note: We skip ARS and fiat currencies.
        df['coin_clean'] = df['moneda'].apply(canonicalize_ticker)
        df['dt'] = parse_dates_series_robust(df['fecha'])
        df['inflow_priority'] = df.apply(_get_op_priority, axis=1)
        coins = df['coin_clean'].unique()
        
        updates = []  # list of tuples (cotizacion_compra, audit_flag, tx_hash) to update in DB

        for coin in coins:
            if not coin or coin in ('ARS', 'USD', 'NONE', 'EUR'):
                continue
                
            coin_df = df[df['coin_clean'] == coin]
            coin_sorted = coin_df.sort_values(['dt', 'inflow_priority', 'tx_hash'])
            
            # Queue to hold purchase lots (FIFO)
            buy_queue = collections.deque()
            transfer_out_pool = collections.deque()
            
            for row in coin_sorted.itertuples(index=False):
                tx_hash = row.tx_hash
                op_type = str(row.tipo_operacion).upper().strip()
                m_compra = float(row.monto_compra_cripto or 0.0)
                m_venta = float(row.monto_venta_cripto or 0.0)
                cot_compra = float(row.cotizacion_compra or 0.0)
                m_ars = float(row.monto_ars or 0.0)
                ex = str(row.exchange)
                coment = str(getattr(row, 'comentarios', '') or '').lower()
                is_cert = 1 if getattr(row, 'is_certified', 0) in (1, '1', True) else 0
                r_dt = row.dt
                
                from models.operational_models import OPERATIONAL_NON_TAXABLE_TYPES
                op_non_taxable = {t.upper().strip() for t in OPERATIONAL_NON_TAXABLE_TYPES}
                is_non_taxable_op = (op_type in op_non_taxable) or any(t in op_type for t in op_non_taxable)

                is_fee = any(k in op_type for k in ("COMISION", "COMISIÓN", "FEE", "TAX", "GASTO")) and not is_non_taxable_op
                is_transfer_out = any(k in op_type for k in ("RETIRO", "ENVIO", "ENVÍO", "WITHDRAW", "TRANSFER", "SEND", "EGRESO", "SALIDA", "EXTRACCION", "EXTRACCIÓN")) and m_venta > 0 and not is_fee
                is_deposit_inflow = any(k in op_type for k in ("INGRESO", "DEPOSITO", "DEPÓSITO", "DEPOSIT", "RECEIVE", "RECEPCION", "RECEPCIÓN", "INCOMING", "ENTRADA", "ABONO")) and not any(k in op_type for k in ("COMPRA", "BUY")) and m_compra > 0 and not is_fee
                is_buy = (any(k in op_type for k in ("COMPRA", "INGRESO", "DEPOSITO", "DEPÓSITO", "BUY", "DEPOSIT", "RECEIVE", "RECEPCION", "RECEPCIÓN", "ENTRADA", "ABONO")) or (m_compra > 0 and m_venta == 0)) and not is_fee
                is_sell = (any(k in op_type for k in ("VENTA", "SELL", "CONSUMO", "PAGO", "PAYMENT")) or (m_venta > 0 and m_compra == 0)) and not is_transfer_out and not is_fee and not is_non_taxable_op

                # Egress stale orphan withdrawals (> 30 days without deposit match) so they consume stock
                if pd.notna(r_dt):
                    _egress_stale_withdrawals(transfer_out_pool, buy_queue, r_dt, max_days=30)

                if is_transfer_out:
                    w_txid = extract_transfer_txid(coment)
                    transfer_out_pool.append({
                        "fecha": row.fecha,
                        "dt": r_dt,
                        "qty_remaining": m_venta,
                        "exchange": ex,
                        "txid": w_txid,
                        "comentarios": coment,
                        "tipo_operacion": getattr(row, 'tipo_operacion', ''),
                        "tipo": op_type
                    })

                # Inflow processing (Buy / Deposit)
                if is_buy and m_compra > 0:
                    qty_to_enqueue = m_compra
                    # If this is a deposit/transfer in, match against pending withdrawals:
                    # Level 1: Match by identical blockchain TXID across different exchanges
                    # Level 2: Strict <= 48h chronological window and network fee tolerance across different exchanges
                    if is_deposit_inflow and transfer_out_pool:
                        d_txid = extract_transfer_txid(coment)
                        matched_idx = -1
                        ex_root = get_canonical_exchange_root(ex)
                        if d_txid:
                            for idx, t_out in enumerate(transfer_out_pool):
                                t_out_root = get_canonical_exchange_root(t_out.get('exchange'))
                                if t_out_root != ex_root and t_out.get('txid') and t_out['txid'] == d_txid and t_out['qty_remaining'] > CRYPTO_DUST_EPSILON:
                                    matched_idx = idx
                                    break
                        if matched_idx == -1 and pd.notna(r_dt):
                            for idx, t_out in enumerate(transfer_out_pool):
                                t_out_root = get_canonical_exchange_root(t_out.get('exchange'))
                                if t_out_root == ex_root:
                                    continue
                                w_dt = t_out.get('dt')
                                if pd.isna(w_dt) or t_out['qty_remaining'] <= CRYPTO_DUST_EPSILON:
                                    continue
                                if (r_dt >= w_dt - pd.Timedelta(hours=24)) and (r_dt <= w_dt + pd.Timedelta(hours=72)):
                                    diff = abs(t_out['qty_remaining'] - qty_to_enqueue)
                                    is_stable = coin in ('USDT', 'USDC', 'DAI', 'BUSD', 'FDUSD', 'U')
                                    if (diff / max(t_out['qty_remaining'], 0.01) <= 0.05) or (is_stable and diff <= 5.0) or (diff <= CRYPTO_DUST_EPSILON):
                                        matched_idx = idx
                                        break
                        if matched_idx != -1:
                            t_out = transfer_out_pool[matched_idx]
                            out_remaining = t_out['qty_remaining']
                            matched_transfer = min(qty_to_enqueue, out_remaining)
                            t_out['qty_remaining'] -= matched_transfer
                            qty_to_enqueue -= matched_transfer

                            # Network fee difference: when out_qty > in_qty (e.g. sent 100 USDT, received 99 USDT),
                            # the network fee difference consumes stock from buy_queue
                            fee_diff = out_remaining - matched_transfer
                            if 0.0 < fee_diff <= 5.0:
                                t_out['qty_remaining'] = 0.0
                                rem_net_fee = fee_diff
                                while rem_net_fee > CRYPTO_DUST_EPSILON and buy_queue:
                                    b_lot = buy_queue[0]
                                    fee_cut = min(rem_net_fee, b_lot['qty_remaining'])
                                    b_lot['qty_remaining'] -= fee_cut
                                    rem_net_fee -= fee_cut
                                    if b_lot['qty_remaining'] <= CRYPTO_DUST_EPSILON:
                                        buy_queue.popleft()
                            transfer_out_pool = collections.deque([t for t in transfer_out_pool if t.get('qty_remaining', 0.0) > CRYPTO_DUST_EPSILON])

                    if qty_to_enqueue > CRYPTO_DUST_EPSILON:
                        # Determine unit price in ARS for this buy
                        if cot_compra > 0:
                            unit_price_ars = cot_compra
                        elif not is_deposit_inflow and m_compra > 0 and m_ars > 0:
                            unit_price_ars = m_ars / m_compra
                        else:
                            unit_price_ars = 0.0
                            
                        buy_queue.append({
                            "fecha": row.fecha,
                            "dt": r_dt,
                            "qty_remaining": qty_to_enqueue,
                            "price_ars": unit_price_ars,
                            "exchange": ex
                        })
                    
                if is_sell and m_venta > 0:
                    # Match this sale against the FIFO queue, distinguishing valued vs unvalued ($0.0) lots
                    total_cost_ars = 0.0
                    valued_qty_used = 0.0
                    unvalued_qty_used = 0.0
                    remaining_to_match = m_venta
                    
                    while remaining_to_match > CRYPTO_DUST_EPSILON and buy_queue:
                        oldest_buy = buy_queue[0]
                        if oldest_buy['qty_remaining'] <= remaining_to_match + CRYPTO_DUST_EPSILON:
                            qty_used = oldest_buy['qty_remaining']
                            buy_queue.popleft()
                        else:
                            qty_used = remaining_to_match
                            oldest_buy['qty_remaining'] -= qty_used
                        remaining_to_match = max(0.0, remaining_to_match - qty_used)
                        if oldest_buy['price_ars'] > 0.0:
                            total_cost_ars += qty_used * oldest_buy['price_ars']
                            valued_qty_used += qty_used
                        else:
                            unvalued_qty_used += qty_used
                            
                    # Handle unmatched and unvalued amounts (Stock Depletion / Gaps / $0 lots)
                    uncovered_qty = max(0.0, remaining_to_match) + unvalued_qty_used
                    audit_flag = 1 if uncovered_qty > 1e-6 else 0

                    if is_cert == 1 and cot_compra > 0:
                        effective_buy_price = cot_compra
                    else:
                        effective_buy_price = (total_cost_ars / valued_qty_used) if valued_qty_used > CRYPTO_DUST_EPSILON else 0.0
                    effective_buy_price = round(effective_buy_price, 8)
                    
                    updates.append((effective_buy_price, audit_flag, round(uncovered_qty, 8), tx_hash))

                if is_fee and m_venta > 0:
                    fee_cost_ars = 0.0
                    rem_fee = m_venta
                    while rem_fee > 0 and buy_queue:
                        buy_lot = buy_queue[0]
                        matched_qty = min(rem_fee, buy_lot['qty_remaining'])
                        fee_cost_ars += matched_qty * buy_lot['price_ars']
                        buy_lot['qty_remaining'] -= matched_qty
                        rem_fee -= matched_qty
                        if buy_lot['qty_remaining'] <= CRYPTO_DUST_EPSILON:
                            buy_queue.popleft()
                    eff_fee_price = fee_cost_ars / m_venta if m_venta > 0 else 0.0
                    updates.append((round(eff_fee_price, 8), 0, 0.0, tx_hash))


                    
        # 2. Write updates to DB (Strictly preserves CPA certified transactions)
        if updates:
            c = conn.cursor()
            c.executemany("""
                UPDATE transactions 
                SET cotizacion_compra = ?, requires_cost_audit = ?, monto_descubierto = ?
                WHERE tx_hash = ? AND (is_certified IS NULL OR is_certified = 0)
            """, updates)
            conn.commit()
            return {"success": True, "message": "Successfully updated Venta transactions with FIFO cost.", "updated_count": len(updates)}
        else:
            return {"success": True, "message": "No Venta transactions to update.", "updated_count": 0}
            
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"Error recalculating FIFO costs: {e}")
        return {"success": False, "error": str(e), "updated_count": 0}
    finally:
        conn.close()
