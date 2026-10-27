import logging
import re
from datetime import datetime
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_USD_ARS: float = 1000.0

CRYPTO_REF_PRICES_USD = {
    'EUR': 1.08, 'USD': 1.0, 'USDT': 1.0, 'USDC': 1.0, 'DAI': 1.0, 'BUSD': 1.0,
    'BTC': 60000.0, 'ETH': 3000.0, 'SOL': 150.0, 'BNB': 600.0, 'XRP': 0.6, 'ADA': 0.5, 'DOT': 7.0, 'AVAX': 30.0, 'LINK': 15.0
}
LAST_STATIC_FALLBACK_COINS = set()

_SPANISH_MONTHS_DICT = {
    'ene': 'jan', 'enero': 'january', 'feb': 'feb', 'febrero': 'february', 'mar': 'mar', 'marzo': 'march',
    'abr': 'apr', 'abril': 'april', 'may': 'may', 'mayo': 'may', 'jun': 'jun', 'junio': 'june',
    'jul': 'jul', 'julio': 'july', 'ago': 'aug', 'agosto': 'august', 'sep': 'sep', 'sept': 'sep',
    'septiembre': 'september', 'set': 'sep', 'setiembre': 'september', 'oct': 'oct', 'octubre': 'october',
    'nov': 'nov', 'noviembre': 'november', 'dic': 'dec', 'diciembre': 'december'
}


def _extract_year_safe(f_val):
    if f_val is None:
        return None
    parsed_f = getattr(f_val, 'year', None)
    if parsed_f:
        return int(parsed_f)
    f_str = str(f_val).strip()
    if not f_str or f_str.lower() in ('nan', 'none', 'nat'):
        return None
    if len(f_str) >= 4 and f_str[:4].isdigit():
        return int(f_str[:4])
    f_norm = re.sub(
        r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sept|sep|set|oct|nov|dic)\b',
        lambda m: _SPANISH_MONTHS_DICT.get(m.group(0).lower(), m.group(0)), f_str, flags=re.IGNORECASE
    )
    dayfirst = not bool(re.match(r'^\d{4}', f_norm))
    parsed_ts = pd.to_datetime(f_norm, dayfirst=dayfirst, errors='coerce')
    return int(parsed_ts.year) if pd.notna(parsed_ts) else None


def _is_valid_quote_row(cand_coin, rate, db_fecha, m_compra, m_venta, m_ars, fecha_val):
    if not rate or rate <= 0:
        return False
    m_crypto = m_compra if (m_compra and m_compra > 0) else m_venta
    if m_crypto and m_ars and m_crypto > 0 and m_ars > 0:
        implied = m_ars / m_crypto
        if abs(rate - implied) / max(rate, implied) > 0.8:
            return False
    from services.tax_service import get_tax_settings
    y = _extract_year_safe(fecha_val) or _extract_year_safe(db_fecha) or datetime.now().year
    try:
        usd_ars = get_tax_settings(y).get('usd_ars_exchange_rate', DEFAULT_FALLBACK_USD_ARS)
    except Exception:
        usd_ars = DEFAULT_FALLBACK_USD_ARS
    usd_p = rate / (usd_ars if usd_ars > 0 else DEFAULT_FALLBACK_USD_ARS)
    if cand_coin in CRYPTO_REF_PRICES_USD:
        ref = CRYPTO_REF_PRICES_USD[cand_coin]
        if usd_p < ref * 0.05 or usd_p > ref * 20.0:
            return False
    return True


