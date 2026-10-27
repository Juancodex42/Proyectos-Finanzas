"""
Servicio de persistencia, deduplicación e inserción de transacciones.
Aplica blindaje a períodos certificados y coordina el recálculo de FIFO.
Referencia de diseño: docs/contratos_io_transacciones.md
"""

import re
import sqlite3
import logging
import pandas as pd
import db.connection

logger = logging.getLogger(__name__)

def get_connection():
    return db.connection.get_connection()

from services.certifications_service import _normalize_cert_boundary


try:
    from .transaction_dedup_service import deduplicate_existing_database
except ImportError:
    from services.transaction_dedup_service import deduplicate_existing_database

deduplicate_database = deduplicate_existing_database


def insert_transactions(transactions_list, trigger_fifo_recalc=True, allow_certified_insert=False, external_conn=None, source=None):
    """Inserts dictionary transactions into SQLite (using external_conn if provided without commit/close). Returns (inserted, skipped)."""
    if isinstance(trigger_fifo_recalc, str):
        source = trigger_fifo_recalc
        trigger_fifo_recalc = bool(allow_certified_insert) if isinstance(allow_certified_insert, bool) else True
        allow_certified_insert = (source == "CERTIFICATION")
    if not transactions_list:
        return 0, 0

    is_cert_source = (source == "CERTIFICATION")
    conn = external_conn if external_conn is not None else get_connection()
    c = conn.cursor()
    certified_ranges, has_fills_in_db, has_orders_in_db = [], False, False
    try:
        c.execute("SELECT start_date, end_date FROM certifications")
        certified_ranges = c.fetchall()
        has_fills_in_db = c.execute("SELECT 1 FROM transactions WHERE comentarios LIKE '%trade%' OR comentarios LIKE '%fill%' LIMIT 1").fetchone() is not None
        has_orders_in_db = c.execute("SELECT 1 FROM transactions WHERE comentarios LIKE '%order%' OR comentarios LIKE '%orden%' LIMIT 1").fetchone() is not None
    except sqlite3.OperationalError:
        certified_ranges, has_fills_in_db, has_orders_in_db = [], True, True

    inserted, skipped = 0, 0
    from models.transaction_models import canonicalize_ticker, compute_canonical_tx_hash
    from parsers.base_parser import normalize_exchange_name
    from services.fifo_service import parse_date_robust
    def_ex, def_coin, def_tipo, def_com = ('Binance', 'USDT', 'Compra', 'Certificación C.P.N.') if is_cert_source else ('', '', '', '')

    for tx in transactions_list:
        try:
            raw_fecha = str(tx.get('Fecha', tx.get('fecha', ''))).strip()
            raw_ex = str(tx.get('Exchange', tx.get('exchange', def_ex)) or def_ex).strip()
            tx_exchange = normalize_exchange_name(raw_ex) if not is_cert_source else (raw_ex or 'Binance')
            raw_coin = str(tx.get('Moneda', tx.get('moneda', def_coin)) or def_coin).strip()
            tx_moneda = canonicalize_ticker(raw_coin) if not is_cert_source else (raw_coin or 'USDT')
            tx_tipo = str(tx.get('Tipo de Operación', tx.get('tipo_operacion', def_tipo)) or def_tipo).strip()
            tx_m_compra = float(tx.get('Monto Compra (Cripto)', tx.get('monto_compra_cripto', 0)) or 0)
            tx_m_venta = float(tx.get('Monto Venta (Cripto)', tx.get('monto_venta_cripto', 0)) or 0)
            tx_c_compra = float(tx.get('Cotización Compra', tx.get('cotizacion_compra', 0)) or 0)
            tx_c_venta = float(tx.get('Cotización Venta', tx.get('cotizacion_venta', 0)) or 0)
            tx_m_ars = float(tx.get('Monto ARS', tx.get('monto_ars', 0)) or 0)
            tx_comentarios = str(tx.get('Comentarios', tx.get('comentarios', def_com)) or def_com).strip()

            if not is_cert_source and (not raw_fecha or not tx_exchange or not tx_moneda or (tx_m_compra <= 0 and tx_m_venta <= 0 and tx_m_ars <= 0)):
                skipped += 1
                continue

            if len(raw_fecha) == 19 and raw_fecha[4] == '-' and raw_fecha[7] == '-':
                tx_fecha = raw_fecha[:10] + ' ' + raw_fecha[11:19]
            elif len(raw_fecha) == 10 and raw_fecha[4] == '-' and raw_fecha[7] == '-':
                tx_fecha = raw_fecha + ' 00:00:00'
            elif raw_fecha:
                try:
                    _parsed_dt = parse_date_robust(raw_fecha)
                    tx_fecha = _parsed_dt.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(_parsed_dt) else raw_fecha[:19].replace('T', ' ')
                except Exception:
                    tx_fecha = raw_fecha[:19].replace('T', ' ')
            else:
                tx_fecha = raw_fecha

            is_certified_range, matched_boundary = False, None
            if certified_ranges and not is_cert_source:
                for c_start, c_end in certified_ranges:
                    if not c_start or not c_end:
                        continue
                    c_s, c_e = _normalize_cert_boundary(c_start, is_end=False), _normalize_cert_boundary(c_end, is_end=True)
                    if c_s <= tx_fecha <= c_e:
                        is_certified_range, matched_boundary = True, (c_s, c_e)
                        break
                if is_certified_range:
                    if not allow_certified_insert:
                        logger.warning(f"Auditoría: Operación {tx_fecha} ({tx_moneda} {tx_tipo}) dentro del período certificado ({matched_boundary[0][:10]} al {matched_boundary[1][:10]}). Se omite para salvaguardar la certificación oficial.")
                        skipped += 1
                        continue
                    logger.warning(f"Auditoría: Operación {tx_fecha} ({tx_moneda} {tx_tipo}) dentro del período certificado ({matched_boundary[0][:10]} al {matched_boundary[1][:10]}). Se inserta provisoriamente con auditoría de costo requerida.")

            from models.transaction_models import get_canonical_exchange_root
            ex_root = get_canonical_exchange_root(tx_exchange)
            ex_family = {
                'BINANCE': ['Binance', 'Binance Spot', 'Binance P2P'],
                'BITSO': ['Bitso', 'Bitso Alpha'],
                'RIPIO': ['Ripio', 'Ripio Trade', 'Ripio Select'],
                'FIWIND': ['Fiwind'],
                'LEMON': ['Lemon Cash', 'Lemon'],
                'BYBIT': ['Bybit', 'Bybit Spot', 'Bybit P2P'],
                'OKX': ['OKX', 'OKX Spot', 'OKX P2P'],
                'BITGET': ['Bitget', 'Bitget Spot', 'Bitget P2P'],
            }
            ex_candidates = ex_family.get(ex_root, [tx_exchange])
            if tx_exchange not in ex_candidates:
                ex_candidates.append(tx_exchange)
            ex_ph = ','.join(['?'] * len(ex_candidates))

            p_hashes_to_delete = []
            if tx_comentarios and not is_cert_source:
                m_ord = re.search(r'(?:\b(?:order\s*id|order\s*no\.?)\b\s*[:#]\s*|\b(?:order|orden)\s*[:#]?\s*)((?=[a-zA-Z0-9_\-]*\d)[a-zA-Z0-9_\-]+)', str(tx_comentarios), re.IGNORECASE)
                has_trade_id = bool(re.search(r'(?:\b(?:trade\s*id|fill\s*id)\b\s*[:#]\s*|\b(?:trade|fill)\s*[:#]?\s*)((?=[a-zA-Z0-9_\-]*\d)[a-zA-Z0-9_\-]+)', str(tx_comentarios), re.IGNORECASE))
                if has_trade_id:
                    has_fills_in_db = True
                elif m_ord:
                    has_orders_in_db = True

                if m_ord:
                    clean_op_id = m_ord.group(1).strip()
                    if len(clean_op_id) >= 6 and any(ch.isdigit() for ch in clean_op_id):
                        if not has_trade_id and has_fills_in_db:
                            c.execute(
                                f"SELECT SUM(monto_compra_cripto), SUM(monto_venta_cripto), COUNT(*) FROM transactions WHERE moneda = ? AND exchange IN ({ex_ph}) AND comentarios LIKE ? AND (comentarios LIKE '%trade%' OR comentarios LIKE '%fill%')",
                                (tx_moneda, *ex_candidates, f"%{clean_op_id}%")
                            )
                            fills_row = c.fetchone()
                            if fills_row and fills_row[2] and fills_row[2] >= 1:
                                if abs((fills_row[0] or 0.0) - tx_m_compra) < 1e-6 and abs((fills_row[1] or 0.0) - tx_m_venta) < 1e-6:
                                    skipped += 1
                                    continue
                        elif has_trade_id and has_orders_in_db:
                            c.execute(
                                f"SELECT tx_hash, is_certified, monto_compra_cripto, monto_venta_cripto FROM transactions WHERE moneda = ? AND exchange IN ({ex_ph}) AND comentarios LIKE ? AND (comentarios NOT LIKE '%trade%' AND comentarios NOT LIKE '%fill%')",
                                (tx_moneda, *ex_candidates, f"%{clean_op_id}%")
                            )
                            parent_orders = c.fetchall()
                            if parent_orders:
                                if any(p[1] == 1 for p in parent_orders):
                                    skipped += 1
                                    continue
                                p_tot_buy = sum(float(p[2] or 0.0) for p in parent_orders)
                                p_tot_sell = sum(float(p[3] or 0.0) for p in parent_orders)
                                c.execute(
                                    f"SELECT SUM(monto_compra_cripto), SUM(monto_venta_cripto) FROM transactions WHERE moneda = ? AND exchange IN ({ex_ph}) AND comentarios LIKE ? AND (comentarios LIKE '%trade%' OR comentarios LIKE '%fill%')",
                                    (tx_moneda, *ex_candidates, f"%{clean_op_id}%")
                                )
                                curr_fills = c.fetchone()
                                acc_buy = (float(curr_fills[0] or 0.0)) + tx_m_compra
                                acc_sell = (float(curr_fills[1] or 0.0)) + tx_m_venta
                                if acc_buy >= (p_tot_buy - 1e-6) and acc_sell >= (p_tot_sell - 1e-6):
                                    p_hashes_to_delete = [p[0] for p in parent_orders]

            hash_fecha_arg = f"{tx_fecha}Z" if (tx.get('_is_utc') and not str(tx_fecha).endswith('Z')) else tx_fecha
            tx_hash = (tx.get('tx_hash') if is_cert_source else None) or compute_canonical_tx_hash(
                hash_fecha_arg, tx_exchange, tx_tipo, tx_moneda, monto_compra=tx_m_compra, monto_venta=tx_m_venta, monto_ars=tx_m_ars, unique_ref=tx_comentarios
            )
            if is_certified_range and allow_certified_insert:
                if '[Auditoría: Período Certificado]' not in tx_comentarios:
                    tx_comentarios = f"{tx_comentarios} [Auditoría: Período Certificado]".strip()
            req_audit = 0 if is_cert_source else (1 if is_certified_range else int(tx.get('requires_cost_audit', 0) or 0))
            tx_fn = str(tx.get('filename', '') or '')
            tx_src = str(tx.get('source', source or 'NATIVE_CSV') or source or 'NATIVE_CSV')
            if is_cert_source:
                c.execute("""
                    INSERT INTO transactions (
                        tx_hash, fecha, exchange, tipo_operacion, moneda,
                        monto_compra_cripto, monto_venta_cripto, cotizacion_compra,
                        cotizacion_venta, monto_ars, comentarios, filename,
                        is_certified, source, requires_cost_audit
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0)
                    ON CONFLICT(tx_hash) DO UPDATE SET
                        is_certified = 1,
                        source = 'CERTIFICATION',
                        requires_cost_audit = 0,
                        cotizacion_compra = CASE WHEN excluded.cotizacion_compra > 0 THEN excluded.cotizacion_compra ELSE transactions.cotizacion_compra END
                """, (tx_hash, tx_fecha, tx_exchange, tx_tipo, tx_moneda, tx_m_compra, tx_m_venta, tx_c_compra, tx_c_venta, tx_m_ars, tx_comentarios, tx_fn, tx_src))
            else:
                c.execute("""
                    INSERT INTO transactions (
                        tx_hash, fecha, exchange, tipo_operacion, moneda,
                        monto_compra_cripto, monto_venta_cripto, cotizacion_compra,
                        cotizacion_venta, monto_ars, comentarios, filename,
                        is_certified, source, requires_cost_audit
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (tx_hash, tx_fecha, tx_exchange, tx_tipo, tx_moneda, tx_m_compra, tx_m_venta, tx_c_compra, tx_c_venta, tx_m_ars, tx_comentarios, tx_fn, 1 if is_cert_source else 0, tx_src, req_audit))
            if p_hashes_to_delete:
                c.execute(f"DELETE FROM transactions WHERE tx_hash IN ({','.join(['?']*len(p_hashes_to_delete))})", p_hashes_to_delete)
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1
        except Exception:
            if external_conn is not None and not isinstance(tx, dict):
                raise
            skipped += 1

    if external_conn is None:
        try:
            conn.commit()
        finally:
            conn.close()

    if inserted > 0 and external_conn is None:
        try:
            from services.cache_service import invalidate_analytics_cache
            invalidate_analytics_cache()
        except Exception as e:
            logger.warning(f"Error invalidating analytics cache after transaction insert: {e}")

        real_coins = {
            str(tx.get('Moneda', tx.get('moneda', ''))).strip() for tx in transactions_list
            if str(tx.get('Exchange', tx.get('exchange', ''))).strip() != 'Sistema de Conciliación'
            and str(tx.get('Tipo de Operación', tx.get('tipo_operacion', ''))).strip() != 'Ingreso Automático'
            and not any(k in str(tx.get('Comentarios', tx.get('comentarios', ''))) for k in ('para subsanar venta', 'Ingreso clasificado manualmente', '[Ajuste FIFO'))
        } - {''}
        tx_fechas = [str(tx.get('Fecha', tx.get('fecha', ''))).strip() for tx in transactions_list if tx.get('Fecha') or tx.get('fecha')]
        tx_fechas = [f for f in tx_fechas if len(f) >= 10]
        min_date = min(tx_fechas) if tx_fechas else None
        max_date = max(tx_fechas) if tx_fechas else None
        if real_coins and min_date and max_date:
            try:
                import db_manager
                from services.reconciliation_service import ReconciliationEngine
                ReconciliationEngine(db_path=getattr(db_manager, 'DB_PATH', None)).prune_obsolete_auto_corrections(
                    coins=real_coins, auto_re_correct=False, start_date=min_date, end_date=max_date
                )
            except Exception as e:
                logger.warning(f"Failed to prune obsolete auto corrections: {e}")

    if inserted > 0 and trigger_fifo_recalc:
        try:
            from services.fifo_service import recalculate_fifo_costs_db
            recalculate_fifo_costs_db()
        except Exception as e:
            logger.error(f"Error executing recalculate_fifo_costs_db after insert: {e}")
    return inserted, skipped
def _format_tx_df(df, extra_cols=None, include_filename=False):
    if isinstance(extra_cols, bool):
        include_filename, extra_cols = extra_cols, None
    if df.empty:
        return pd.DataFrame()
    df = df.rename(columns={
        'fecha': 'Fecha', 'exchange': 'Exchange', 'tipo_operacion': 'Tipo de Operación',
        'moneda': 'Moneda', 'monto_compra_cripto': 'Monto Compra (Cripto)',
        'monto_venta_cripto': 'Monto Venta (Cripto)', 'cotizacion_compra': 'Cotización Compra',
        'cotizacion_venta': 'Cotización Venta', 'monto_ars': 'Monto ARS', 'comentarios': 'Comentarios'
    })
    cols = ['Fecha', 'Exchange', 'Tipo de Operación', 'Moneda', 'Monto Compra (Cripto)', 'Monto Venta (Cripto)', 'Cotización Compra', 'Cotización Venta', 'Monto ARS', 'Comentarios', 'tx_hash'] + (extra_cols or [])
    if include_filename:
        df['filename'] = df['filename'].fillna('') if 'filename' in df.columns else ''
        if 'filename' not in cols:
            cols.append('filename')
    return df[[c for c in cols if c in df.columns]]

def get_all_transactions_df(include_filename=False):
    """Returns all transactions as a Pandas DataFrame formatted for the Master Excel generator."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM transactions ORDER BY fecha ASC", conn)
    finally:
        conn.close()
    return _format_tx_df(df, ['is_certified', 'certification_id', 'source', 'monto_descubierto', 'requires_cost_audit'], include_filename=include_filename)

