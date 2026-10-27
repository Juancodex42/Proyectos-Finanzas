import logging
from pydantic import BaseModel, Field, field_validator, model_validator, PrivateAttr
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Standard IEEE 754 precision tolerance for micro-crypto fractions (Satoshis / Wei)
CRYPTO_DUST_EPSILON: float = 1e-12

def get_canonical_exchange_root(ex_name: str) -> str:
    if not ex_name:
        return 'OTROS'
    ex_upper = str(ex_name).strip().upper()
    roots = ['BINANCE', 'BITSO', 'RIPIO', 'FIWIND', 'LEMON', 'BYBIT', 'OKX', 'BITGET', 'KUCOIN', 'COINBASE', 'KRAKEN', 'BINGX', 'GATE', 'BELO', 'SATOSHITANGO', 'LOCALBITCOINS', 'PAXFUL']
    for root in roots:
        if root in ex_upper:
            return root
    if 'MANUAL' in ex_upper or 'VARIOS' in ex_upper:
        return 'MANUAL'
    return ex_upper

def canonicalize_ticker(ticker: str) -> str:
    """
    Standardizes crypto tickers, stripping network or protocol suffixes:
    e.g. 'USDT-TRC20', 'USDT_TRX', 'USD₮', 'USDT (TRC20)', 'USDT-ERC20', 'USDT-BEP20' -> 'USDT'
    """
    if ticker is None:
        return ""
    import pandas as pd
    if pd.isna(ticker):
        return ""
    import re
    t = str(ticker).strip().upper()
    if not t or t in ('NONE', 'NAN', 'NULL', ''):
        return ""
    # Strip parentheses e.g. 'USDT (TRC20)', 'USDT(TRC20)', 'USDC (POLYGON)'
    clean_t = re.sub(r'\s*\((?:TRC20|ERC20|BEP20|TRX|BSC|POLYGON|POL|SOL|AVAX|ARB|OP|BTC|ETH|TON|BASE|SUI|NEAR|LINEA)\)$', '', t)
    # Strip dash/underscore suffixes e.g. 'USDT-TRC20', 'USDT_TRX'
    clean_t = re.sub(r'[-_](?:TRC20|ERC20|BEP20|TRX|BSC|POLYGON|POL|SOL|AVAX|ARB|OP|TON|BASE|SUI|NEAR|LINEA)$', '', clean_t)
    if clean_t in ('USD₮', 'USDT_TRX', 'USDTERC20', 'USDTTRC20', 'USDTBEP20', 'USDTTON', 'USDTBASE'):
        return 'USDT'
    if clean_t in ('USDC_POL', 'USDC_SOL', 'USDCPOLYGON', 'USDCERC20', 'USDCBASE'):
        return 'USDC'
    return clean_t

def extract_transfer_txid(comment: str) -> str:
    """Extracts a normalized blockchain or off-chain transaction ID / reference hash from a comment."""
    if not comment:
        return ""
    import re
    s = str(comment).strip()
    m_txid = re.search(r'(?:TXID|Hash|Ref)\s*:\s*(?:Off-chain\s+transfer\s+)?([a-zA-Z0-9_\-]+)', s, re.IGNORECASE)
    if m_txid:
        val = m_txid.group(1).strip().lower()
        if len(val) >= 6 and val not in ('none', 'null', 'nan', 'off-chain', 'transfer'):
            return val
    m_off = re.search(r'Off-chain\s+transfer\s+([a-zA-Z0-9_\-]+)', s, re.IGNORECASE)
    if m_off:
        return m_off.group(1).strip().lower()
    return ""

try:
    from services.price_lookup_service import (
        CRYPTO_REF_PRICES_USD,
        LAST_STATIC_FALLBACK_COINS,
        _SPANISH_MONTHS_DICT,
        _extract_year_safe,
        _is_valid_quote_row,
        get_recent_historical_price,
        get_latest_known_price,
        get_quote_usd_value,
    )
except ImportError:
    from ..services.price_lookup_service import (
        CRYPTO_REF_PRICES_USD,
        LAST_STATIC_FALLBACK_COINS,
        _SPANISH_MONTHS_DICT,
        _extract_year_safe,
        _is_valid_quote_row,
        get_recent_historical_price,
        get_latest_known_price,
        get_quote_usd_value,
    )

