"""
Normalización e higienización de datos crudos en la ingesta de extractos.
Aplica validación de columnas, limpieza numérica y conversión estricta a UTC.
Referencia de diseño: docs/contratos_io_transacciones.md
"""

import re, difflib, unicodedata, logging
from datetime import datetime, date, timezone
import pandas as pd
from .file_preview import extract_preview_columns

logger = logging.getLogger(__name__)
try:
    from services.config_service import load_config, get_date_format
    from utils.exceptions import MissingColumnsError
except ImportError:
    try:
        import config_manager
        from exceptions import MissingColumnsError
    except ImportError:
        from compat import config_manager  # type: ignore
        from compat.exceptions import MissingColumnsError  # type: ignore
    load_config, get_date_format = config_manager.load_config, config_manager.get_date_format

class _UTCDatetime(datetime):
    _is_explicit_utc = True

def _as_utc_dt(dt):
    return _UTCDatetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, getattr(dt, 'microsecond', 0))

def _normalize_text(s):
    """Lowercases, strips whitespace/BOM, and removes accents/diacritics."""
    if s is None:
        return ""
    s = unicodedata.normalize('NFKD', str(s).replace('\ufeff', '').strip().lower())
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return s.replace('_', ' ').replace('-', ' ').strip()

_NEGATIVE_STATUS_KEYWORDS = (
    'cancel', 'rechaz', 'reject', 'fallid', 'fail', 'expir', 'incomplet', 'incomplete', 'error', 'devuel', 'refund',
    'pendiente', 'pending', 'progres', 'progress', 'esperando', 'waiting', 'apelaci', 'appeal', 'disput', 'en curso',
    'anulad', 'anulado', 'anulada', 'invalid', 'void', 'denied'
)
_NEGATIVE_STATUS_REGEX = re.compile(
    r'\b(cancel\w*|rechaz\w*|reject\w*|fallid\w*|fail\w*|expir\w*|incomplet\w*|error\w*|devuel\w*|refund\w*|'
    r'pendient\w*|pending|progres\w*|esperando|waiting|apelaci\w*|appeal\w*|disput\w*|en\s+curso|anulad\w*|invalid\w*|void\w*|denied)\b',
    re.IGNORECASE
)
_FIAT_USD_RATES = {'USD': 1.0, 'EUR': 1.08, 'BRL': 0.18, 'UYU': 0.024, 'CLP': 0.00105, 'COP': 0.00024, 'MXN': 0.05, 'PEN': 0.27, 'GBP': 1.27}

def get_fiat_usd_rate(fiat_code: str) -> float:
    return _FIAT_USD_RATES.get(str(fiat_code or '').upper().strip(), 1.0)

def get_usd_ars_rate(fecha=None):
    try:
        from services.tax_service import get_tax_settings
        from models.transaction_models import _extract_year_safe
        y = getattr(fecha, 'year', None) or _extract_year_safe(fecha) or 2025
        settings = get_tax_settings(y)
        rate = float(settings.get('usd_ars_exchange_rate', 1000.0) or 1000.0)
        if rate == 1000.0 and (not settings or 'usd_ars_exchange_rate' not in settings):
            logger.warning(f"get_usd_ars_rate: Sin cotización configurada para año {y} (fecha={fecha}). Usando fallback 1000.0")
        return rate
    except Exception as e:
        logger.warning(f"get_usd_ars_rate: Fallo al obtener cotización USD/ARS para fecha={fecha}: {e}. Usando fallback 1000.0")
        return 1000.0

KEY_CANDIDATES = {
    'fecha': ['fecha', 'date', 'datetime', 'fecha/hora', 'created_at', 'timestamp', 'time'],
    'tipo': ['tipo', 'type', 'operacion', 'operación', 'action', 'transaction type'],
    'moneda': ['moneda', 'currency', 'moneda_destino', 'asset', 'destino', 'symbol', 'coin'],
    'moneda_origen': ['moneda_origen', 'moneda origen', 'source_currency', 'origen', 'from_currency', 'source asset'],
    'monto': ['monto', 'amount', 'monto_destino', 'monto destino', 'quantity', 'total'],
    'monto_origen': ['monto_origen', 'monto origen', 'source_amount', 'monto_inicial', 'source quantity'],
    'precio': ['precio', 'price', 'rate', 'cotizacion', 'cotización', 'unit price'],
    'codigo_operacion': ['codigo_operacion', 'codigo de operacion', 'order_id', 'id_operacion', 'order id', 'txid', 'id']
}

