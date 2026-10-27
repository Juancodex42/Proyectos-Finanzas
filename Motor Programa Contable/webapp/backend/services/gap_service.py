"""
Detección de brechas históricas de inventario y análisis de liquidez.
Identifica descubiertos por exchange y globales sin falsos positivos.
Referencia de diseño: docs/especificacion_fifo_prioridades.md
"""

import re
from datetime import datetime, timedelta
import collections
import logging
import pandas as pd
from db.connection import get_connection
from models.transaction_models import canonicalize_ticker, get_canonical_exchange_root, extract_transfer_txid, CRYPTO_DUST_EPSILON

logger = logging.getLogger(__name__)

def _parse_dt_safe(val):
    if not val or pd.isna(val):
        return pd.NaT
    s = str(val).strip()
    if re.match(r'^\d{4}[-/]', s):
        return pd.to_datetime(s, errors='coerce', dayfirst=False)
    return pd.to_datetime(s, errors='coerce', dayfirst=True)

def _parse_fechas_series(s_series):
    if s_series.empty:
        return pd.Series([], dtype='datetime64[ns]')
    s = s_series.fillna('').astype(str).str.strip()
    is_iso = s.str.match(r'^\d{4}[-/]')
    dt_res = pd.Series(pd.NaT, index=s_series.index, dtype='datetime64[ns]')
    if is_iso.any():
        dt_res[is_iso] = pd.to_datetime(s[is_iso], errors='coerce', dayfirst=False)
    if (~is_iso).any():
        dt_res[~is_iso] = pd.to_datetime(s[~is_iso], errors='coerce', dayfirst=True)
    return dt_res


# Re-export enrichment and interval grouping functions from the dedicated enrichment service
from services.gap_enrichment_service import (
    enrich_gaps_with_clues,
    group_gaps_into_root_intervals,
    _generate_recommended_action,
)

__all__ = [
    "check_history_gaps",
    "check_for_gaps_in_batches",
    "enrich_gaps_with_clues",
    "group_gaps_into_root_intervals",
    "_generate_recommended_action",
]


def _egress_stale_withdrawals(transfer_out_pool, buy_queue, ref_dt, max_days=30):
    """
    Egresses stale orphan withdrawals (> max_days without deposit match) so they consume stock
    rather than floating indefinitely into subsequent fiscal years.
    First consumes lots from the withdrawal exchange, then consumes from head of queue.
    Cold storage / self-custody withdrawals are preserved in transfer_out_pool so subsequent
    re-deposits match against them and do not duplicate purchases in buy_queue.
    """
    if not transfer_out_pool or pd.isna(ref_dt):
        return

    retained_pool = collections.deque()
    while transfer_out_pool:
        stale_w = transfer_out_pool.popleft()
        w_dt = stale_w.get('dt')
        if pd.isna(w_dt):
            continue

        stale_coment = str(stale_w.get('comentarios', '')).lower()
        stale_ex = str(stale_w.get('exchange', '')).lower()
        stale_tipo = str(stale_w.get('tipo', '') or stale_w.get('tipo_operacion', '')).lower()
        if any(k in stale_coment or k in stale_ex or k in stale_tipo for k in (
            'cold', 'fria', 'fría', 'ledger', 'trezor', 'hardware', 'personal',
            'custodia', 'self-custody', 'autocustodia', 'metamask', 'trust wallet', 'exodus',
            'safepal', 'tangem', 'bitbox', 'keepkey', 'phantom', 'rabby'
        )):
            retained_pool.append(stale_w)
            continue

        if (ref_dt - w_dt).days <= max_days:
            retained_pool.append(stale_w)
            continue

        stale_qty = stale_w.get('qty_remaining', 0.0)
        if stale_qty > CRYPTO_DUST_EPSILON:
            to_consume = stale_qty
            stale_root = get_canonical_exchange_root(stale_w.get('exchange'))
            for b_lot in list(buy_queue):
                lot_root = get_canonical_exchange_root(b_lot.get('exchange'))
                if lot_root == stale_root and b_lot['qty_remaining'] > CRYPTO_DUST_EPSILON:
                    c_qty = min(to_consume, b_lot['qty_remaining'])
                    b_lot['qty_remaining'] -= c_qty
                    to_consume -= c_qty
                    if to_consume <= CRYPTO_DUST_EPSILON:
                        break
            if to_consume > CRYPTO_DUST_EPSILON:
                for b_lot in list(buy_queue):
                    lot_root = get_canonical_exchange_root(b_lot.get('exchange'))
                    if lot_root != stale_root and b_lot['qty_remaining'] > CRYPTO_DUST_EPSILON:
                        c_qty = min(to_consume, b_lot['qty_remaining'])
                        b_lot['qty_remaining'] -= c_qty
                        to_consume -= c_qty
                        if to_consume <= CRYPTO_DUST_EPSILON:
                            break
            while buy_queue and buy_queue[0]['qty_remaining'] <= CRYPTO_DUST_EPSILON:
                buy_queue.popleft()

    transfer_out_pool.extend(retained_pool)