def compute_canonical_tx_hash(fecha_str: str, exchange: str, tipo_operacion: str, moneda: str, monto_compra: float = 0.0, monto_venta: float = 0.0, *args, unique_ref: str = "", **kwargs) -> str:
    """Computes a deterministic MD5 hash for a transaction."""
    monto_ars = kwargs.get('monto_ars', 0.0)
    if len(args) == 1:
        if isinstance(args[0], (int, float)):
            monto_ars = float(args[0])
        else:
            unique_ref = str(args[0])
    elif len(args) >= 2:
        if isinstance(args[0], (int, float)):
            monto_ars = float(args[0])
        if not unique_ref:
            unique_ref = str(args[1])

    import hashlib, re
    try:
        import pandas as pd
        f_raw = str(fecha_str).strip()
        f_raw = re.sub(
            r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sept|sep|set|oct|nov|dic)\b',
            lambda m: _SPANISH_MONTHS_DICT.get(m.group(0).lower(), m.group(0)), f_raw, flags=re.IGNORECASE
        )
        f_raw = re.sub(r'\s+de[l]?\s+', ' ', f_raw, flags=re.IGNORECASE)
        f_raw = re.sub(r'\b(?:ART|UTC-0?3(?::00)?|GMT-0?3(?::00)?)\b', '-03:00', f_raw, flags=re.I).strip()
        if f_raw.isdigit() and len(f_raw) in (10, 13, 16):
            unit = 's' if len(f_raw) == 10 else ('ms' if len(f_raw) == 13 else 'us')
            _parsed = pd.to_datetime(int(f_raw), unit=unit, utc=True)
        else:
            date_p = f_raw.split(' ')[0].split('T')[0]
            d_parts = [p for p in re.split(r'[-/]', date_p) if p]
            use_dayfirst = False
            if len(d_parts) >= 3 and len(d_parts[-1]) == 4 and d_parts[-1].isdigit() and d_parts[0].isdigit() and d_parts[1].isdigit():
                p0, p1 = int(d_parts[0]), int(d_parts[1])
                use_dayfirst = True if (p0 > 12 and p1 <= 12) else (False if (p1 > 12 and p0 <= 12) else (('/' in f_raw) or (len(d_parts[0]) <= 2)))
            elif '/' in f_raw and not (len(f_raw) >= 4 and f_raw[:4].isdigit()):
                use_dayfirst = True
            tz_pattern = re.compile(r'(?:Z$|Z\b|(?:\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?\s*(?:Z|[+-]\d{2}(?::?\d{2})?))\b|\b(?:UTC|GMT)\b)', re.I)
            has_tz_indicator = bool(tz_pattern.search(f_raw)) or bool(re.search(r'[+-]\d{2}:?\d{2}$', f_raw))
            _parsed = pd.to_datetime(f_raw, dayfirst=use_dayfirst, errors='coerce', utc=has_tz_indicator)
        if _parsed is not None and not pd.isna(_parsed):
            if hasattr(_parsed, 'tz_convert') and _parsed.tzinfo is not None:
                _parsed = _parsed.tz_convert('UTC').tz_localize(None)
            clean_fecha = _parsed.strftime('%Y-%m-%d %H:%M:%S')
        else:
            clean_fecha = f_raw[:19].replace('T', ' ')
    except Exception:
        clean_fecha = str(fecha_str).strip()[:19].replace('T', ' ')
        
    ex_root = get_canonical_exchange_root(exchange)
    tipo_upper = str(tipo_operacion).strip().upper()
    if any(k in tipo_upper for k in ['DEPOSITO', 'DEPÓSITO', 'INGRESO', 'DEPOSIT', 'RECEIVE', 'RECEPCION', 'RECEPCIÓN', 'ENTRADA', 'ABONO', 'INCOMING']):
        clean_tipo = 'DEPOSITO'
    elif any(k in tipo_upper for k in ['COMPRA', 'BUY']):
        clean_tipo = 'COMPRA'
    elif any(k in tipo_upper for k in ['RETIRO', 'ENVIO', 'ENVÍO', 'WITHDRAW', 'SEND', 'OUTGOING', 'SALIDA', 'EGRESO', 'EXTRACCION', 'EXTRACCIÓN']):
        clean_tipo = 'RETIRO'
    elif any(k in tipo_upper for k in ['VENTA', 'SELL', 'CONSUMO', 'PAGO', 'PAYMENT']):
        clean_tipo = 'VENTA'
    else:
        clean_tipo = tipo_upper
    clean_moneda = canonicalize_ticker(moneda)
    
    clean_ref = ""
    if unique_ref:
        ref_str = str(unique_ref).strip()
        # Strip noisy substrings: page numbers, fee annotations, certification labels
        ref_str = re.sub(r'\(?\s*p[áa]g(?:ina)?\.?\s*\d+\s*\)?', '', ref_str, flags=re.I)
        ref_str = re.sub(r'\bfee\s*:\s*[\d\.]+\s*(?:ars|usdt|usd|bnb|btc|eth)?\b', '', ref_str, flags=re.I)
        ref_str = re.sub(r'certificaci[óo]n\s+c\.?p\.?n\.?', '', ref_str, flags=re.I)
        ref_str = re.sub(r'\[ajuste\s+fifo[^\]]*\]', '', ref_str, flags=re.I)
        ref_str = re.sub(r'\[auditor[íi]a[^\]]*\]', '', ref_str, flags=re.I)
        
        noise_keywords = {
            'binance', 'bitso', 'ripio', 'fiwind', 'lemon', 'bybit', 'okx', 'bitget', 'otros',
            'spot', 'p2p', 'trade', 'compra', 'venta', 'ingreso', 'retiro', 'deposito', 'envio',
            'conversion', 'swap', 'order', 'orden', 'manual', 'id', 'de', 'on', 'en', 'la', 'el',
            'realizada', 'buy', 'sell', 'deposit', 'withdraw', 'transfer', 'send', 'payment', 'pago',
            'receive', 'fee', 'comision', 'comisión', 'fiat', 'crypto', 'cripto', 'ejecutada', 'bancaria'
        }
        # Require explicit separator (:#) or token containing at least one digit
        labeled_matches = re.findall(r'(?:\b(?:order\s*id|order\s*no\.?|trade\s*id|txid|tx_id|operaci[óo]n)\b\s*[:#]\s*|#\s*)([a-zA-Z0-9_\-]+)', ref_str, re.IGNORECASE)
        candidates = [t.lower() for t in labeled_matches if t.lower() not in noise_keywords]
        if not candidates:
            fallback_labeled = re.findall(r'\b(?:order|orden|trade|id|ref|txid)\s*[:#]?\s*((?=[a-zA-Z0-9_\-]*\d)[a-zA-Z0-9_\-]{4,})\b', ref_str, re.IGNORECASE)
            candidates = [t.lower() for t in fallback_labeled if t.lower() not in noise_keywords]
        if candidates:
            sub_cands = [c for c in candidates if '_' in c]
            clean_ref = sub_cands[0] if sub_cands else candidates[0]
        if not clean_ref:
            tokens = re.findall(r'\b((?=[a-zA-Z0-9_\-]*\d)[a-zA-Z0-9_\-]{4,}(?:_[a-z0-9]+)?)\b', ref_str)
            candidates = [t for t in tokens if t.lower() not in noise_keywords]
            if candidates:
                clean_ref = candidates[0].lower()
        if clean_ref:
            clean_ref = re.sub(r'[-_](?:[cv]|quote|dep|ret)$', '', clean_ref, flags=re.IGNORECASE)

    raw_str = f"{clean_fecha}_{ex_root}_{clean_tipo}_{clean_moneda}_{float(monto_compra or 0):.16f}_{float(monto_venta or 0):.16f}_{float(monto_ars or 0):.2f}_{clean_ref}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

