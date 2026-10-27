"""
Dynamic Exchange Detection Engine.
Scores file columns, structure, and metadata against weighted exchange signatures
to identify exchanges deterministically without brittle hardcoded cascaded if-conditions.
"""

import re
import os
import io
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

try:
    from .base_parser import _normalize_text, extract_preview_columns
except ImportError:
    from parsers.base_parser import _normalize_text, extract_preview_columns


# Normalized signature definitions for supported exchanges
EXCHANGE_SIGNATURES = {
    'okx_p2p': {
        'canonical_name': 'OKX',
        'sub_type': 'P2P',
        'required_cols': ['order no', 'volume', 'amount'],
        'discriminators': ['order source', 'payment method', 'counterparty', 'order type', 'crypto', 'currency'],
        'filename_keywords': ['okx'],
        'weights': {'required': 6.0, 'discriminator': 2.0, 'filename': 2.0}
    },
    'okx_spot': {
        'canonical_name': 'OKX',
        'sub_type': 'SPOT',
        'required_cols': ['instrument', 'side', 'size'],
        'discriminators': ['fee', 'filled time', 'order id', 'avg price', 'order state'],
        'filename_keywords': ['okx'],
        'weights': {'required': 6.0, 'discriminator': 2.0, 'filename': 2.0}
    },
    'binance_p2p': {
        'canonical_name': 'Binance P2P',
        'sub_type': 'P2P',
        'required_cols': ['número de pedido', 'numero de pedido', 'tipo de orden', 'fiat type', 'asset type'],
        'discriminators': ['precio total', 'hora de creación', 'hora de creacion', 'fiat', 'order type'],
        'filename_keywords': ['c2c', 'p2p', 'binance'],
        'weights': {'required': 5.0, 'discriminator': 1.5, 'filename': 2.0}
    },
    'binance_p2p_es': {
        'canonical_name': 'Binance P2P',
        'sub_type': 'P2P',
        'required_cols': ['número de pedido', 'tipo de orden', 'activo', 'tipo de fiat'],
        'discriminators': ['precio total', 'hora de creación', 'hora de creacion', 'tarifa de creador', 'comisión de tomador', 'comision de tomador', 'contraparte'],
        'filename_keywords': ['c2c', 'p2p', 'binance', 'órdenes', 'ordenes'],
        'weights': {'required': 5.0, 'discriminator': 2.0, 'filename': 2.0}
    },
    'binance_spot': {
        'canonical_name': 'Binance Spot',
        'sub_type': 'SPOT',
        'required_cols': ['executed', 'pair', 'side'],
        'discriminators': ['date(utc)', 'trade id', 'fee coin', 'market', 'instrumento'],
        'filename_keywords': ['spot', 'binance'],
        'weights': {'required': 5.0, 'discriminator': 1.5, 'filename': 2.0}
    },
    'binance_spot_es': {
        'canonical_name': 'Binance Spot',
        'sub_type': 'SPOT',
        'required_cols': ['ejecutado', 'par', 'lado'],
        'discriminators': ['número de orden', 'numero de orden', 'hora', 'precio', 'tarifa', 'tarifa de conversión aor', 'tasa de conversión de aor'],
        'filename_keywords': ['spot', 'binance'],
        'weights': {'required': 5.0, 'discriminator': 2.0, 'filename': 2.0}
    },
    'bitso': {
        'canonical_name': 'Bitso Alpha',
        'sub_type': 'SPOT',
        'required_cols': ['major', 'minor', 'rate'],
        'discriminators': ['value', 'datetime', 'bitso'],
        'filename_keywords': ['bitso'],
        'weights': {'required': 6.0, 'discriminator': 2.0, 'filename': 2.0}
    },
    'fiwind': {
        'canonical_name': 'Fiwind',
        'sub_type': 'GENERAL',
        'required_cols': ['operación', 'operacion', 'origen', 'destino'],
        'discriminators': ['moneda', 'monto origen', 'monto destino', 'estado', 'fiwind'],
        'filename_keywords': ['fiwind'],
        'weights': {'required': 5.0, 'discriminator': 2.0, 'filename': 3.0}
    },
    'ripio_trade': {
        'canonical_name': 'Ripio Trade',
        'sub_type': 'SPOT',
        'required_cols': ['codigo_operacion', 'codigo de operacion', 'moneda', 'monto'],
        'discriminators': ['cantidad ejecutada', 'costo total', 'comision', 'ripio'],
        'filename_keywords': ['ripio', 'trade'],
        'weights': {'required': 5.0, 'discriminator': 2.0, 'filename': 2.5}
    },
    'ripio_trade_ledger': {
        'canonical_name': 'Ripio Trade',
        'sub_type': 'MOVEMENTS',
        'required_cols': ['codigo de operacion', 'saldo despues de la operacion', 'identificador'],
        'discriminators': ['monto de la operacion', 'moneda', 'documento del cliente', 'descripcion', 'ripio'],
        'filename_keywords': ['ripio', 'trade', 'historico'],
        'weights': {'required': 5.0, 'discriminator': 2.5, 'filename': 2.5}
    },
    'ripio_classic': {
        'canonical_name': 'Ripio Classic',
        'sub_type': 'GENERAL',
        'required_cols': ['tipo de movimiento', 'monto en cripto'],
        'discriminators': ['valor en ars', 'estado'],
        'filename_keywords': ['ripio'],
        'weights': {'required': 4.0, 'discriminator': 2.0, 'filename': 2.0}
    },
    'bitget_p2p': {
        'canonical_name': 'Bitget P2P',
        'sub_type': 'P2P',
        'required_cols': ['order id', 'crypto amount', 'total price'],
        'discriminators': ['coin', 'fiat', 'order status', 'bitget'],
        'filename_keywords': ['bitget'],
        'weights': {'required': 5.0, 'discriminator': 2.0, 'filename': 2.5}
    },
    'bybit': {
        'canonical_name': 'Bybit',
        'sub_type': 'SPOT',
        'required_cols': ['spot pair', 'contracts', 'order price'],
        'discriminators': ['bybit', 'filled value', 'trade time'],
        'filename_keywords': ['bybit'],
        'weights': {'required': 5.0, 'discriminator': 2.0, 'filename': 2.5}
    },
    'bingx': {
        'canonical_name': 'BingX',
        'sub_type': 'P2P',
        'required_cols': ['bingx', 'fiat currency', 'crypto volume'],
        'discriminators': ['order no', 'created time'],
        'filename_keywords': ['bingx'],
        'weights': {'required': 5.0, 'discriminator': 2.0, 'filename': 3.0}
    },
    'multi_consolidated': {
        'canonical_name': 'Planilla Consolidada',
        'sub_type': 'MULTI',
        'required_cols': ['exchange', 'cotizacion compra', 'cotizacion venta'],
        'discriminators': ['monto compra (cripto)', 'monto venta (cripto)', 'monto ars'],
        'filename_keywords': ['consolidado', 'consolidada', 'contador', 'maestro'],
        'weights': {'required': 6.0, 'discriminator': 2.0, 'filename': 2.0}
    }
}