def find_column_fuzzy(df, candidates, cutoff=0.8):
    """Finds the best matching column in a DataFrame (Exact -> Substring/Token -> Fuzzy ratio)."""
    if df is None or len(df.columns) == 0 or not candidates:
        return None
    df_cols = list(df.columns)
    norm_cols = [_normalize_text(c) for c in df_cols]
    norm_candidates = [_normalize_text(c) for c in candidates if c]
    for cand in norm_candidates:
        for idx, norm_col in enumerate(norm_cols):
            if norm_col == cand:
                return df_cols[idx]
    for cand in norm_candidates:
        if len(cand) < 3:
            continue
        cand_tokens = set(cand.split())
        for idx, norm_col in enumerate(norm_cols):
            if norm_col and (cand in norm_col or (len(norm_col) >= 4 and norm_col in cand) or (cand_tokens and cand_tokens.issubset(set(norm_col.split())))):
                return df_cols[idx]
    best_match, best_score = None, 0.0
    for cand in norm_candidates:
        if len(cand) < 3:
            continue
        for idx, norm_col in enumerate(norm_cols):
            if norm_col:
                ratio = difflib.SequenceMatcher(None, cand, norm_col).ratio()
                if ratio > best_score and ratio >= cutoff:
                    best_score, best_match = ratio, df_cols[idx]
    return best_match

def validate_columns(df, exchange):
    """Checks if critical columns exist in the dataframe using fuzzy matching."""
    config = load_config()
    if exchange not in config:
        return
    missing = [
        f"{key} ('{col_name}')" for key, col_name in config[exchange]['columns'].items()
        if col_name and find_column_fuzzy(df, [col_name, key] + KEY_CANDIDATES.get(key, [])) is None
    ]
    if missing:
        raise MissingColumnsError(exchange, missing, [str(c)[:20] for c in df.columns])

def _normalize_tz_to_utc(dt_val, exchange=None):
    """Safely converts timezone-aware or naive Argentine datetime to naive UTC datetime."""
    if dt_val is None or pd.isna(dt_val):
        return dt_val
    if getattr(dt_val, 'tzinfo', None) is not None:
        try:
            dt = dt_val.tz_convert('UTC').tz_localize(None) if hasattr(dt_val, 'tz_convert') else dt_val.astimezone(timezone.utc).replace(tzinfo=None)
            return _as_utc_dt(dt)
        except Exception:
            return dt_val
    if exchange and any(k in str(exchange).lower() for k in ('bitso', 'ripio', 'fiwind', 'lemon', 'belo', 'buenbit', 'satoshitango')):
        try:
            return _as_utc_dt(dt_val + pd.Timedelta(hours=3))
        except Exception:
            pass
    return dt_val

_SPANISH_MONTHS_MAP = {
    'ene': 'jan', 'enero': 'january', 'feb': 'feb', 'febrero': 'february', 'mar': 'mar', 'marzo': 'march',
    'abr': 'apr', 'abril': 'april', 'may': 'may', 'mayo': 'may', 'jun': 'jun', 'junio': 'june',
    'jul': 'jul', 'julio': 'july', 'ago': 'aug', 'agosto': 'august', 'sep': 'sep', 'sept': 'sep',
    'septiembre': 'september', 'set': 'sep', 'setiembre': 'september', 'oct': 'oct', 'octubre': 'october',
    'nov': 'nov', 'noviembre': 'november', 'dic': 'dec', 'diciembre': 'december'
}

def _normalize_spanish_months_str(s: str) -> str:
    if not s or not isinstance(s, str):
        return s
    return re.sub(
        r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sept|sep|set|oct|nov|dic)\b',
        lambda m: _SPANISH_MONTHS_MAP.get(m.group(0).lower(), m.group(0)), s, flags=re.IGNORECASE
    )