class TransactionModel(BaseModel):
    """Standardized strict model for a single cryptocurrency operation."""
    _is_utc: bool = PrivateAttr(default=False)
    fecha: datetime = Field(..., description="Fecha exacta de la operación")
    exchange: str = Field(..., description="Nombre del Exchange (Ej: Binance, Fiwind, Ripio Trade)")
    tipo_operacion: str = Field(..., description="Compra, Venta, Ingreso Cripto, etc.")
    moneda: str = Field(default="", description="Símbolo de la criptomoneda principal")
    monto_compra_cripto: float = Field(default=0.0, ge=0, description="Cantidad adquirida (debe ser >= 0)")
    monto_venta_cripto: float = Field(default=0.0, ge=0, description="Cantidad entregada (debe ser >= 0)")
    cotizacion_compra: float = Field(default=0.0, ge=0, description="Precio unitario en ARS al comprar")
    cotizacion_venta: float = Field(default=0.0, ge=0, description="Precio unitario en ARS al vender")
    monto_ars: float = Field(default=0.0, description="Volumen total operado en pesos argentinos")
    comentarios: str = Field(default="", description="Referencia de origen o ID de operación")
    source: str = Field(default="EXCHANGE_API", description="Origen de la transacción")

    def __init__(self, **data):
        import re
        data.pop('tx_hash', None)
        raw_f_obj = data.get('fecha')
        raw_f = str(raw_f_obj or '').strip().upper()
        is_utc = bool(data.pop('is_utc', False) or data.pop('_is_utc', False))
        if raw_f_obj is not None:
            if getattr(raw_f_obj, 'tzinfo', None) is not None or getattr(raw_f_obj, '_is_explicit_utc', False):
                is_utc = True
            elif any(ind in raw_f for ind in ['Z', '+', 'UTC', 'GMT', 'ART']) or bool(re.search(r'[+-]\d{2}:?\d{2}$', raw_f)):
                is_utc = True
                if isinstance(raw_f_obj, str) and re.search(r'\b(?:ART|UTC-0?3(?::00)?|GMT-0?3(?::00)?)\b', raw_f_obj, re.I):
                    data['fecha'] = re.sub(r'\s*\b(?:ART|UTC-0?3(?::00)?|GMT-0?3(?::00)?)\b', '-03:00', raw_f_obj, flags=re.I)
        super().__init__(**data)
        if is_utc:
            self._is_utc = True

    @classmethod
    def from_dict(cls, data: dict) -> "TransactionModel":
        """Instantiates TransactionModel from a dictionary without mutating the caller's input dictionary."""
        d = dict(data)
        d.pop("tx_hash", None)
        key_map = {
            "Fecha": "fecha", "Exchange": "exchange", "Tipo de Operación": "tipo_operacion",
            "Moneda": "moneda", "Monto Compra (Cripto)": "monto_compra_cripto",
            "Monto Venta (Cripto)": "monto_venta_cripto", "Cotización Compra": "cotizacion_compra",
            "Cotización Venta": "cotizacion_venta", "Monto ARS": "monto_ars", "Comentarios": "comentarios"
        }
        for k_legacy, k_field in key_map.items():
            if k_legacy in d and k_field not in d:
                d[k_field] = d.pop(k_legacy)
        return cls(**d)

    @field_validator('fecha')
    @classmethod
    def normalize_fecha(cls, v: datetime) -> datetime:
        """Convert timezone-aware datetime to naive UTC datetime."""
        if v is not None and getattr(v, 'tzinfo', None) is not None:
            from datetime import timezone
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v

    @field_validator('moneda')
    @classmethod
    def clean_moneda(cls, v: str) -> str:
        """Ensure currency symbol is always uppercase, sanitized, and stripped of network suffixes."""
        return canonicalize_ticker(v) if v else ""
        
    @field_validator('tipo_operacion')
    @classmethod
    def standarize_tipo(cls, v: str) -> str:
        """Clean type whitespace for consistency across all inputs"""
        return v.strip() if v else ""

    @model_validator(mode='after')
    def validate_non_empty(self):
        """Reject transactions where crypto amounts or ARS are negative."""
        if self.monto_compra_cripto < 0 or self.monto_venta_cripto < 0 or self.monto_ars < 0:
            raise ValueError("Crypto amounts and ARS cannot be negative.")
        return self

    def to_dict(self) -> dict:
        """
        Exports the validated model back into the dictionary format expected 
        by the legacy Master Excel generator, including a unique tx_hash.
        """
        fecha_str = self.fecha.strftime('%Y-%m-%d %H:%M:%S')
        hash_fecha = f"{fecha_str}Z" if getattr(self, '_is_utc', False) else fecha_str
        tx_hash = compute_canonical_tx_hash(
            hash_fecha, self.exchange, self.tipo_operacion, self.moneda,
            monto_compra=self.monto_compra_cripto, monto_venta=self.monto_venta_cripto,
            monto_ars=self.monto_ars,
            unique_ref=self.comentarios
        )
        res = {
            "tx_hash": tx_hash, "Fecha": fecha_str, "Exchange": self.exchange,
            "Tipo de Operación": self.tipo_operacion, "Moneda": self.moneda,
            "Monto Compra (Cripto)": self.monto_compra_cripto, "Monto Venta (Cripto)": self.monto_venta_cripto,
            "Cotización Compra": self.cotizacion_compra, "Cotización Venta": self.cotizacion_venta,
            "Monto ARS": self.monto_ars, "Comentarios": self.comentarios,
            "source": self.source
        }
        if getattr(self, '_is_utc', False):
            res["_is_utc"] = True
        return res


try:
    from .cpa_seed_data import CPA_MONTHLY_MAP
except ImportError:
    from models.cpa_seed_data import CPA_MONTHLY_MAP