def _normalize_col(col_name: Any) -> str:
    s = str(col_name or '').lower().strip()
    s = re.sub(r'[\r\n\t]+', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s


def score_exchange_match(cols_set: set, filename: str) -> Dict[str, Any]:
    """
    Computes weighted score for each exchange signature against column set and filename.
    Returns sorted list of match candidates.
    """
    fn_lower = filename.lower()
    norm_cols_set = {_normalize_text(c) for c in (cols_set or set())}
    scores = {}

    for sig_id, sig in EXCHANGE_SIGNATURES.items():
        score = 0.0
        max_possible = 0.0

        # Check required columns
        req_weights = sig['weights']['required']
        req_cols = [_normalize_text(c) for c in sig.get('required_cols', [])]
        matched_req = [c for c in req_cols if c in norm_cols_set]
        if matched_req:
            score += (len(matched_req) / len(req_cols)) * req_weights
        max_possible += req_weights

        # Check discriminator columns
        disc_weights = sig['weights']['discriminator']
        disc_cols = [_normalize_text(c) for c in sig.get('discriminators', [])]
        matched_disc = [c for c in disc_cols if c in norm_cols_set]
        if matched_disc:
            score += min(len(matched_disc) * 0.8, disc_weights)
        max_possible += disc_weights

        # Check filename keywords
        fn_weight = sig['weights']['filename']
        if any(kw in fn_lower for kw in sig['filename_keywords']):
            score += fn_weight
        max_possible += fn_weight

        # Negative penalty: if it matches OKX P2P signature precisely ('volume' and 'amount' in cols),
        # severely penalize binance_p2p to prevent false hijack
        if sig_id in ('binance_p2p', 'binance_p2p_es') and ('volume' in norm_cols_set and 'amount' in norm_cols_set and 'order source' in norm_cols_set):
            score = 0.0
        if sig_id == 'bybit' and ('bitget' in fn_lower or 'bitso' in fn_lower):
            score = 0.0

        confidence = round(score / max_possible, 3) if max_possible > 0 else 0.0
        scores[sig_id] = {
            'canonical_name': sig['canonical_name'],
            'sub_type': sig['sub_type'],
            'raw_score': score,
            'confidence': confidence
        }

    # Also evaluate user-registered dynamic exchanges from DB
    try:
        from db.connection import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, name, mapping_json FROM exchanges_config WHERE is_active = 1")
        for row in c.fetchall():
            ex_id, ex_name, map_json = row
            if ex_id in EXCHANGE_SIGNATURES:
                continue
            name_lower = ex_name.lower()
            ex_score = 0.0
            if name_lower in fn_lower:
                ex_score += 3.0
            if ex_score > 0:
                scores[f"custom_{ex_id}"] = {
                    'canonical_name': ex_name,
                    'sub_type': 'CUSTOM',
                    'raw_score': ex_score,
                    'confidence': min(1.0, round(ex_score / 5.0, 3))
                }
        conn.close()
    except Exception:
        pass

    return scores


def detect_exchange(file_obj, filename: str, preview_cols: Optional[set] = None) -> Dict[str, Any]:
    """
    Main detection entrypoint.
    Returns best-matching exchange metadata, confidence, and alternatives.
    """
    if preview_cols is None:
        try:
            preview_cols = extract_preview_columns(file_obj, filename)
        except Exception:
            preview_cols = set()
    else:
        preview_cols = {_normalize_text(c) for c in preview_cols}

    # Pre-check: explicit 'Exchange' or 'Plataforma' column takes absolute precedence for multi-exchange
    if any(k in preview_cols for k in ['exchange', 'plataforma', 'exchange/plataforma', 'exchange plataforma']):
        if any(k in preview_cols for k in ['cotizacion compra', 'cotizacion venta', 'monto compra (cripto)']):
            return {
                'detected_exchange': 'Planilla Consolidada',
                'confidence': 1.0,
                'sub_type': 'MULTI',
                'needs_user_confirmation': False,
                'alternatives': []
            }

    scores = score_exchange_match(preview_cols, filename)
    sorted_candidates = sorted(scores.items(), key=lambda item: item[1]['confidence'], reverse=True)

    if sorted_candidates and sorted_candidates[0][1]['confidence'] >= 0.40:
        best_key, best_meta = sorted_candidates[0]
        alternatives = [c[1]['canonical_name'] for c in sorted_candidates[1:5] if c[1]['confidence'] >= 0.20]
        return {
            'detected_exchange': best_meta['canonical_name'],
            'confidence': best_meta['confidence'],
            'sub_type': best_meta['sub_type'],
            'needs_user_confirmation': best_meta['confidence'] < 0.70,
            'alternatives': alternatives,
            'signature_key': best_key
        }

    fn = filename.lower()
    fn_key = None
    if 'bitget' in fn:
        fn_key = 'bitget_p2p'
    elif 'bitso' in fn:
        fn_key = 'bitso'
    elif 'bybit' in fn:
        fn_key = 'bybit'

    if fn_key and fn_key in scores:
        best_meta = scores[fn_key]
        return {
            'detected_exchange': best_meta['canonical_name'],
            'confidence': max(best_meta['confidence'], 0.45),
            'sub_type': best_meta['sub_type'],
            'needs_user_confirmation': True,
            'alternatives': [c[1]['canonical_name'] for c in sorted_candidates[:4] if c[0] != fn_key and c[1]['confidence'] >= 0.20],
            'signature_key': fn_key
        }

    return {
        'detected_exchange': 'CSV / Excel Estándar',
        'confidence': 0.1,
        'sub_type': 'GENERIC',
        'needs_user_confirmation': True,
        'alternatives': ['Binance P2P', 'Binance Spot', 'Fiwind', 'Bitso Alpha', 'Ripio Trade', 'OKX', 'Bybit', 'Bitget P2P']
    }