get_all_transactions = get_all_transactions_df

def get_transactions_by_filenames(filenames):
    """Filter transactions where comentarios contains any of the filenames."""
    if not filenames:
        return pd.DataFrame()
    conn = get_connection()
    try:
        conds, params = ["comentarios LIKE ?" for _ in filenames], [f"%{f}%" for f in filenames]
        df = pd.read_sql_query(f"SELECT * FROM transactions WHERE {' OR '.join(conds)} ORDER BY fecha ASC", conn, params=params)
    finally:
        conn.close()
    return _format_tx_df(df)

def clear_db():
    """Deletes all uncertified transactions while preserving certified records."""
    conn = get_connection()
    try:
        conn.cursor().execute("DELETE FROM transactions WHERE (is_certified IS NULL OR is_certified = 0)")
        conn.commit()
    finally:
        conn.close()
    try:
        from services.cache_service import invalidate_analytics_cache
        invalidate_analytics_cache()
    except Exception as e:
        logger.warning(f"Error invalidating analytics cache in clear_db: {e}")

def expand_exchange_names(exchanges):
    """Expands canonical exchange roots to match all sub-account names in the database."""
    if not exchanges:
        return []
    from models.transaction_models import get_canonical_exchange_root
    ex_map = {
        'BINANCE': ['Binance', 'Binance Spot', 'Binance P2P', 'BINANCE'], 'BITSO': ['Bitso', 'Bitso Alpha', 'BITSO'],
        'RIPIO': ['Ripio', 'Ripio Trade', 'Ripio Classic', 'Ripio Wallet', 'RIPIO'], 'BITGET': ['Bitget', 'Bitget P2P', 'BITGET'],
        'LEMON': ['Lemon', 'Lemon Cash', 'LEMON'], 'FIWIND': ['Fiwind', 'FIWIND'],
    }
    return list({s for ex in exchanges for s in [str(ex).strip()] + ex_map.get(get_canonical_exchange_root(str(ex).strip()), [])})