def parse_date(date_str, exchange):
    """Parses date using configured format and structural date detection with resilient fallback."""
    if date_str is None or pd.isna(date_str):
        return None
    if isinstance(date_str, _UTCDatetime):
        return date_str
    if isinstance(date_str, (pd.Timestamp, datetime, date)):
        res = pd.to_datetime(date_str)
        if getattr(res, 'tzinfo', None) is not None:
            return _normalize_tz_to_utc(res, exchange)
        is_ar_ex = exchange and any(k in str(exchange).lower() for k in ('bitso', 'ripio', 'fiwind', 'lemon', 'belo', 'buenbit', 'satoshitango'))
        if is_ar_ex:
            return _as_utc_dt(res + pd.Timedelta(hours=3))
        return res
    s = str(date_str).strip()
    if not s or s.lower() in ('nan', 'nat', 'none', 'null', ''):
        return None
    s = re.sub(r'\b(?:ART|UTC-0?3(?::00)?|GMT-0?3(?::00)?)\b', '-03:00', s, flags=re.I).strip()
    s = _normalize_spanish_months_str(s)
    has_tz = bool(re.search(r'(?:Z$|Z\b|(?:\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?\s*(?:Z|[+-]\d{2}(?::?\d{2})?))\b|\b(?:ART|UTC|GMT)\b)', s, re.I))

    def _finish(parsed):
        if parsed is None or pd.isna(parsed):
            return None
        is_ar_ex = exchange and any(k in str(exchange).lower() for k in ('bitso', 'ripio', 'fiwind', 'lemon', 'belo', 'buenbit', 'satoshitango'))
        if has_tz or getattr(parsed, 'tzinfo', None) is not None:
            res = _normalize_tz_to_utc(parsed, exchange)
            return res if isinstance(res, _UTCDatetime) else _as_utc_dt(res)
        if is_ar_ex:
            return _as_utc_dt(parsed + pd.Timedelta(hours=3))
        return parsed

    ex_key = str(exchange).lower().strip().replace(' ', '_') if exchange else ''
    for k_sub, k_norm in (('bitso', 'bitso'), ('ripio', 'ripio_trade'), ('p2p', 'binance_p2p'), ('binance', 'binance_spot'), ('fiwind', 'fiwind')):
        if k_sub in ex_key:
            ex_key = k_norm
            break
    fmt = (get_date_format(ex_key) if ex_key else '') or (get_date_format(str(exchange).strip()) if exchange else '')
    if fmt:
        try:
            parsed = pd.to_datetime(s, format=fmt)
            if not pd.isna(parsed):
                return _finish(parsed)
        except Exception:
            pass
    if isinstance(date_str, (int, float)) or (s.isdigit() and len(s) in (10, 13, 16)):
        try:
            val = int(date_str) if isinstance(date_str, (int, float)) else int(s)
            unit = 's' if len(str(val)) == 10 else ('ms' if len(str(val)) == 13 else 'us')
            return _normalize_tz_to_utc(pd.to_datetime(val, unit=unit, utc=True), exchange)
        except Exception:
            pass
    clean_s = s[:19].replace('T', ' ')
    if len(clean_s) >= 4 and clean_s[:4].isdigit() and (len(clean_s) == 4 or clean_s[4] in ('-', '/', ' ', 'T')):
        for target_s, u_flag in ((s, has_tz), (clean_s, False)):
            try:
                parsed = pd.to_datetime(target_s, dayfirst=False, errors='coerce', utc=u_flag)
                if not pd.isna(parsed):
                    return _finish(parsed)
            except Exception:
                pass
    date_part = s.split(' ')[0].split('T')[0]
    parts = [p for p in re.split(r'[-/]', date_part) if p]
    if len(parts) >= 3 and len(parts[-1]) == 4 and parts[-1].isdigit() and parts[0].isdigit() and parts[1].isdigit():
        p0, p1 = int(parts[0]), int(parts[1])
        is_ar_ex = exchange and any(k in str(exchange).lower() for k in ('bitso', 'ripio', 'fiwind', 'lemon', 'belo', 'buenbit', 'satoshitango'))
        is_us_ex = exchange and any(k in str(exchange).lower() for k in ('kraken', 'bybit', 'coinbase', 'okx'))
        df_opt = True if is_ar_ex else (False if is_us_ex else (False if p1 > 12 and p0 <= 12 else (True if p0 > 12 and p1 <= 12 else ('/' in s or len(parts[0]) <= 2))))
        try:
            parsed = pd.to_datetime(s, dayfirst=df_opt, errors='coerce', utc=has_tz)
            if not pd.isna(parsed):
                return _finish(parsed)
        except Exception:
            pass
    for df_opt in (True, False):
        try:
            parsed = pd.to_datetime(s, dayfirst=df_opt, errors='coerce', utc=has_tz)
            if not pd.isna(parsed):
                return _finish(parsed)
        except Exception:
            pass
    logger.warning(f"Date Parse Error: '{date_str}' could not be parsed for {exchange}. Row will be skipped.")
    return None

def clean_decimal(val):
    if isinstance(val, (int, float)):
        return float(val)
    if pd.isna(val) or not str(val).strip():
        return 0.0
    s = str(val).strip()
    sci_m = re.search(r'^[+-]?\d+(?:[.,]\d+)?[eE][+-]?\d+$', s)
    if sci_m:
        return float(sci_m.group(0).replace(',', '.'))
    s = re.sub(r'[^\d.,\-+]', '', s).strip()
    if not s:
        return 0.0
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.') if s.rfind(',') > s.rfind('.') else s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except Exception as e:
        try:
            return float(s.replace('.', ''))
        except Exception as e2:
            logging.getLogger(__name__).warning(f"clean_decimal: Error parseando decimal '{val}': {e} / {e2}")
            return 0.0