def check_history_gaps(exchanges=None, date_start=None, date_end=None, mode='global', year=None):
    """
    Analyzes the chronological sequence of transactions to find dates where 
    the cumulative balance of any coin goes negative, indicating missing purchase history.
    
    Modes:
    - 'global' (default): Groups by coin across the entire unified portfolio (standard AFIP criteria).
                Transfers/withdrawals between user accounts do not count as disposals;
                only actual sales/exits consume the global purchase balance.
    - 'exchange': Groups by (exchange_root, coin). Strict per-exchange accounting.
    - 'year': Isolates a specific fiscal year, cutting off uncertified phantom surpluses
              from previous years and auditing the year on its own merits.
    """
    if year:
        date_start = f"{year}-01-01 00:00:00"
        date_end = f"{year}-12-31 23:59:59"

    conn = get_connection()
    query = (
        "SELECT tx_hash, fecha, exchange, moneda, tipo_operacion, monto_compra_cripto, "
        "monto_venta_cripto, comentarios, is_certified "
        "FROM transactions "
        "WHERE UPPER(TRIM(moneda)) NOT IN ('ARS', 'USD', 'EUR', 'NONE', '')"
    )
    params = []
    
    if exchanges and isinstance(exchanges, str):
        exchanges = [exchanges]

    if exchanges and isinstance(exchanges, list) and len(exchanges) > 0 and mode != 'global':
        from services.transactions_service import expand_exchange_names
        expanded_ex = expand_exchange_names(exchanges)
        placeholders = ','.join(['?'] * len(expanded_ex))
        query += f" AND exchange IN ({placeholders})"
        params.extend(expanded_ex)
        
    # Prioritize buys/deposits before sales on same timestamp to avoid intra-day false gaps
    query += """
        ORDER BY fecha ASC, 
                 CASE 
                    WHEN (LOWER(tipo_operacion) LIKE '%compra%' OR LOWER(tipo_operacion) LIKE '%buy%') AND monto_compra_cripto > 0 THEN 1
                    WHEN (LOWER(tipo_operacion) LIKE '%retiro%' OR LOWER(tipo_operacion) LIKE '%withdraw%' OR LOWER(tipo_operacion) LIKE '%envio%' OR LOWER(tipo_operacion) LIKE '%egreso%') THEN 2
                    WHEN (LOWER(tipo_operacion) LIKE '%ingreso%' OR LOWER(tipo_operacion) LIKE '%deposit%' OR LOWER(tipo_operacion) LIKE '%recep%') THEN 3
                    ELSE 4 
                 END ASC,
                 tx_hash ASC
    """
    
    df = pd.DataFrame()
    certified_ranges = []
    try:
        try:
            df = pd.read_sql_query(query, conn, params=params)
        except Exception as e:
            logger.critical(f"Critical error fetching transactions for gap check: {e}")
            raise RuntimeError(f"Database error during gap inspection: {e}") from e

        try:
            c_cursor = conn.cursor()
            c_cursor.execute("SELECT start_date, end_date FROM certifications WHERE certified_buys_ars > 0 OR reconciliation_status = 'MATCH'")
            for s_date, e_date in c_cursor.fetchall():
                if s_date and e_date:
                    s_dt = _parse_dt_safe(s_date)
                    e_dt = _parse_dt_safe(e_date)
                    if pd.notna(s_dt) and pd.notna(e_dt):
                        certified_ranges.append((s_dt, e_dt))
        except Exception as e:
            logger.warning(f"Notice: Certifications check in gaps engine: {e}")
    finally:
        conn.close()
        
    if df.empty:
        return []

    df['dt'] = _parse_fechas_series(df['fecha'])
    if year:
        cutoff_dt = pd.Timestamp(f"{year}-12-31 23:59:59")
        df = df[df['dt'] <= cutoff_dt].copy()
    elif date_end:
        cutoff_dt = _parse_dt_safe(str(date_end)[:10] + " 23:59:59")
        if pd.notna(cutoff_dt):
            df = df[df['dt'] <= cutoff_dt].copy()
    if df.empty:
        return []

    gaps = []
    df['coin_clean'] = df['moneda'].apply(canonicalize_ticker)
    
    if mode == 'global':
        grouped = df.groupby('coin_clean')
    else:
        df['exchange_root'] = df['exchange'].apply(get_canonical_exchange_root)
        grouped = df.groupby(['exchange_root', 'coin_clean'])
    
    dt_start_parsed = _parse_dt_safe(date_start) if date_start else None
    if date_end:
        d_end_s = str(date_end)
        if len(d_end_s) == 10:
            d_end_s += " 23:59:59"
        dt_end_parsed = _parse_dt_safe(d_end_s)
    else:
        dt_end_parsed = None

    from domain.operations import get_operation_priority

    def _get_gap_op_priority(row):
        return get_operation_priority(
            row.get('tipo_operacion'),
            row.get('monto_compra_cripto'),
            row.get('monto_venta_cripto')
        )

    for key, group in grouped:
        buy_queue = collections.deque()
        transfer_out_pool = collections.deque()
        uncovered_deficit = 0.0
        last_deficit_dt = None
        exchange_deficits = collections.defaultdict(float)
        audit_boundary_crossed = False
        current_year = None
        coin = key if mode == 'global' else key[1]
        group = group.copy()
        group['inflow_priority'] = group.apply(_get_gap_op_priority, axis=1)
        group['dt'] = _parse_fechas_series(group['fecha'])
        group_sorted = group.sort_values(['dt', 'inflow_priority', 'tx_hash'])
        
        for row in group_sorted.itertuples(index=False):
            r_dt = row.dt
            r_fecha = str(row.fecha)

            # Bounded deficit drag across fiscal years (only isolate when mode == 'year')
            if pd.notna(r_dt):
                tx_year = r_dt.year
                if mode == 'year' and current_year is not None and tx_year != current_year:
                    uncovered_deficit = 0.0
                    last_deficit_dt = None
                    exchange_deficits.clear()
                current_year = tx_year

            # Reset deficit across genuinely certified ranges using timestamp comparison or is_certified tag
            row_is_cert = getattr(row, 'is_certified', 0) in (1, '1', True)
            is_certified_tx = row_is_cert or (any(s_dt <= r_dt <= e_dt for s_dt, e_dt in certified_ranges) if pd.notna(r_dt) else False)
            if is_certified_tx:
                uncovered_deficit = 0.0
                last_deficit_dt = None
                exchange_deficits.clear()

            # Isolate opening fiscal year boundary using timestamp comparison
            if dt_start_parsed is not None and not audit_boundary_crossed and pd.notna(r_dt):
                if r_dt >= dt_start_parsed:
                    uncovered_deficit = 0.0
                    last_deficit_dt = None
                    exchange_deficits.clear()
                    audit_boundary_crossed = True

            tipo = str(row.tipo_operacion).lower()
            m_compra = float(row.monto_compra_cripto or 0.0)
            m_venta = float(row.monto_venta_cripto or 0.0)
            ex = str(row.exchange)
            coment = str(getattr(row, 'comentarios', '') or '').lower()
            
            is_fee = any(k in tipo for k in ('comision', 'comisión', 'fee', 'tax', 'gasto'))
            is_transfer_out = any(k in tipo for k in ('retiro', 'envio', 'envío', 'withdraw', 'transfer', 'send', 'egreso', 'salida', 'extraccion', 'extracción')) and m_venta > 0 and not is_fee
            is_deposit_inflow = any(k in tipo for k in ('ingreso', 'deposito', 'depósito', 'deposit', 'receive', 'recepcion', 'recepción', 'incoming', 'entrada', 'abono')) and not any(k in tipo for k in ('compra', 'buy')) and m_compra > 0 and not is_fee
            is_buy = (any(k in tipo for k in ('compra', 'ingreso', 'deposito', 'depósito', 'ajuste', 'buy', 'deposit', 'receive', 'recepcion', 'recepción', 'entrada', 'abono')) or (m_compra > 0 and m_venta == 0)) and not is_fee
            
            if mode == 'global':
                is_taxable_sell = (any(k in tipo for k in ('venta', 'sell', 'consumo', 'pago', 'payment')) or (m_venta > 0 and m_compra == 0)) and not is_transfer_out and not is_fee
                
                # Egress stale orphan withdrawals (> 30 days without deposit match) so they consume stock
                # rather than floating indefinitely into subsequent fiscal years
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
                        "tipo": tipo
                    })
            else:
                is_internal_transfer = is_transfer_out and any(k in coment for k in ('interno', 'internal', 'intercambio', 'transferencia interna'))
                is_taxable_sell = (any(k in tipo for k in ('venta', 'sell', 'consumo', 'pago', 'payment')) or (m_venta > 0 and m_compra == 0 and not is_transfer_out and not is_internal_transfer)) and not is_fee
            
            if is_buy and m_compra > 0:
                qty_to_enqueue = m_compra
                if mode == 'global' and is_deposit_inflow and transfer_out_pool:
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
                        matched_qty = min(qty_to_enqueue, t_out['qty_remaining'])
                        t_out['qty_remaining'] -= matched_qty
                        qty_to_enqueue -= matched_qty
                    transfer_out_pool = collections.deque([t for t in transfer_out_pool if t.get('qty_remaining', 0.0) > CRYPTO_DUST_EPSILON])

                if exchange_deficits[ex] > 1e-9:
                    rec_ex = min(m_compra, exchange_deficits[ex])
                    exchange_deficits[ex] -= rec_ex

                if uncovered_deficit > 1e-9:
                    recovered = min(uncovered_deficit, m_compra)
                    uncovered_deficit = max(0.0, uncovered_deficit - recovered)

                # Isolate historical deficits: do NOT subtract from qty_to_enqueue so future sales are not starved
                if qty_to_enqueue > 1e-9:
                    buy_queue.append({"fecha": row.fecha, "dt": r_dt, "qty_remaining": qty_to_enqueue, "exchange": ex})
            elif is_taxable_sell and m_venta > 0:
                remaining_to_match = m_venta
                while remaining_to_match > CRYPTO_DUST_EPSILON and buy_queue:
                    buy_lot = buy_queue[0]
                    matched_qty = min(remaining_to_match, buy_lot['qty_remaining'])
                    buy_lot['qty_remaining'] -= matched_qty
                    remaining_to_match -= matched_qty
                    if buy_lot['qty_remaining'] <= CRYPTO_DUST_EPSILON:
                        buy_queue.popleft()
                
                if remaining_to_match > 1e-9:
                    uncovered_deficit += remaining_to_match
                    last_deficit_dt = r_dt
                    exchange_deficits[ex] += remaining_to_match
                    is_in_range = True
                    if year and (pd.isna(r_dt) or r_dt.year != int(year)):
                        is_in_range = False
                    elif dt_start_parsed is not None and (pd.isna(r_dt) or r_dt < dt_start_parsed):
                        is_in_range = False
                    elif dt_end_parsed is not None and (pd.isna(r_dt) or r_dt > dt_end_parsed):
                        is_in_range = False
                    elif is_certified_tx:
                        is_in_range = False
                    
                    if is_in_range:
                        deficit = remaining_to_match
                        available_qty = max(0.0, m_venta - remaining_to_match)
                        run_def = uncovered_deficit if mode == 'global' else exchange_deficits[ex]
                        gaps.append({
                            "exchange": "Cartera Global" if mode == 'global' else ex,
                            "origin_exchange": ex, "coin": coin, "crypto": coin, "currency": coin,
                            "date": row.fecha, "deficit": deficit, "missing": deficit,
                            "running_deficit": round(run_def, 8),
                            "sold_qty": m_venta, "available_qty": available_qty, "mode": mode
                        })
            elif mode != 'global' and is_transfer_out and m_venta > 0:
                rem_transfer = m_venta
                while rem_transfer > CRYPTO_DUST_EPSILON and buy_queue:
                    buy_lot = buy_queue[0]
                    matched_qty = min(rem_transfer, buy_lot['qty_remaining'])
                    buy_lot['qty_remaining'] -= matched_qty
                    rem_transfer -= matched_qty
                    if buy_lot['qty_remaining'] <= CRYPTO_DUST_EPSILON:
                        buy_queue.popleft()
            elif is_fee and m_venta > 0:
                rem_fee = m_venta
                while rem_fee > CRYPTO_DUST_EPSILON and buy_queue:
                    buy_lot = buy_queue[0]
                    matched_qty = min(rem_fee, buy_lot['qty_remaining'])
                    buy_lot['qty_remaining'] -= matched_qty
                    rem_fee -= matched_qty
                    if buy_lot['qty_remaining'] <= CRYPTO_DUST_EPSILON:
                        buy_queue.popleft()
                if rem_fee > 1e-9:
                    uncovered_deficit += rem_fee
                    exchange_deficits[ex] += rem_fee
                    is_in_range = True
                    if year and (pd.isna(r_dt) or r_dt.year != int(year)):
                        is_in_range = False
                    elif dt_start_parsed is not None and (pd.isna(r_dt) or r_dt < dt_start_parsed):
                        is_in_range = False
                    elif dt_end_parsed is not None and (pd.isna(r_dt) or r_dt > dt_end_parsed):
                        is_in_range = False
                    elif is_certified_tx:
                        is_in_range = False

                    if is_in_range:
                        deficit = rem_fee
                        available_qty = max(0.0, m_venta - rem_fee)
                        run_def = uncovered_deficit if mode == 'global' else exchange_deficits[ex]
                        gaps.append({
                            "exchange": "Cartera Global" if mode == 'global' else ex,
                            "origin_exchange": ex, "coin": coin, "crypto": coin, "currency": coin,
                            "date": row.fecha, "deficit": deficit, "missing": deficit,
                            "running_deficit": round(run_def, 8),
                            "sold_qty": m_venta, "available_qty": available_qty, "mode": mode
                        })

        if mode == 'global':
            max_group_dt = group_sorted['dt'].max()
            _egress_stale_withdrawals(transfer_out_pool, buy_queue, max_group_dt, max_days=30)

    return gaps


check_for_gaps_in_batches = check_history_gaps