def get_recent_historical_price(cand_coin: str, fecha=None) -> Optional[float]:
    """Queries DB for recent historical quote in USD for a given coin around fecha."""
    if not cand_coin or cand_coin in ('ARS', 'USD', 'NONE', ''):
        return None
    conn = None
    try:
        from db.connection import get_connection
        conn = get_connection()
        c = conn.cursor()
        base_q = (
            "SELECT cotizacion_compra, cotizacion_venta, fecha, monto_compra_cripto, monto_venta_cripto, monto_ars "
            "FROM transactions WHERE moneda = ? {date_cond} AND (cotizacion_compra > 0 OR cotizacion_venta > 0) "
            "AND (monto_compra_cripto > 0 OR monto_venta_cripto > 0) AND monto_ars > 0 "
            "AND (requires_cost_audit IS NULL OR requires_cost_audit = 0) "
            "AND (exchange != 'Sistema de Conciliación' AND tipo_operacion != 'Ingreso Automático') "
            "ORDER BY fecha {order_dir} LIMIT 5"
        )
        c.execute(base_q.format(date_cond="AND fecha <= ?", order_dir="DESC"), (cand_coin, str(fecha)))
        rows = c.fetchall()
        if not rows:
            c.execute(base_q.format(date_cond="", order_dir="ASC"), (cand_coin,))
            rows = c.fetchall()
        for row in rows:
            rate = row[0] or row[1]
            db_fecha, m_compra, m_venta, m_ars = row[2], row[3], row[4], row[5]
            if _is_valid_quote_row(cand_coin, rate, db_fecha, m_compra, m_venta, m_ars, fecha):
                from services.tax_service import get_tax_settings
                y = _extract_year_safe(fecha) or _extract_year_safe(db_fecha) or datetime.now().year
                usd_ars = get_tax_settings(y).get('usd_ars_exchange_rate', DEFAULT_FALLBACK_USD_ARS)
                return rate / (usd_ars if usd_ars > 0 else DEFAULT_FALLBACK_USD_ARS)
    except Exception as e:
        logger.warning(f"Error querying historical price from DB for {cand_coin}: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    return None


def get_latest_known_price(cand_coin: str, fecha=None) -> Optional[float]:
    """Queries DB for the latest known quote in USD for a given coin."""
    if not cand_coin or cand_coin in ('ARS', 'USD', 'NONE', ''):
        return None
    conn = None
    try:
        from db.connection import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT cotizacion_compra, cotizacion_venta, fecha, monto_compra_cripto, monto_venta_cripto, monto_ars "
            "FROM transactions WHERE moneda = ? AND (cotizacion_compra > 0 OR cotizacion_venta > 0) "
            "AND (monto_compra_cripto > 0 OR monto_venta_cripto > 0) AND monto_ars > 0 "
            "AND (requires_cost_audit IS NULL OR requires_cost_audit = 0) "
            "AND (exchange != 'Sistema de Conciliación' AND tipo_operacion != 'Ingreso Automático') "
            "ORDER BY fecha DESC LIMIT 5",
            (cand_coin,)
        )
        for row in c.fetchall():
            rate = row[0] or row[1]
            db_fecha, m_compra, m_venta, m_ars = row[2], row[3], row[4], row[5]
            if _is_valid_quote_row(cand_coin, rate, db_fecha, m_compra, m_venta, m_ars, fecha):
                try:
                    from services.tax_service import get_tax_settings
                    y = _extract_year_safe(fecha) or _extract_year_safe(db_fecha) or datetime.now().year
                    usd_ars = get_tax_settings(y).get('usd_ars_exchange_rate', DEFAULT_FALLBACK_USD_ARS)
                except Exception:
                    usd_ars = DEFAULT_FALLBACK_USD_ARS
                return rate / (usd_ars if usd_ars > 0 else DEFAULT_FALLBACK_USD_ARS)
    except Exception as e:
        logger.warning(f"Error querying latest known price from DB for {cand_coin}: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    return None


def get_quote_usd_value(quote_coin: str, quote_amount: float, base_coin: str = "", base_amount: float = 0.0, fecha=None) -> float:
    """Computes real USD value for multi-currency trading pairs, prioritizing historical DB prices."""
    q = str(quote_coin or "").upper().strip()
    b = str(base_coin or "").upper().strip()
    q_amt = float(quote_amount or 0.0)
    b_amt = float(base_amount or 0.0)

    if q in ('USD', 'USDT', 'USDC', 'DAI', 'BUSD', 'UXD'):
        return q_amt

    if fecha:
        for cand_coin in [q, b]:
            usd_p = get_recent_historical_price(cand_coin, fecha=fecha)
            if usd_p is not None:
                return (q_amt * usd_p) if cand_coin == q else (b_amt * usd_p)

    for cand_coin in [q, b]:
        usd_p = get_latest_known_price(cand_coin, fecha=fecha)
        if usd_p is not None:
            return (q_amt * usd_p) if cand_coin == q else (b_amt * usd_p)

    if q in CRYPTO_REF_PRICES_USD:
        LAST_STATIC_FALLBACK_COINS.add(q)
        logger.warning(f"Auditoría de costo requerida: cotización fija de referencia estática usada para {q} (${CRYPTO_REF_PRICES_USD[q]} USD) fecha={fecha}.")
        return q_amt * CRYPTO_REF_PRICES_USD[q]
    if b in CRYPTO_REF_PRICES_USD and b_amt > 0:
        LAST_STATIC_FALLBACK_COINS.add(b)
        logger.warning(f"Auditoría de costo requerida: cotización fija de referencia estática usada para base {b} (${CRYPTO_REF_PRICES_USD[b]} USD) fecha={fecha}.")
        return b_amt * CRYPTO_REF_PRICES_USD[b]

    FALLBACK_CRYPTO_REF_PRICES_USD = {
        'BTC': 60000.0, 'ETH': 3000.0, 'SOL': 150.0, 'BNB': 600.0, 'AVAX': 30.0, 'LINK': 15.0, 'DOT': 7.0,
        'XRP': 0.6, 'ADA': 0.5, 'MATIC': 0.5, 'POL': 0.5, 'LTC': 70.0, 'BCH': 350.0, 'DOGE': 0.1,
        'SHIB': 0.00002, 'TRX': 0.12, 'NEAR': 5.0, 'ATOM': 5.0, 'UNI': 7.0
    }
    if q in FALLBACK_CRYPTO_REF_PRICES_USD:
        LAST_STATIC_FALLBACK_COINS.add(q)
        logger.warning(f"Auditoría de costo requerida: cotización fija fallback estática usada para {q} (${FALLBACK_CRYPTO_REF_PRICES_USD[q]} USD) fecha={fecha}.")
        return q_amt * FALLBACK_CRYPTO_REF_PRICES_USD[q]
    if b in FALLBACK_CRYPTO_REF_PRICES_USD and b_amt > 0:
        LAST_STATIC_FALLBACK_COINS.add(b)
        logger.warning(f"Auditoría de costo requerida: cotización fija fallback estática usada para base {b} (${FALLBACK_CRYPTO_REF_PRICES_USD[b]} USD) fecha={fecha}.")
        return b_amt * FALLBACK_CRYPTO_REF_PRICES_USD[b]
    return 0.0
