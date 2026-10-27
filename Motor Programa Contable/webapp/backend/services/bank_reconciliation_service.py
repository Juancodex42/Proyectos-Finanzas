"""
Service for automated 5-tier bank reconciliation against P2P orders.
Correlates bank credits/debits with Binance/OKX/Fiwind orders, distinguishes internal pass-through
transfers between operational accounts ('PASE_PROPIO') from transfers to/from personal external accounts
('RETIRO' / 'INYECCION'), and separates deductible bank taxes/fees ('GASTO_ARBITRAJE') from common
personal expenses ('GASTO_PERSONAL').
"""
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd

from models.operational_models import BankTransaction
from db.connection import get_connection
from services.bank_persistence_service import (
    get_operational_settings,
    compute_bank_tx_hash,
)


def _parse_to_arg_tz(val, assume_utc: bool = False) -> Optional[datetime]:
    """Parses date string or object and converts UTC/tz timestamps to UTC-3 (Argentina)."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, datetime):
        if val.tzinfo is not None:
            return pd.Timestamp(val).tz_convert('America/Argentina/Buenos_Aires').tz_localize(None).to_pydatetime()
        if assume_utc:
            return (pd.Timestamp(val) - pd.Timedelta(hours=3)).to_pydatetime()
        return val.to_pydatetime() if hasattr(val, 'to_pydatetime') else val
    s = str(val).strip()
    if not s:
        return None
    if re.search(r'(?:Z|[+-]\d{2}:?\d{2})$', s, re.IGNORECASE):
        try:
            ts = pd.to_datetime(s, errors='coerce', utc=True)
            if pd.notna(ts):
                return ts.tz_convert('America/Argentina/Buenos_Aires').tz_localize(None).to_pydatetime()
        except Exception:
            pass
    try:
        is_iso = bool(re.match(r'^\d{4}[-/]', s))
        ts = pd.to_datetime(s, errors='coerce', dayfirst=not is_iso)
        if pd.notna(ts):
            if assume_utc:
                ts = ts - pd.Timedelta(hours=3)
            return ts.to_pydatetime()
    except Exception:
        pass
    return None


ARBITRAGE_BANK_EXPENSE_KEYWORDS = [
    'ley 25413', '25.413', 'impuesto al cheque', 'imp. deb', 'imp deb', 'impuesto deb',
    'imp. cre', 'imp cre', 'mantenimiento de cuenta', 'cargo bancario'
]

TAX_RETENTION_KEYWORDS = [
    'sircreb', 'iibb', 'ingresos brutos', 'retencion', 'retención',
    'percepcion', 'percepción', 'arba', 'agip', 'rentas'
]

COMMERCIAL_PERSONAL_KEYWORDS = [
    'mostaza', 'mcdonald', 'burger', 'pedidosya', 'rappi', 'farmacity',
    'coto', 'dia', 'carrefour', 'jumbo', 'vea', 'disco', 'ypf', 'shell',
    'axion', 'puma', 'qr', 'compra pos', 'mercadolibre', 'mercado libre',
    'netflix', 'spotify', 'edenor', 'edesur', 'metrogas', 'personal flow', 'movistar', 'claro'
]


def _matches_commercial_keyword(text: str) -> bool:
    """Evaluates commercial personal keywords using word boundaries for short tokens like 'dia' or 'coto'."""
    for k in COMMERCIAL_PERSONAL_KEYWORDS:
        if len(k) <= 5:
            if re.search(rf'\b{re.escape(k)}\b', text, re.IGNORECASE):
                return True
        elif k in text:
            return True
    return False


def reconcile_bank_movements(
    bank_txs: List[BankTransaction],
    user_names: Optional[List[str]] = None,
    user_cuits: Optional[List[str]] = None,
    operational_accounts: Optional[List[str]] = None,
    personal_external_accounts: Optional[List[str]] = None,
    personal_expense_threshold_ars: Optional[float] = None
) -> Dict[str, Any]:
    """
    Applies the 5-tier matching algorithm between bank transactions and P2P crypto orders.
    Returns matched transactions, categorized outliers, and summary statistics.
    """
    if not bank_txs:
        return {"matched": [], "pending": [], "summary": {}}

    try:
        settings = get_operational_settings()
    except Exception:
        settings = {}

    conn = get_connection()
    c = conn.cursor()

    # Query all P2P operations with ARS amounts from DB (excluding bank statement rows and ARS ledger)
    c.execute("""
        SELECT tx_hash, fecha, exchange, tipo_operacion, monto_compra_cripto,
               monto_venta_cripto, cotizacion_compra, cotizacion_venta, monto_ars, comentarios
        FROM transactions
        WHERE monto_ars > 0 AND monto_ars IS NOT NULL
          AND COALESCE(source, '') NOT IN ('BANK_STATEMENT', 'CERTIFICATION')
          AND UPPER(TRIM(moneda)) != 'ARS'
        ORDER BY fecha ASC
    """)
    db_p2p = c.fetchall()
    conn.close()

    p2p_orders = []
    for r in db_p2p:
        h, f, ex, tipo, mc, mv, cc, cv, m_ars, com = r
        # P2P orders in transactions table have UTC timestamps: convert to Argentine local time for matching
        p2p_dt = _parse_to_arg_tz(f, assume_utc=True)
        is_buy = any(k in str(tipo).lower() for k in ['compra', 'buy']) or (mc and mc > 0 and (not mv or mv == 0))
        p2p_orders.append({
            "tx_hash": h,
            "raw_fecha": f,
            "dt": p2p_dt,
            "exchange": ex,
            "tipo": 'COMPRA' if is_buy else 'VENTA',
            "monto_ars": float(m_ars or 0.0),
            "comentarios": str(com or '').lower(),
            "matched": False
        })

    raw_names = user_names if user_names is not None else settings.get('owner_names', ['titular', 'cuenta demo'])
    raw_cuits = user_cuits if user_cuits is not None else settings.get('owner_cuits', ['20000000001'])
    raw_op_accs = operational_accounts if operational_accounts is not None else settings.get(
        'operational_accounts', ['mercado pago', 'mercadopago', 'lemon', 'lemon cash', 'fiwind', 'ripio', 'binance']
    )
    raw_pers_accs = personal_external_accounts if personal_external_accounts is not None else settings.get(
        'personal_external_accounts',
        ['galicia', 'santander', 'bbva', 'macro', 'nacion', 'nación', 'hsbc', 'patagonia', 'icbc', 'credicoop', 'provincia', 'ciudad', 'cuenta personal', 'ahorro', 'sueldo']
    )
    threshold_ars = float(
        personal_expense_threshold_ars
        if personal_expense_threshold_ars is not None
        else settings.get('personal_expense_threshold_ars', 25000.0)
    )

    owner_names = [str(n).lower().strip() for n in raw_names if str(n).strip()]
    owner_cuits = [re.sub(r'\D', '', str(c)) for c in raw_cuits if str(c).strip()]
    op_accounts_kw = [str(a).lower().strip() for a in raw_op_accs if str(a).strip()]
    pers_accounts_kw = [str(a).lower().strip() for a in raw_pers_accs if str(a).strip()]

    matched_results = []
    pending_review = []
    used_p2p_hashes = set()

    for b in bank_txs:
        if not b.tx_hash:
            b.tx_hash = compute_bank_tx_hash(b)
        b_dt = _parse_to_arg_tz(b.fecha, assume_utc=False)
        b_amt = float(b.monto_ars)
        b_desc = str(b.descripcion or '').lower()
        b_titular = str(b.titular_contraparte or '').lower()
        b_cuit = re.sub(r'\D', '', str(b.cuit_contraparte or ''))
        combined_text = f"{b_desc} {b_titular}".strip()

        # ----------------------------------------------------
        # Tier 1: Passive Yields / Interest auto-categorization (requires CREDITO)
        # ----------------------------------------------------
        if b.tipo_movimiento == 'CREDITO' and any(k in b_desc for k in ['rendimiento', 'mercadofondo', 'lemon earn', 'interes', 'interés', 'inversion', 'fci']):
            b.categoria = 'RENDIMIENTO'
            b.nota_auditoria = 'Interés / Rendimiento FCI autodetectado.'
            matched_results.append(b)
            continue

        # ----------------------------------------------------
        # Tier 2: Own Accounts (Operational Pass-through vs External Personal Withdrawal/Injection)
        # ----------------------------------------------------
        is_own_account = False
        if any(name in b_desc or name in b_titular for name in owner_names):
            is_own_account = True
        if b_cuit and b_cuit in owner_cuits:
            is_own_account = True
        if any(k in b_desc for k in ['transferencia entre cuentas propias', 'extraccion propia', 'debito cuenta propia', 'cuenta propia']):
            is_own_account = True

        if is_own_account:
            matches_personal_external = any(pk in combined_text for pk in pers_accounts_kw)
            matches_operational = any(ok in combined_text for ok in op_accounts_kw)

            if matches_personal_external and not matches_operational:
                if b.tipo_movimiento == 'DEBITO':
                    b.categoria = 'RETIRO'
                    b.subtipo_cuenta_propia = 'PERSONAL_EXTERNA'
                    b.nota_auditoria = 'Retiro desde cuenta de arbitraje hacia cuenta personal externa propia.'
                else:
                    b.categoria = 'INYECCION'
                    b.subtipo_cuenta_propia = 'PERSONAL_EXTERNA'
                    b.nota_auditoria = 'Inyección de capital desde cuenta personal externa propia hacia arbitraje.'
            else:
                b.categoria = 'PASE_PROPIO'
                b.subtipo_cuenta_propia = 'OPERATIVA'
                b.nota_auditoria = 'Transferencia interna entre cuentas operativas propias (Pasaplatos neutro).'
            matched_results.append(b)
            continue

        # ----------------------------------------------------
        # Tier 3: Deterministic cross-matching with P2P Orders
        # ----------------------------------------------------
        found_p2p = None
        target_p2p_type = 'COMPRA' if b.tipo_movimiento == 'DEBITO' else 'VENTA'

        if b_dt:
            # Candidate window: ±45 minutes
            for p in p2p_orders:
                if p['tx_hash'] in used_p2p_hashes:
                    continue
                if p['tipo'] != target_p2p_type:
                    continue
                if abs(p['monto_ars'] - b_amt) > 1.0:
                    continue
                if p['dt']:
                    diff_minutes = abs((p['dt'] - b_dt).total_seconds()) / 60.0
                    if diff_minutes <= 45.0:
                        found_p2p = p
                        break

            # Secondary pass: if exact amount within ±3 hours
            if not found_p2p:
                for p in p2p_orders:
                    if p['tx_hash'] in used_p2p_hashes:
                        continue
                    if p['tipo'] != target_p2p_type:
                        continue
                    if abs(p['monto_ars'] - b_amt) <= 0.05 and p['dt']:
                        diff_min = abs((p['dt'] - b_dt).total_seconds()) / 60.0
                        if diff_min <= 180.0:
                            found_p2p = p
                            break

        if found_p2p:
            b.categoria = 'P2P_MATCHED'
            b.matched_tx_id = found_p2p['tx_hash']
            b.nota_auditoria = f"Conciliado con orden P2P ({found_p2p['exchange']})."
            used_p2p_hashes.add(found_p2p['tx_hash'])
            matched_results.append(b)
            continue

        # ----------------------------------------------------
        # Tier 4: Arbitrage Bank Taxes & Fees vs Tax Retentions (SIRCREB)
        # ----------------------------------------------------
        is_tax_retention = any(k in b_desc for k in TAX_RETENTION_KEYWORDS)
        if b.tipo_movimiento == 'DEBITO' and is_tax_retention:
            b.categoria = 'RETENCION_NO_RECONOCIDA'
            b.nota_auditoria = 'Retención impositiva bancaria (SIRCREB / IIBB / Rentas). No forma parte del giro; verificar apelación o solicitud de repetición.'
            pending_review.append(b)
            continue

        is_arbitrage_expense = any(k in b_desc for k in ARBITRAGE_BANK_EXPENSE_KEYWORDS)
        if b.tipo_movimiento == 'DEBITO' and is_arbitrage_expense:
            b.categoria = 'GASTO_ARBITRAJE'
            b.nota_auditoria = 'Impuesto Ley 25.413 / Mantenimiento de cuenta bancaria.'
            matched_results.append(b)
            continue

        # ----------------------------------------------------
        # Tier 5: Personal Expense Heuristics vs Pending Outlier
        # ----------------------------------------------------
        is_commercial = _matches_commercial_keyword(b_desc)

        if b.tipo_movimiento == 'DEBITO' and (is_commercial or b_amt < threshold_ars):
            b.categoria = 'GASTO_PERSONAL'
            b.nota_auditoria = 'Gasto común / consumo personal autodetectado (Se imputa como Retiro Personal).'
            matched_results.append(b)
        else:
            b.categoria = 'PENDIENTE'
            b.nota_auditoria = 'Movimiento huérfano. Requiere clasificación manual (¿Préstamo, Inyección, Retiro o P2P?).'
            pending_review.append(b)

    total_count = len(bank_txs)
    auto_count = len(matched_results)
    recon_rate = round((auto_count / total_count * 100.0), 1) if total_count > 0 else 100.0

    # Breakdown by category
    category_counts: Dict[str, int] = {}
    for item in matched_results + pending_review:
        cat_key = item.categoria or 'PENDIENTE'
        category_counts[cat_key] = category_counts.get(cat_key, 0) + 1

    return {
        "matched": matched_results,
        "pending": pending_review,
        "summary": {
            "total_movements": total_count,
            "auto_reconciled": auto_count,
            "pending_count": len(pending_review),
            "reconciliation_rate_pct": recon_rate,
            "by_category": category_counts
        }
    }


reconcile_bank_batch = reconcile_bank_movements
reconcile_bank_Batch = reconcile_bank_movements
