"""
Motor de deduplicación determinista y saneamiento de transacciones.
Depura colisiones por hash canónico y protege ejecuciones parciales simultáneas.
Referencia de diseño: docs/contratos_io_transacciones.md
"""

import re
import logging
import pandas as pd
import db.connection

logger = logging.getLogger(__name__)


def get_connection():
    return db.connection.get_connection()


def deduplicate_existing_database(conn=None):
    """Scans DB and purges duplicates using canonical hashing and trade ID alignment."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        from models.transaction_models import (
            canonicalize_ticker,
            compute_canonical_tx_hash,
            get_canonical_exchange_root,
        )

        df = pd.read_sql_query("SELECT * FROM transactions", conn)
        if df.empty:
            return 0

        def extract_clean_ref(ref):
            if not ref:
                return ""
            ref_str = str(ref).strip()
            noise_keywords = {
                'binance', 'bitso', 'ripio', 'fiwind', 'lemon', 'bybit', 'okx', 'bitget', 'otros', 'spot', 'p2p', 'trade', 'compra', 'venta', 'ingreso', 'retiro', 'deposito', 'envio', 'conversion', 'swap', 'order',
                'orden', 'manual', 'id', 'de', 'on', 'en', 'la', 'el', 'realizada', 'buy', 'sell', 'deposit', 'withdraw', 'transfer', 'send', 'payment', 'pago', 'receive', 'fee', 'comision', 'comisión', 'fiat', 'crypto', 'cripto', 'ejecutada', 'bancaria'
            }

            labeled_match = re.search(r'(?:\b(?:order\s*id|order\s*no\.?|trade\s*id|txid|tx_id|operaci[óo]n)\b\s*[:#]\s*|#\s*)([a-zA-Z0-9_\-]+)', ref_str, re.IGNORECASE)
            if labeled_match:
                t = labeled_match.group(1).lower()
                if t not in noise_keywords:
                    t = re.sub(r'[-_](?:[cv]|quote|dep|ret)$', '', t, flags=re.IGNORECASE)
                    return t
            fallback_match = re.search(r'\b(?:order|orden|trade|id|ref|txid)\s*[:#]?\s*((?=[a-zA-Z0-9_\-]*\d)[a-zA-Z0-9_\-]{4,})\b', ref_str, re.IGNORECASE)
            if fallback_match:
                t = fallback_match.group(1).lower()
                if t not in noise_keywords:
                    t = re.sub(r'[-_](?:[cv]|quote|dep|ret)$', '', t, flags=re.IGNORECASE)
                    return t
            return ""

        def map_clean_tipo(tipo_op):
            tipo_upper = str(tipo_op).strip().upper()
            if any(k in tipo_upper for k in ['DEPOSITO', 'DEPÓSITO', 'INGRESO', 'DEPOSIT', 'RECEIVE', 'RECEPCION', 'RECEPCIÓN', 'ENTRADA', 'ABONO', 'INCOMING']):
                return 'DEPOSITO'
            elif any(k in tipo_upper for k in ['COMPRA', 'BUY']):
                return 'COMPRA'
            elif any(k in tipo_upper for k in ['RETIRO', 'ENVIO', 'ENVÍO', 'WITHDRAW', 'SEND', 'OUTGOING', 'SALIDA', 'EGRESO', 'EXTRACCION', 'EXTRACCIÓN']):
                return 'RETIRO'
            elif any(k in tipo_upper for k in ['VENTA', 'SELL', 'CONSUMO', 'PAGO', 'PAYMENT']):
                return 'VENTA'
            return tipo_upper

        df['exchange_root'] = df['exchange'].apply(get_canonical_exchange_root)
        df['coin_clean'] = df['moneda'].apply(canonicalize_ticker)
        df['clean_tipo'] = df['tipo_operacion'].apply(map_clean_tipo)
        df['clean_fecha'] = df['fecha'].astype(str).str.replace('T', ' ').str.strip()
        df['op_id'] = df['comentarios'].apply(extract_clean_ref)

        def extract_trade_id(ref):
            if not ref:
                return ""
            m = re.search(r'(?:\b(?:trade\s*id|fill\s*id|ejecucion|ejecución)\b\s*[:#]\s*|\btrade\s*[:#]?\s*)((?=[a-zA-Z0-9_\-]*\d)[a-zA-Z0-9_\-]+)', str(ref), re.IGNORECASE)
            return m.group(1).lower() if m else ""

        df['trade_id'] = df.apply(lambda r: extract_trade_id(r.get('comentarios', '')) or extract_trade_id(r.get('tx_hash', '')), axis=1)
        df['effective_op_id'] = df.apply(lambda r: f"{r['op_id']}_trade_{r['trade_id']}" if r['trade_id'] else r['op_id'], axis=1)

        cert_ranges = []
        try:
            for s_d, e_d in conn.cursor().execute("SELECT start_date, end_date FROM certifications").fetchall():
                if s_d and e_d:
                    cert_ranges.append((str(s_d)[:10] + " 00:00:00", str(e_d)[:10] + " 23:59:59"))
        except Exception:
            cert_ranges = []

        df['is_certified_temp'] = df['is_certified'].fillna(0).astype(int) if 'is_certified' in df.columns else 0
        df['in_cert_range'] = df['clean_fecha'].apply(lambda f: 1 if any(s <= f <= e for s, e in cert_ranges) else 0)
        df['has_ars'] = (df['monto_ars'].fillna(0) > 0).astype(int)
        df['is_detailed'] = df['exchange'].apply(lambda x: 1 if 'trade' in str(x).lower() or 'spot' in str(x).lower() else 0)
        df = df.sort_values(by=['is_certified_temp', 'in_cert_range', 'has_ars', 'is_detailed'], ascending=[False, False, False, False])

        empty_mask = ((df['monto_compra_cripto'].fillna(0) == 0) & (df['monto_venta_cripto'].fillna(0) == 0) & (df['monto_ars'].fillna(0) == 0) & (df['is_certified_temp'] != 1))
        hashes_to_delete = set(df[empty_mask]['tx_hash'].dropna().tolist())

        with_id = df[(df['effective_op_id'] != "") & (~df['tx_hash'].isin(hashes_to_delete))]
        dups_1a = with_id[with_id.duplicated(subset=['exchange_root', 'effective_op_id', 'coin_clean', 'clean_tipo', 'monto_compra_cripto', 'monto_venta_cripto', 'clean_fecha'], keep='first')]
        hashes_to_delete.update(dups_1a['tx_hash'].tolist())

        valid_ops = df[(df['op_id'] != "") & (~df['tx_hash'].isin(hashes_to_delete))].groupby(['exchange_root', 'coin_clean', 'clean_tipo', 'op_id'])
        for (ex_r, c_cl, c_tp, o_id), op_group in valid_ops:
            if len(op_group) > 1:
                fills, grp = op_group[op_group['trade_id'] != ""], op_group[op_group['trade_id'] == ""]
                if not fills.empty and not grp.empty:
                    if abs(fills['monto_compra_cripto'].sum() - grp['monto_compra_cripto'].sum()) < 1e-6 and abs(fills['monto_venta_cripto'].sum() - grp['monto_venta_cripto'].sum()) < 1e-6:
                        if not grp[grp['is_certified_temp'] == 1].empty and fills[fills['is_certified_temp'] == 1].empty:
                            hashes_to_delete.update(fills['tx_hash'].tolist())
                        else:
                            hashes_to_delete.update(grp['tx_hash'].tolist())

        surv = df[~df['tx_hash'].isin(hashes_to_delete)].copy()
        surv['canonical_hash_temp'] = surv.apply(
            lambda r: compute_canonical_tx_hash(r['fecha'], r['exchange'], r['tipo_operacion'], r['moneda'], r['monto_compra_cripto'], r['monto_venta_cripto'], r['monto_ars'], r['comentarios']), axis=1
        )
        dups_1b = surv[surv.duplicated(subset=['exchange_root', 'clean_fecha', 'coin_clean', 'clean_tipo', 'monto_compra_cripto', 'monto_venta_cripto', 'op_id', 'canonical_hash_temp'], keep='first')]
        hashes_to_delete.update(dups_1b['tx_hash'].tolist())

        survivors_stage1 = df[~df['tx_hash'].isin(hashes_to_delete)].copy()
        survivors_stage1['new_tx_hash'] = survivors_stage1.apply(
            lambda r: compute_canonical_tx_hash(r['fecha'], r['exchange'], r['tipo_operacion'], r['moneda'], r['monto_compra_cripto'], r['monto_venta_cripto'], r['monto_ars'], r['comentarios']), axis=1
        )
        dups_stage2 = survivors_stage1[survivors_stage1.duplicated(subset=['new_tx_hash'], keep='first')]
        hashes_to_delete.update(dups_stage2['tx_hash'].tolist())

        # Stage 3: Semantic deduplication on exact identical physical events
        # Preserves legitimate same-second fills when effective_op_id is empty
        survivors_stage2 = df[~df['tx_hash'].isin(hashes_to_delete)].copy()
        survivors_stage2['monto_ars_round'] = survivors_stage2['monto_ars'].fillna(0).round(2)
        
        mask_with_id = (survivors_stage2['effective_op_id'] != "") & survivors_stage2.duplicated(
            subset=['exchange_root', 'clean_fecha', 'coin_clean', 'clean_tipo', 'monto_compra_cripto', 'monto_venta_cripto', 'effective_op_id', 'monto_ars_round'],
            keep='first'
        )
        dups_stage3 = survivors_stage2[mask_with_id]

        # Certified records protection: NEVER delete a certified record in automated deduplication
        all_certified_hashes = set(df[df['is_certified_temp'] == 1]['tx_hash'].dropna().tolist())
        hashes_to_delete = (hashes_to_delete - all_certified_hashes)
        hashes_to_delete.update(set(dups_stage3['tx_hash'].dropna().tolist()) - all_certified_hashes)

        if not hashes_to_delete:
            return 0

        c = conn.cursor()
        hashes_list = list(hashes_to_delete)
        for i in range(0, len(hashes_list), 500):
            chunk = hashes_list[i:i+500]
            placeholders = ','.join(['?'] * len(chunk))
            c.execute(f"DELETE FROM transactions WHERE tx_hash IN ({placeholders})", chunk)

        conn.commit()

        print(f"Purged {len(hashes_to_delete)} historical duplicate transactions.")
        return len(hashes_to_delete)
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"Error deduplicating database: {e}")
        return 0
    finally:
        if should_close and conn:
            conn.close()


deduplicate_database = deduplicate_existing_database