def delete_transactions_by_exchange(exchange: str, year: int = None) -> int:
    """Deletes uncertified transactions belonging to an exchange (optionally filtered by year) and triggers FIFO recalculation."""
    if not exchange:
        return 0
    expanded = expand_exchange_names([exchange])
    conn = get_connection()
    try:
        c = conn.cursor()
        sql = f"DELETE FROM transactions WHERE exchange IN ({','.join(['?']*len(expanded))}) AND (is_certified IS NULL OR is_certified = 0)"
        params = list(expanded)
        if year is not None and str(year).strip() != "":
            sql += " AND substr(fecha, 1, 4) = ?"
            params.append(str(year).strip()[:4])
        c.execute(sql, params)
        deleted_count = c.rowcount
        conn.commit()
    finally:
        conn.close()
    if deleted_count > 0:
        try:
            from services.cache_service import invalidate_analytics_cache
            invalidate_analytics_cache()
            from services.fifo_service import recalculate_fifo_costs_db
            recalculate_fifo_costs_db()
        except Exception as e:
            logger.warning(f"Notice after deleting exchange {exchange}: {e}")
    return deleted_count

def get_transactions(exchanges=None, date_start=None, date_end=None, status_filter=None):
    """Fetches transactions filtered by exchange, date range, and certification status with high-performance direct row mapping."""
    conn = get_connection()
    query = (
        "SELECT fecha, exchange, tipo_operacion, moneda, monto_compra_cripto, "
        "monto_venta_cripto, cotizacion_compra, cotizacion_venta, monto_ars, "
        "comentarios, tx_hash FROM transactions WHERE 1=1"
    )
    params = []
    if exchanges and isinstance(exchanges, str):
        exchanges = [exchanges]
    if exchanges and isinstance(exchanges, list) and len(exchanges) > 0:
        ex_list = expand_exchange_names(exchanges)
        query += f" AND exchange IN ({','.join(['?']*len(ex_list))})"
        params.extend(ex_list)
    if date_start and str(date_start).strip():
        query += " AND fecha >= ?"
        params.append(str(date_start)[:10] + " 00:00:00")
    if date_end and str(date_end).strip():
        query += " AND fecha <= ?"
        params.append(str(date_end)[:10] + " 23:59:59")
    if status_filter == 'certified':
        query += " AND is_certified = 1"
    elif status_filter == 'uncertified':
        query += " AND (is_certified IS NULL OR is_certified = 0)"
    query += " ORDER BY fecha ASC"
    try:
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    return [
        {
            'Fecha': r[0],
            'Exchange': r[1],
            'Tipo de Operación': r[2],
            'Moneda': r[3],
            'Monto Compra (Cripto)': r[4],
            'Monto Venta (Cripto)': r[5],
            'Cotización Compra': r[6],
            'Cotización Venta': r[7],
            'Monto ARS': r[8],
            'Comentarios': r[9],
            'tx_hash': r[10]
        }
        for r in rows
    ]

def get_latest_transaction_info():
    """Returns the earliest and latest transaction timestamps recorded in the database."""
    conn = get_connection()
    try:
        row = conn.cursor().execute("SELECT MIN(fecha), MAX(fecha), COUNT(*) FROM transactions").fetchone()
    finally:
        conn.close()
    return {"first_tx_date": row[0], "latest_tx_date": row[1], "total_transactions": row[2]} if row and row[1] else None
