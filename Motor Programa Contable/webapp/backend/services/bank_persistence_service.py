"""
Persistence and Auto-Calculation Service for Bank Reconciliation,
Own-Account Classification, and Operational Stock/Cash Excel Defaults.
"""
import hashlib
import json
import logging
import re
import sqlite3
from typing import List, Dict, Any, Optional
import pandas as pd

from db.connection import get_connection
from models.operational_models import (
    BankTransaction, TIPO_INYECCION, TIPO_RETIRO,
    TIPO_PRESTAMO_RECIBIDO, TIPO_DEVOLUCION_PRESTAMO, TIPO_DEVOLUCION_PRESTAMO_USDT,
    TIPO_RENDIMIENTO, TIPO_GASTO_ARBITRAJE,
)

logger = logging.getLogger(__name__)

DEFAULT_OPERATIONAL_SETTINGS: Dict[str, Any] = {
    "owner_names": ["titular", "cuenta demo"],
    "owner_cuits": ["20000000001"],
    "operational_accounts": [
        "mercado pago", "mercadopago", "lemon", "lemon cash", "fiwind", "ripio", "binance"
    ],
    "personal_external_accounts": [
        "galicia", "santander", "bbva", "macro", "nacion", "nación", "hsbc",
        "patagonia", "icbc", "credicoop", "provincia", "ciudad",
        "cuenta personal", "ahorro", "sueldo"
    ],
    "personal_expense_threshold_ars": 25000.0,
    "existencia_inicial_usd": 0.0,
    "existencia_inicial_ars": 0.0,
    "garantia_total_usdt": 0.0,
    "saldo_bancos_final_ars": 0.0,
    "cotizacion_cierre_usdt": 1000.0,
}

_BANK_COLS = [
    "id", "tx_hash", "fecha", "banco", "tipo_movimiento", "monto_ars",
    "descripcion", "titular_contraparte", "cuit_contraparte",
    "categoria", "subtipo_cuenta_propia", "matched_tx_id", "raw_reference", "nota_auditoria"
]


def _ensure_tables(conn) -> None:
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS bank_movements ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, tx_hash TEXT UNIQUE, fecha TEXT NOT NULL, "
        "banco TEXT NOT NULL, tipo_movimiento TEXT NOT NULL, monto_ars REAL NOT NULL, "
        "descripcion TEXT DEFAULT '', titular_contraparte TEXT DEFAULT '', cuit_contraparte TEXT DEFAULT '', "
        "categoria TEXT DEFAULT 'PENDIENTE', subtipo_cuenta_propia TEXT DEFAULT NULL, "
        "matched_tx_id TEXT DEFAULT NULL, raw_reference TEXT DEFAULT '', nota_auditoria TEXT DEFAULT '', "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    c.execute("CREATE TABLE IF NOT EXISTS operational_settings (key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")


def normalize_bank_date(raw_date: str) -> str:
    if not raw_date:
        return ""
    s = str(raw_date).strip()
    # Only perform UTC-to-Argentina conversion if the string has an explicit timezone specifier
    has_tz = ('Z' in s.upper()) or (('+' in s or ('-' in s and s.rfind('-') > 10)) and len(s) > 19)
    if has_tz:
        try:
            dt = pd.to_datetime(s, utc=True, errors='coerce')
            if pd.notna(dt):
                return dt.tz_convert('America/Argentina/Buenos_Aires').tz_localize(None).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
    try:
        is_iso = bool(re.match(r'^\d{4}[-/]', s))
        dt = pd.to_datetime(s, dayfirst=not is_iso, errors='coerce')
        if pd.notna(dt):
            return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        pass
    return s[:19].replace('T', ' ')


def compute_bank_tx_hash(b: BankTransaction) -> str:
    norm_date = normalize_bank_date(b.fecha)
    raw_str = f"{norm_date}|{str(b.banco).upper().strip()}|{str(b.tipo_movimiento).upper().strip()}|{float(b.monto_ars):.2f}|{str(b.raw_reference or '').strip()}|{str(b.descripcion or '').strip()[:40]}"
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()[:24]


def get_operational_settings() -> Dict[str, Any]:
    conn = get_connection()
    try:
        merged = dict(DEFAULT_OPERATIONAL_SETTINGS)
        try:
            rows = conn.cursor().execute("SELECT key, value_json FROM operational_settings").fetchall()
        except sqlite3.OperationalError:
            _ensure_tables(conn)
            rows = []
        for k, v_json in rows:
            try:
                merged[k] = json.loads(v_json)
            except Exception:
                pass
        return merged
    finally:
        conn.close()