def limpiar_numero_binance(valor):
    """Convierte '20USDT' -> 20.0 (float) con soporte completo para separador de miles y notación científica."""
    if pd.isna(valor) or str(valor).strip() == '':
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    val_str = str(valor).strip().replace(',', '')
    sci_m = re.search(r'[+-]?\d+(?:\.\d+)?[eE][+-]?\d+', val_str)
    return clean_decimal(sci_m.group(0)) if sci_m else clean_decimal(re.sub(r'[^\d.\-+]', '', val_str).strip())

def is_cancelled_transaction(row):
    """Scans row for any status column and returns True if cancelled, rejected, etc."""
    status_keywords = {'estado', 'status', 'state', 'resultado', 'result', 'condicion', 'condition', 'situacion', 'situación', 'etapa', 'outcome', 'estatus', 'condición'}
    cols = row.keys() if hasattr(row, 'keys') else getattr(row, 'index', [])
    for col in cols:
        if any(kw in _normalize_text(col) for kw in status_keywords):
            val_str = _normalize_text(row[col])
            if not val_str:
                continue
            val_cleaned = re.sub(
                r'\b(sin|no|without)\s+(error|errors|rechazo|rechazos|rechaz\w*|disputa|disputas|disput\w*|fallo|fallos|cancellation|cancellations|anulacion|anulaciones|pendiente|pendientes|pending)\b|'
                r'\brefund\s*[:=\s]*n/?a\b|\brefund\s*[:=\s]*none\b|\bno\s+refund\b|\bwithout\s+refund\b|'
                r'\b(dispute\s+resolved|disputa\s+resuelta|error\s+resuelto|error\s+corregido|error\s+solucionado)\b',
                '', val_str, flags=re.IGNORECASE
            )
            if _NEGATIVE_STATUS_REGEX.search(val_cleaned):
                return True
    return False

def normalize_exchange_name(ex_name):
    if not ex_name or not str(ex_name).strip():
        return 'Otros'
    clean, clean_upper = str(ex_name).strip(), str(ex_name).strip().upper()
    if clean_upper in ('NONE', 'NAN', 'NULL', ''):
        return 'Otros'
    if 'BINANCE P2P' in clean_upper or 'BINANCE_P2P' in clean_upper:
        return 'Binance P2P'
    if 'BINANCE' in clean_upper:
        return 'Binance Spot' if ('SPOT' in clean_upper or clean_upper == 'BINANCE') else 'Binance P2P'
    if 'BITSO' in clean_upper:
        return 'Bitso Alpha' if 'ALPHA' in clean_upper else 'Bitso'
    if 'FIWIND' in clean_upper:
        return 'Fiwind'
    if 'RIPIO TRADE' in clean_upper or 'RIPIO_TRADE' in clean_upper or 'RIPIO (CSV)' in clean_upper:
        return 'Ripio Trade'
    if 'RIPIO CLASSIC' in clean_upper or 'RIPIO_CLASSIC' in clean_upper or clean_upper == 'RIPIO':
        return 'Ripio Classic'
    if 'LEMON' in clean_upper:
        return 'Lemon Cash'
    if 'BITGET' in clean_upper:
        return 'Bitget Spot' if 'SPOT' in clean_upper else ('Bitget P2P' if 'P2P' in clean_upper else 'Bitget')
    if 'OKX' in clean_upper or 'BYBIT' in clean_upper:
        return 'OKX' if 'OKX' in clean_upper else 'Bybit'
    return clean.title() if clean.isupper() or clean.islower() else clean

