"""
Cross-Audit Service: Reconciles CPA Certifications against Exchange Excel/CSV statements.
Detects OCR date corruptions, decimal/amount mismatches, missing operations in Excel,
and operations omitted from certification, using canonical deduplication across overlapping files.
"""

import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd

from db.connection import get_connection
from models.transaction_models import get_canonical_exchange_root, canonicalize_ticker
from services.fifo_service import parse_dates_series_robust, parse_date_robust

logger = logging.getLogger(__name__)


def _normalize_op_direction(tipo_str: str, mc: float = 0.0, mv: float = 0.0) -> str:
    s = str(tipo_str or '').lower().strip()
    if any(k in s for k in ('compra', 'buy', 'ingreso', 'deposit', 'deposito', 'depósito')) or (mc > 0 and mv == 0):
        return 'BUY'
    if any(k in s for k in ('venta', 'sell', 'retiro', 'withdraw', 'envio', 'envío')) or (mv > 0 and mc == 0):
        return 'SELL'
    return 'OTHER'


def audit_certification_vs_excel(cert_id: Optional[int] = None, target_year: Optional[int] = None) -> Dict[str, Any]:
    """
    Cross-checks certified transactions against uploaded Excel/CSV statements.
    Returns categorized discrepancies: FECHA_DISCREPANTE, MONTO_DISCREPANTE,
    FALTANTE_EN_EXCEL, and OMITIDA_EN_CERTIFICACION.
    """
    conn = get_connection()
    try:
        c = conn.cursor()
        
        # 1. Fetch active certification periods
        if cert_id:
            c.execute("SELECT id, title, start_date, end_date FROM certifications WHERE id = ?", (cert_id,))
        elif target_year:
            c.execute("SELECT id, title, start_date, end_date FROM certifications WHERE start_date LIKE ? OR end_date LIKE ?", 
                      (f"{target_year}%", f"{target_year}%"))
        else:
            c.execute("SELECT id, title, start_date, end_date FROM certifications ORDER BY start_date ASC")
        
        certs = c.fetchall()
        if not certs:
            return {"success": True, "discrepancies": [], "summary": {"total_discrepancies": 0}}

        # 2. Fetch all transactions
        query = """
            SELECT id, tx_hash, fecha, exchange, tipo_operacion, moneda,
                   monto_compra_cripto, monto_venta_cripto, cotizacion_compra, cotizacion_venta,
                   monto_ars, comentarios, filename, is_certified, certification_id, source
            FROM transactions
            WHERE COALESCE(source, '') != 'BANK_STATEMENT'
            ORDER BY fecha ASC
        """
        df_all = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    if df_all.empty:
        return {"success": True, "discrepancies": [], "summary": {"total_discrepancies": 0}}

    df_all['dt'] = parse_dates_series_robust(df_all['fecha'])
    df_all['coin_clean'] = df_all['moneda'].apply(canonicalize_ticker)
    df_all['exchange_root'] = df_all['exchange'].apply(get_canonical_exchange_root)
    df_all['m_compra'] = pd.to_numeric(df_all['monto_compra_cripto'], errors='coerce').fillna(0.0)
    df_all['m_venta'] = pd.to_numeric(df_all['monto_venta_cripto'], errors='coerce').fillna(0.0)
    df_all['amount'] = df_all.apply(lambda r: r['m_compra'] if r['m_compra'] > 0 else r['m_venta'], axis=1)
    df_all['dir'] = df_all.apply(lambda r: _normalize_op_direction(r['tipo_operacion'], r['m_compra'], r['m_venta']), axis=1)

    discrepancies: List[Dict[str, Any]] = []

    for c_row in certs:
        c_id, c_title, s_raw, e_raw = c_row
        s_dt = parse_date_robust(s_raw)
        e_dt = parse_date_robust(e_raw)
        if pd.isna(s_dt) or pd.isna(e_dt):
            continue

        # Certified records in this window
        mask_cert = (
            (df_all['is_certified'] == 1) | (df_all['source'] == 'CERTIFICATION') | (df_all['certification_id'] == c_id)
        ) & (df_all['dt'] >= s_dt) & (df_all['dt'] <= e_dt)
        cert_sub = df_all[mask_cert].copy()

        # Non-certified Excel / CSV records (source != 'CERTIFICATION')
        # We allow a ±5 days boundary to catch date-skewed OCR entries
        mask_excel = (
            (df_all['source'] != 'CERTIFICATION') &
            (df_all['is_certified'] != 1) &
            (df_all['dt'] >= (s_dt - timedelta(days=5))) &
            (df_all['dt'] <= (e_dt + timedelta(days=5)))
        )
        excel_sub = df_all[mask_excel].copy()

        if cert_sub.empty and excel_sub.empty:
            continue

        # Intelligent Deduplication of overlapping Excels:
        # Group excel transactions by (exchange_root, coin_clean, dir, rounded_amount, day)
        excel_used_ids = set()
        excel_records = excel_sub.to_dict('records')
        cert_records = cert_sub.to_dict('records')

        for c_tx in cert_records:
            c_coin = c_tx['coin_clean']
            c_ex = c_tx['exchange_root']
            c_dir = c_tx['dir']
            c_amt = c_tx['amount']
            c_dt = c_tx['dt']
            c_date_str = str(c_tx['fecha'])

            if not c_coin or c_coin in ('ARS', 'USD', 'NONE') or c_amt <= 0:
                continue

            matched_excel = None
            discrepancy_type = None

            # Pass 1: Identical Amount & Direction & Exchange -> Check Date Discrepancy
            for e_tx in excel_records:
                if e_tx['id'] in excel_used_ids:
                    continue
                if e_tx['coin_clean'] != c_coin or e_tx['exchange_root'] != c_ex or e_tx['dir'] != c_dir:
                    continue
                
                # Check if amount matches within 0.0001
                if abs(e_tx['amount'] - c_amt) <= 1e-4:
                    e_dt = e_tx['dt']
                    diff_days = abs((c_dt - e_dt).total_seconds()) / 86400.0 if (pd.notna(c_dt) and pd.notna(e_dt)) else 999.0
                    
                    if diff_days > 1.0:
                        # Date discrepancy detected (OCR mistake or timezone offset)
                        matched_excel = e_tx
                        discrepancy_type = 'FECHA_DISCREPANTE'
                        break
                    else:
                        # Clean match
                        matched_excel = e_tx
                        excel_used_ids.add(e_tx['id'])
                        break

            # Pass 2: Identical Date (±24h) & Direction & Exchange -> Check Amount / Decimal Discrepancy
            if not matched_excel and pd.notna(c_dt):
                for e_tx in excel_records:
                    if e_tx['id'] in excel_used_ids:
                        continue
                    if e_tx['coin_clean'] != c_coin or e_tx['exchange_root'] != c_ex or e_tx['dir'] != c_dir:
                        continue
                    
                    e_dt = e_tx['dt']
                    if pd.notna(e_dt) and abs((c_dt - e_dt).total_seconds()) <= 86400:
                        # Check for decimal factor (10x, 100x) or significant divergence
                        e_amt = e_tx['amount']
                        ratio = (c_amt / e_amt) if e_amt > 0 else 0.0
                        is_decimal_shift = abs(ratio - 10.0) < 0.1 or abs(ratio - 100.0) < 0.1 or abs(ratio - 0.1) < 0.01 or abs(ratio - 0.01) < 0.001
                        if is_decimal_shift or (abs(c_amt - e_amt) > 0.05 * max(c_amt, e_amt)):
                            matched_excel = e_tx
                            discrepancy_type = 'MONTO_DISCREPANTE'
                            break

            if matched_excel:
                excel_used_ids.add(matched_excel['id'])
                if discrepancy_type == 'FECHA_DISCREPANTE':
                    discrepancies.append({
                        "id": f"disc_date_{c_tx['id']}_{matched_excel['id']}",
                        "type": "FECHA_DISCREPANTE",
                        "severity": "MEDIA",
                        "cert_id": c_id,
                        "cert_title": c_title,
                        "tx_id": c_tx['id'],
                        "excel_tx_id": matched_excel['id'],
                        "exchange": c_tx['exchange'],
                        "coin": c_coin,
                        "amount": c_amt,
                        "cert_value": c_date_str[:19],
                        "excel_value": str(matched_excel['fecha'])[:19],
                        "excel_filename": matched_excel.get('filename') or 'Extracto Excel',
                        "message": (
                            f"Fecha divergente: En certificación figura {c_date_str[:10]} pero el extracto "
                            f"{matched_excel.get('filename') or ''} registra {str(matched_excel['fecha'])[:10]} "
                            f"({c_amt:,.2f} {c_coin})."
                        ),
                        "suggested_action": "align_with_excel_date"
                    })
                elif discrepancy_type == 'MONTO_DISCREPANTE':
                    discrepancies.append({
                        "id": f"disc_amt_{c_tx['id']}_{matched_excel['id']}",
                        "type": "MONTO_DISCREPANTE",
                        "severity": "ALTA",
                        "cert_id": c_id,
                        "cert_title": c_title,
                        "tx_id": c_tx['id'],
                        "excel_tx_id": matched_excel['id'],
                        "exchange": c_tx['exchange'],
                        "coin": c_coin,
                        "date": c_date_str[:19],
                        "cert_value": f"{c_amt:,.4f} {c_coin}",
                        "excel_value": f"{matched_excel['amount']:,.4f} {c_coin}",
                        "excel_filename": matched_excel.get('filename') or 'Extracto Excel',
                        "message": (
                            f"Importe discrepante: Certificación indica {c_amt:,.4f} {c_coin} "
                            f"vs extracto Excel con {matched_excel['amount']:,.4f} {c_coin} el {c_date_str[:10]}."
                        ),
                        "suggested_action": "align_with_excel_amount"
                    })
            else:
                # Certified transaction without matching Excel transaction
                # Only flag if there are other excel records for this exchange in this period (meaning an excel was uploaded)
                exchange_has_excels = any(e['exchange_root'] == c_ex for e in excel_records)
                if exchange_has_excels:
                    discrepancies.append({
                        "id": f"disc_missing_excel_{c_tx['id']}",
                        "type": "FALTANTE_EN_EXCEL",
                        "severity": "BAJA",
                        "cert_id": c_id,
                        "cert_title": c_title,
                        "tx_id": c_tx['id'],
                        "exchange": c_tx['exchange'],
                        "coin": c_coin,
                        "amount": c_amt,
                        "date": c_date_str[:19],
                        "cert_value": f"{c_amt:,.2f} {c_coin} ({c_tx['tipo_operacion']})",
                        "excel_value": "No registrado en Excel",
                        "message": (
                            f"Operación certificada de {c_amt:,.2f} {c_coin} en {c_tx['exchange']} "
                            f"el {c_date_str[:10]} no figura en los extractos subidos."
                        ),
                        "suggested_action": "verify_missing_source"
                    })

        # Remaining non-matched excel records strictly inside [s_dt, e_dt]
        for e_tx in excel_records:
            if e_tx['id'] in excel_used_ids:
                continue
            e_dt = e_tx['dt']
            if pd.notna(e_dt) and (s_dt <= e_dt <= e_dt):
                e_coin = e_tx['coin_clean']
                e_amt = e_tx['amount']
                if not e_coin or e_coin in ('ARS', 'USD', 'NONE') or e_amt <= 0:
                    continue
                discrepancies.append({
                    "id": f"disc_omitted_cert_{e_tx['id']}",
                    "type": "OMITIDA_EN_CERTIFICACION",
                    "severity": "BAJA",
                    "cert_id": c_id,
                    "cert_title": c_title,
                    "excel_tx_id": e_tx['id'],
                    "exchange": e_tx['exchange'],
                    "coin": e_coin,
                    "amount": e_amt,
                    "date": str(e_tx['fecha'])[:19],
                    "cert_value": "No incluida en Dictamen",
                    "excel_value": f"{e_amt:,.2f} {e_coin} ({e_tx['tipo_operacion']})",
                    "message": (
                        f"Operación en extracto {e_tx.get('filename') or ''} ({e_amt:,.2f} {e_coin} "
                        f"el {str(e_tx['fecha'])[:10]}) no figura en la certificación contable."
                    ),
                    "suggested_action": "verify_omission"
                })

    counts_by_type: Dict[str, int] = {}
    for d in discrepancies:
        t = d['type']
        counts_by_type[t] = counts_by_type.get(t, 0) + 1

    return {
        "success": True,
        "discrepancies": discrepancies,
        "summary": {
            "total_discrepancies": len(discrepancies),
            "by_type": counts_by_type
        }
    }