def save_operational_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_connection()
    try:
        _ensure_tables(conn)
        c = conn.cursor()
        for k, val in data.items():
            if k in DEFAULT_OPERATIONAL_SETTINGS and val is not None:
                c.execute("INSERT OR REPLACE INTO operational_settings (key, value_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (k, json.dumps(val)))
        conn.commit()
    finally:
        conn.close()
    return get_operational_settings()


def _map_category_to_ledger_type(categoria: str) -> Optional[str]:
    cat = str(categoria or '').upper().strip()
    mapping = {
        'INYECCION': TIPO_INYECCION,
        'RETIRO': TIPO_RETIRO,
        'GASTO_PERSONAL': TIPO_RETIRO,
        'GASTO_ARBITRAJE': TIPO_GASTO_ARBITRAJE,
        'PRESTAMO': TIPO_PRESTAMO_RECIBIDO,
        'PRESTAMO_RECIBIDO': TIPO_PRESTAMO_RECIBIDO,
        'DEVOLUCION_PRESTAMO': TIPO_DEVOLUCION_PRESTAMO,
        'DEVOLUCION_PRESTAMO_USDT': TIPO_DEVOLUCION_PRESTAMO_USDT,
        'RENDIMIENTO': TIPO_RENDIMIENTO,
    }
    return mapping.get(cat)


def _sync_single_bank_row_to_transactions(c, b_dict: Dict[str, Any]) -> bool:
    ledger_hash = f"BANK_{b_dict['tx_hash']}"
    ledger_type = _map_category_to_ledger_type(b_dict.get('categoria', ''))
    if not ledger_type:
        c.execute("DELETE FROM transactions WHERE tx_hash = ? AND (is_certified IS NULL OR is_certified = 0)", (ledger_hash,))
        return False

    norm_fecha = normalize_bank_date(b_dict.get('fecha', ''))
    try:
        if c.execute("SELECT 1 FROM transactions WHERE tx_hash = ? AND is_certified = 1 LIMIT 1", (ledger_hash,)).fetchone():
            return False
        if norm_fecha and c.execute("SELECT 1 FROM certifications WHERE start_date <= ? AND end_date >= ? LIMIT 1", (norm_fecha, norm_fecha)).fetchone():
            return False
    except Exception:
        pass

    banco = str(b_dict.get('banco') or 'BANCO / FINTECH').upper().strip()
    monto_ars = float(b_dict.get('monto_ars') or 0.0)
    desc = str(b_dict.get('descripcion') or '').strip()
    titular = str(b_dict.get('titular_contraparte') or '').strip()
    nota = str(b_dict.get('nota_auditoria') or '').strip()
    cat = str(b_dict.get('categoria') or '').upper()

    comment_parts = [f"[Extracto {banco} - {cat}]"]
    if desc:
        comment_parts.append(desc)
    if titular and titular.lower() not in desc.lower():
        comment_parts.append(f"({titular})")
    if nota:
        comment_parts.append(f"| {nota}")
    comentarios = " ".join(comment_parts).strip()

    c.execute(
        "INSERT OR REPLACE INTO transactions (tx_hash, fecha, exchange, tipo_operacion, moneda, monto_compra_cripto, monto_venta_cripto, cotizacion_compra, cotizacion_venta, monto_ars, comentarios, filename, is_certified, source, requires_cost_audit) VALUES (?, ?, ?, ?, 'ARS', 0.0, 0.0, 0.0, 0.0, ?, ?, 'bank_statement', 0, 'BANK_STATEMENT', 0)",
        (ledger_hash, norm_fecha, banco, ledger_type, monto_ars, comentarios)
    )
    return True


def save_reconciled_bank_movements(bank_txs: List[BankTransaction]) -> Dict[str, int]:
    if not bank_txs:
        return {"saved": 0, "synced_to_ledger": 0}

    conn = get_connection()
    saved, synced = 0, 0
    try:
        _ensure_tables(conn)
        c = conn.cursor()
        for b in bank_txs:
            b_hash = b.tx_hash or compute_bank_tx_hash(b)
            b.tx_hash = b_hash
            norm_fecha = normalize_bank_date(b.fecha)
            b.fecha = norm_fecha

            existing = c.execute("SELECT categoria, subtipo_cuenta_propia, nota_auditoria FROM bank_movements WHERE tx_hash = ?", (b_hash,)).fetchone()
            if existing and existing[2] and "[Clasificación Manual]" in str(existing[2]):
                b.categoria, b.subtipo_cuenta_propia, b.nota_auditoria = existing[0], existing[1], existing[2]

            c.execute(
                "INSERT OR REPLACE INTO bank_movements (tx_hash, fecha, banco, tipo_movimiento, monto_ars, descripcion, titular_contraparte, cuit_contraparte, categoria, subtipo_cuenta_propia, matched_tx_id, raw_reference, nota_auditoria) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    b_hash, norm_fecha, str(b.banco).upper(), str(b.tipo_movimiento).upper(),
                    float(b.monto_ars), str(b.descripcion or ''), str(b.titular_contraparte or ''),
                    str(b.cuit_contraparte or ''), str(b.categoria or 'PENDIENTE'),
                    b.subtipo_cuenta_propia, b.matched_tx_id, str(b.raw_reference or ''), str(b.nota_auditoria or '')
                )
            )
            saved += 1
            b_dict = b.model_dump() if hasattr(b, 'model_dump') else b.dict()
            if _sync_single_bank_row_to_transactions(c, b_dict):
                synced += 1
        conn.commit()
    finally:
        conn.close()
    return {"saved": saved, "synced_to_ledger": synced}