def create_transaction(fecha, exchange, tipo_op, moneda, m_compra, m_venta, cot_compra, cot_venta, m_ars, comentario="", unique_id=None):
    from models.transaction_models import compute_canonical_tx_hash
    exchange = normalize_exchange_name(exchange)
    ex_str = str(exchange).strip() if exchange is not None else ''
    exchange_name = 'Otros' if (not ex_str or ex_str.lower() in ('nan', 'none', 'null', '')) else ex_str
    if fecha is None or pd.isna(fecha):
        logger.warning(f"create_transaction [{exchange_name}]: fecha is None or NaN, row skipped.")
        return None
    is_explicit_utc = False
    if isinstance(fecha, (pd.Timestamp, datetime, date)):
        if getattr(fecha, 'tzinfo', None) is not None or getattr(fecha, '_is_explicit_utc', False):
            is_explicit_utc = True
            dt_norm = _normalize_tz_to_utc(pd.to_datetime(fecha)) if getattr(fecha, 'tzinfo', None) is not None else fecha
            fecha_fmt = dt_norm.strftime('%Y-%m-%d %H:%M:%S')
        else:
            fecha_fmt = pd.to_datetime(fecha).strftime('%Y-%m-%d %H:%M:%S')
    else:
        try:
            s_fecha = str(fecha).strip()
            if not s_fecha or s_fecha.lower() in ('nan', 'nat', 'none', 'null', ''):
                logger.warning(f"create_transaction [{exchange_name}]: Empty date '{fecha}', row skipped.")
                return None
            if bool(re.search(r'(?:Z$|Z\b|(?:\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?\s*(?:Z|[+-]\d{2}(?::?\d{2})?))\b|\b(?:ART|UTC|GMT)\b)', s_fecha, re.I)):
                is_explicit_utc = True
            parsed_dt = parse_date(s_fecha, exchange_name)
            if getattr(parsed_dt, '_is_explicit_utc', False):
                is_explicit_utc = True
            if parsed_dt is None:
                parsed_dt = pd.to_datetime(s_fecha[:19].replace('T', ' '), errors='coerce')
            if parsed_dt is not None and not pd.isna(parsed_dt):
                fecha_fmt = parsed_dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                logger.warning(f"create_transaction [{exchange_name}]: Could not parse date '{fecha}', row skipped.")
                return None
        except Exception as e:
            logger.warning(f"create_transaction [{exchange_name}]: Exception parsing date '{fecha}': {e}, row skipped.")
            return None
    if unique_id is not None and str(unique_id).strip() not in ('', 'nan', 'none', 'null'):
        u_str = str(unique_id).strip()
        base_id = u_str.rsplit('_', 1)[0] if '_' in u_str else u_str
        if f"ID: {u_str}" not in str(comentario):
            if f"ID: {base_id}" in str(comentario):
                comentario = re.sub(r'\|\s*ID:\s*' + re.escape(base_id) + r'\b', f'| ID: {u_str}', str(comentario))
                comentario = re.sub(r'\bID:\s*' + re.escape(base_id) + r'\b', f'ID: {u_str}', str(comentario))
            elif u_str not in str(comentario):
                comentario = f"{comentario} | ID: {u_str}" if comentario else f"ID: {u_str}"
        ref = comentario
    else:
        ref = str(comentario)
    m_compra = float(round(m_compra, 16)) if m_compra and m_compra > 0 else 0.0
    m_venta = float(round(m_venta, 16)) if m_venta and m_venta > 0 else 0.0
    m_ars_clean = float(round(abs(m_ars), 2)) if m_ars else 0.0
    hash_date = f"{fecha_fmt}Z" if is_explicit_utc else fecha_fmt
    tx_hash = compute_canonical_tx_hash(hash_date, exchange_name, tipo_op, moneda, monto_compra=m_compra, monto_venta=m_venta, monto_ars=m_ars_clean, unique_ref=ref)
    return {
        'Fecha': fecha_fmt, 'Exchange': exchange_name, 'Tipo de Operación': tipo_op, 'Moneda': moneda,
        'Monto Compra (Cripto)': m_compra, 'Monto Venta (Cripto)': m_venta,
        'Cotización Compra': float(round(cot_compra, 2)) if cot_compra > 0 else 0,
        'Cotización Venta': float(round(cot_venta, 2)) if cot_venta > 0 else 0,
        'Monto ARS': m_ars_clean, 'Comentarios': comentario, 'tx_hash': tx_hash,
        '_is_utc': is_explicit_utc
    }

__all__ = ['_UTCDatetime', '_as_utc_dt', '_normalize_text', '_NEGATIVE_STATUS_KEYWORDS', '_NEGATIVE_STATUS_REGEX', '_FIAT_USD_RATES', 'get_fiat_usd_rate', 'get_usd_ars_rate', 'KEY_CANDIDATES', 'find_column_fuzzy', 'validate_columns', '_normalize_tz_to_utc', '_SPANISH_MONTHS_MAP', '_normalize_spanish_months_str', 'parse_date', 'clean_decimal', 'limpiar_numero_binance', 'is_cancelled_transaction', 'normalize_exchange_name', 'create_transaction', 'extract_preview_columns', 'load_config', 'get_date_format', 'MissingColumnsError']