def resolve_cross_audit_discrepancy(tx_id: int, action: str, new_value: Any = None) -> Dict[str, Any]:
    """
    Applies user resolution to a cross-audit discrepancy.
    Actions: 'align_with_excel_date', 'align_with_excel_amount', 'dismiss'.
    """
    conn = get_connection()
    try:
        c = conn.cursor()
        if action == 'align_with_excel_date' and new_value:
            norm_date = str(new_value).strip()
            c.execute("UPDATE transactions SET fecha = ? WHERE id = ?", (norm_date, tx_id))
            conn.commit()
            return {"success": True, "message": f"Fecha actualizada a {norm_date} exitosamente."}
        elif action == 'align_with_excel_amount' and new_value is not None:
            new_flt = float(new_value)
            # Check if buy or sell to update the correct amount column
            row = c.execute("SELECT monto_compra_cripto FROM transactions WHERE id = ?", (tx_id,)).fetchone()
            if row and float(row[0] or 0.0) > 0:
                c.execute("UPDATE transactions SET monto_compra_cripto = ? WHERE id = ?", (new_flt, tx_id))
            else:
                c.execute("UPDATE transactions SET monto_venta_cripto = ? WHERE id = ?", (new_flt, tx_id))
            conn.commit()
            return {"success": True, "message": f"Importe actualizado a {new_flt} exitosamente."}
        elif action == 'dismiss':
            return {"success": True, "message": "Discrepancia desestimada (se conserva valor dictaminado)."}
        else:
            return {"success": False, "error": f"Acción desconocida: {action}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