def update_bank_movement_category(
    identifier: str, new_category: str, nota: Optional[str] = None, subtipo_cuenta_propia: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    if not identifier:
        return None
    conn = get_connection()
    try:
        _ensure_tables(conn)
        c = conn.cursor()
        row = c.execute(
            f"SELECT {', '.join(_BANK_COLS)} FROM bank_movements WHERE tx_hash = ? OR raw_reference = ? OR CAST(id AS TEXT) = ? LIMIT 1",
            (str(identifier), str(identifier), str(identifier))
        ).fetchone()
        if not row:
            return None

        tx_hash = row[1]
        clean_note = f"[Clasificación Manual] {nota}".strip() if nota else "[Clasificación Manual]"
        if subtipo_cuenta_propia is None:
            if new_category in ('RETIRO', 'INYECCION'):
                subtipo_cuenta_propia = 'PERSONAL_EXTERNA'
            elif new_category == 'PASE_PROPIO':
                subtipo_cuenta_propia = 'OPERATIVA'

        c.execute(
            "UPDATE bank_movements SET categoria = ?, subtipo_cuenta_propia = ?, nota_auditoria = ? WHERE tx_hash = ?",
            (new_category, subtipo_cuenta_propia, clean_note, tx_hash)
        )
        updated_dict = dict(zip(_BANK_COLS, row))
        updated_dict.update({"categoria": new_category, "subtipo_cuenta_propia": subtipo_cuenta_propia, "nota_auditoria": clean_note})
        _sync_single_bank_row_to_transactions(c, updated_dict)
        conn.commit()
        return updated_dict
    finally:
        conn.close()


def get_persisted_bank_movements(
    date_start: Optional[str] = None, date_end: Optional[str] = None, categoria: Optional[str] = None
) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        query = f"SELECT {', '.join(_BANK_COLS)} FROM bank_movements WHERE 1=1"
        params: List[Any] = []
        if date_start and str(date_start).strip():
            query += " AND fecha >= ?"
            params.append(str(date_start)[:10] + " 00:00:00")
        if date_end and str(date_end).strip():
            query += " AND fecha <= ?"
            params.append(str(date_end)[:10] + " 23:59:59")
        if categoria and str(categoria).strip():
            query += " AND categoria = ?"
            params.append(str(categoria).strip().upper())
        query += " ORDER BY fecha DESC"
        try:
            rows = conn.cursor().execute(query, params).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(zip(_BANK_COLS, r)) for r in rows]
    finally:
        conn.close()


def get_bank_ledger_transactions(date_start: Optional[str] = None, date_end: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        query = "SELECT * FROM transactions WHERE source = 'BANK_STATEMENT'"
        params: List[Any] = []
        if date_start and str(date_start).strip():
            query += " AND fecha >= ?"
            params.append(str(date_start)[:10] + " 00:00:00")
        if date_end and str(date_end).strip():
            query += " AND fecha <= ?"
            params.append(str(date_end)[:10] + " 23:59:59")
        query += " ORDER BY fecha ASC"
        df = pd.read_sql_query(query, conn, params=params)
        if df.empty:
            return []
        from services.transactions_service import _format_tx_df
        df = _format_tx_df(df)
        return df.astype(object).where(pd.notnull(df), None).to_dict(orient='records')
    finally:
        conn.close()


def compute_operational_defaults(
    exchanges: Optional[List[str]] = None, date_start: Optional[str] = None, date_end: Optional[str] = None
) -> Dict[str, Any]:
    settings = get_operational_settings()
    conn = get_connection()
    try:
        c = conn.cursor()
        start_bound = (str(date_start)[:10] + " 00:00:00") if (date_start and str(date_start).strip()) else None
        end_bound = (str(date_end)[:10] + " 23:59:59") if (date_end and str(date_end).strip()) else None

        ex_list: List[str] = []
        if isinstance(exchanges, str) and exchanges.strip():
            ex_list = [exchanges.strip()]
        elif exchanges:
            ex_list = [str(e).strip() for e in exchanges if e and str(e).strip()]

        ex_clause = ""
        ex_params: List[Any] = []
        if ex_list:
            from models.transaction_models import get_canonical_exchange_root
            conds = []
            for ex in ex_list:
                root = get_canonical_exchange_root(ex).lower()
                ex_low = ex.lower()
                conds.append("(LOWER(COALESCE(exchange, '')) = ? OR LOWER(COALESCE(exchange, '')) LIKE ?)")
                ex_params.extend([ex_low, f"%{root}%"])
            ex_clause = " AND (" + " OR ".join(conds) + ")"

        # 1. Calculate Existencia Inicial USD from stablecoin history prior to start_bound
        calc_init_usd = float(settings.get("existencia_inicial_usd", 0.0))
        if start_bound or ex_list:
            q1 = (
                "SELECT SUM(COALESCE(monto_compra_cripto, 0) - COALESCE(monto_venta_cripto, 0)) FROM transactions "
                "WHERE UPPER(COALESCE(moneda, 'USDT')) IN ('USDT', 'USDC', 'DAI', 'USD', 'BUSD', 'FDUSD') "
                "AND LOWER(COALESCE(tipo_operacion, '')) NOT LIKE '%bloqueo comerciante%' "
                "AND (source IS NULL OR source != 'CERTIFICATION')"
            )
            q1_params: List[Any] = []
            if start_bound:
                q1 += " AND fecha < ?"
                q1_params.append(start_bound)
            row_prior = c.execute(q1 + ex_clause, q1_params + ex_params).fetchone()
            if row_prior and row_prior[0] is not None and abs(float(row_prior[0])) > 1e-6:
                calc_init_usd = round(max(0.0, float(row_prior[0])), 2)

        # 2. Calculate closing USDT exchange rate on or before end_bound
        cierre_rate = float(settings.get("cotizacion_cierre_usdt", 1601.20))
        rate_query = (
            "SELECT cotizacion_venta, cotizacion_compra FROM transactions "
            "WHERE UPPER(COALESCE(moneda, '')) = 'USDT' "
            "AND (COALESCE(cotizacion_venta, 0) > 0 OR COALESCE(cotizacion_compra, 0) > 0) "
            "AND (source IS NULL OR source != 'CERTIFICATION')"
            + ex_clause
        )
        rate_params: List[Any] = list(ex_params)
        if end_bound:
            rate_query += " AND fecha <= ?"
            rate_params.append(end_bound)
        r_row = c.execute(rate_query + " ORDER BY fecha DESC LIMIT 1", rate_params).fetchone()
        if r_row:
            detected_rate = float(r_row[0] or r_row[1] or 0.0)
            if detected_rate > 0:
                cierre_rate = round(detected_rate, 2)

        # 3. Calculate Guarantee USDT locked if explicit rows exist
        garantia_usdt = float(settings.get("garantia_total_usdt", 650.0))
        g_row = c.execute(
            "SELECT SUM(ABS(COALESCE(monto_compra_cripto, 0)) + ABS(COALESCE(monto_venta_cripto, 0))) "
            "FROM transactions WHERE LOWER(COALESCE(tipo_operacion, '')) LIKE '%bloqueo comerciante%'"
            + ex_clause,
            ex_params
        ).fetchone()
        if g_row and g_row[0] and float(g_row[0]) > 0:
            garantia_usdt = round(float(g_row[0]), 2)

        # 4. Bank movements summary in period
        bank_movs = get_persisted_bank_movements(date_start=date_start, date_end=date_end)
        by_cat: Dict[str, Dict[str, Any]] = {}
        for m in bank_movs:
            cat = m.get("categoria") or "PENDIENTE"
            if cat not in by_cat:
                by_cat[cat] = {"count": 0, "total_ars": 0.0}
            by_cat[cat]["count"] += 1
            by_cat[cat]["total_ars"] = round(by_cat[cat]["total_ars"] + float(m.get("monto_ars") or 0.0), 2)

        return {
            "existencia_inicial_usd": calc_init_usd,
            "existencia_inicial_ars": float(settings.get("existencia_inicial_ars", 604395.39)),
            "garantia_total_usdt": garantia_usdt,
            "saldo_bancos_final_ars": float(settings.get("saldo_bancos_final_ars", 1042066.17)),
            "cotizacion_cierre_usdt": cierre_rate,
            "settings": settings,
            "bank_movements_count": len(bank_movs),
            "bank_summary_by_category": by_cat,
        }
    finally:
        conn.close()
