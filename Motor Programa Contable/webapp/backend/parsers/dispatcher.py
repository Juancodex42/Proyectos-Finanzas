"""
Central file dispatcher for uploaded accounting statements and archives.
"""

import io
import sys
import zipfile
import pandas as pd

try:
    from exceptions import MissingColumnsError
except ImportError:
    from utils.exceptions import MissingColumnsError

from .base_parser import extract_preview_columns
from .binance_parser import process_binance_csv
from .fiwind_parser import process_fiwind
from .bitso_parser import process_bitso
from .ripio_parser import process_ripio_trade, procesar_ripio_comun_txt
from .bitget_parser import process_bitget
from .other_exchanges_parser import process_dynamic_csv, process_other_exchange
from .excel_multi_processor import process_multi_exchange_excel
from .archive_processor import process_archive
from .exchange_detector import detect_exchange
from .okx_parser import process_okx_file
from .pdf_cert_helper import extract_info_from_pdf_stream
from .pdf_table_extractor import extract_transactions_from_pdf_stream

parse_pdf_Visual_or_text = extract_info_from_pdf_stream
extract_tables_from_pdf = extract_transactions_from_pdf_stream


def _resolve_helper(name: str, default_fn):
    """Checks compat.processor_lib / processor_lib in sys.modules for monkeypatched overrides."""
    for mod_name in ("processor_lib", "compat.processor_lib"):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, name):
            candidate = getattr(mod, name)
            if candidate is not default_fn:
                return candidate
    return default_fn


def process_uploaded_file(file_obj, filename, depth=0, state=None, override_exchange=None):
    """Dispatches uploaded file to the specialized exchange parser with dynamic scoring and override support."""
    fn = filename.lower()
    known_data_exts = ('.csv', '.xls', '.xlsx', '.txt')

    if fn.endswith('.pdf'):
        file_obj.seek(0)
        raw_bytes = file_obj.read() if hasattr(file_obj, 'read') else b''
        pdf_visual_fn = _resolve_helper('parse_pdf_Visual_or_text', parse_pdf_Visual_or_text)
        pdf_tables_fn = _resolve_helper('extract_tables_from_pdf', extract_tables_from_pdf)
        if pdf_tables_fn is not extract_transactions_from_pdf_stream:
            res = pdf_tables_fn(io.BytesIO(raw_bytes) if raw_bytes else file_obj, filename)
            if isinstance(res, tuple) and len(res) == 2:
                return res
            if isinstance(res, list):
                return res, res[:5]
        if pdf_visual_fn is not extract_info_from_pdf_stream:
            res = pdf_visual_fn(io.BytesIO(raw_bytes) if raw_bytes else file_obj, filename)
            if isinstance(res, tuple) and len(res) == 2:
                return res
            if isinstance(res, list):
                return res, res[:5]
        if raw_bytes.startswith(b'%PDF-'):
            extractor = _resolve_helper('extract_transactions_from_pdf_stream', extract_transactions_from_pdf_stream)
            txs = extractor(raw_bytes, filename=filename) or []
            if override_exchange:
                for r in txs:
                    r['Exchange'] = override_exchange
            return txs, txs[:5]
        return [], []

    archive_fn = _resolve_helper('process_archive', process_archive)
    if not fn.endswith(known_data_exts):
        if fn.endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.7z', '.rar')):
            file_obj.seek(0)
            return archive_fn(file_obj, filename, depth, state, process_uploaded_file)
        try:
            file_obj.seek(0)
            if zipfile.is_zipfile(file_obj):
                file_obj.seek(0)
                return archive_fn(file_obj, filename, depth, state, process_uploaded_file)
        except Exception:
            pass

    preview_fn = _resolve_helper('extract_preview_columns', extract_preview_columns)
    cols_set = preview_fn(file_obj, filename)

    # 1. Determine target exchange via manual override or dynamic signature scoring
    target_exchange = (override_exchange or "").strip()
    if not target_exchange:
        detect_fn = _resolve_helper('detect_exchange', detect_exchange)
        detected_meta = detect_fn(file_obj, filename, preview_cols=cols_set)
        if detected_meta.get('confidence', 0.0) >= 0.35:
            target_exchange = detected_meta.get('detected_exchange', '')

    target_upper = target_exchange.upper()

    # 2. Specialized OKX parser (prevents false hijack by Binance P2P)
    is_okx = target_upper == 'OKX' or ('OKX' in target_upper and 'BINANCE' not in target_upper)
    if is_okx or ('volume' in cols_set and 'amount' in cols_set and 'order source' in cols_set):
        try:
            okx_fn = _resolve_helper('process_okx_file', process_okx_file)
            res = okx_fn(file_obj, filename)
            if res and res[0]:
                if override_exchange:
                    for r in res[0]:
                        r['Exchange'] = override_exchange
                return res
        except MissingColumnsError:
            raise
        except Exception as e:
            print(f"OKX processor error: {e}")

    # 3. Explicit Multi-exchange consolidated workbook
    has_explicit_ex_col = any(k in cols_set for k in ['exchange', 'plataforma', 'entidad', 'broker', 'exchange/plataforma', 'plataforma/exchange'])
    has_ex_col = has_explicit_ex_col or any(k in cols_set for k in ['billetera', 'wallet'])
    has_cons_cols = any(k in cols_set for k in ['cotizacion compra', 'cotizacion venta', 'monto compra (cripto)', 'monto venta (cripto)', 'cotizacion_compra', 'cotizacion_venta'])
    ex_hint = (override_exchange or target_exchange or "").lower()
    fn_lower = fn
    has_dedicated_exchange = any(
        ex_kw in ex_hint or ex_kw in fn_lower
        for ex_kw in ('bitso', 'fiwind', 'ripio', 'bitget', 'binance', 'okx')
    ) and not has_explicit_ex_col

    multi_excel_fn = _resolve_helper('process_multi_exchange_excel', process_multi_exchange_excel)
    if (target_upper == 'PLANILLA CONSOLIDADA' or has_ex_col or has_cons_cols) and not has_dedicated_exchange:
        try:
            m_recs, m_samp = multi_excel_fn(file_obj, filename)
            if m_recs:
                if override_exchange:
                    for r in m_recs:
                        r['Exchange'] = override_exchange
                return m_recs, m_samp
        except Exception as e:
            print(f"Multi-exchange check error: {e}")

    # 4. Bitso parser
    is_bitso = target_upper in ('BITSO', 'BITSO ALPHA') or ('major' in cols_set and 'minor' in cols_set) or ('rate' in cols_set and 'value' in cols_set) or ('bitso' in cols_set) or ('bitso' in fn)
    if is_bitso:
        try:
            bitso_fn = _resolve_helper('process_bitso', process_bitso)
            res = bitso_fn(file_obj, filename)
            if res and res[0]:
                if override_exchange:
                    for r in res[0]:
                        r['Exchange'] = override_exchange
                return res
        except MissingColumnsError:
            if "bitso" in fn or 'bitso' in cols_set or ('major' in cols_set and 'minor' in cols_set):
                raise
        except Exception as e:
            print(f"Bitso error: {e}")

    # 5. Fiwind parser
    is_fiwind = target_upper == 'FIWIND' or ("fiwind" in fn or "fiwind" in cols_set)
    if is_fiwind and (fn.endswith('.xls') or fn.endswith('.xlsx') or fn.endswith('.csv')):
        try:
            fiwind_fn = _resolve_helper('process_fiwind', process_fiwind)
            res = fiwind_fn(file_obj, filename)
            if res and res[0] and override_exchange:
                for r in res[0]:
                    r['Exchange'] = override_exchange
            return res
        except MissingColumnsError:
            if "fiwind" in fn or "fiwind" in cols_set:
                raise

    # 6. Ripio parser
    is_ripio = 'RIPIO' in target_upper or ("ripio" in fn or "ripio trade" in fn or "ripio_trade" in fn or 'codigo_operacion' in cols_set or 'codigo de operacion' in cols_set)
    if is_ripio and not fn.endswith('.txt'):
        try:
            ripio_fn = _resolve_helper('process_ripio_trade', process_ripio_trade)
            res = ripio_fn(file_obj, filename)
            if res and res[0] and override_exchange:
                for r in res[0]:
                    r['Exchange'] = override_exchange
            return res
        except MissingColumnsError:
            if "ripio" in fn or "ripio" in cols_set or 'codigo_operacion' in cols_set or 'codigo de operacion' in cols_set:
                raise
    elif is_ripio and fn.endswith('.txt'):
        try:
            ripio_txt_fn = _resolve_helper('procesar_ripio_comun_txt', procesar_ripio_comun_txt)
            return ripio_txt_fn(file_obj, filename)
        except Exception:
            pass

    # 7. Bitget parser
    is_bitget = 'BITGET' in target_upper or "bitget" in fn or 'bitget' in cols_set
    if is_bitget:
        try:
            bitget_fn = _resolve_helper('process_bitget', process_bitget)
            res = bitget_fn(file_obj, filename)
            if res and res[0]:
                if override_exchange:
                    for r in res[0]:
                        r['Exchange'] = override_exchange
                return res
        except Exception as e:
            print(f"Bitget error: {e}")

    # 8. Binance Parser (disambiguated: supports both English and Spanish statements)
    is_binance_p2p = any(k in cols_set for k in ['tipo de orden', 'número de pedido', 'numero de pedido', 'tipo de fiat', 'precio total', 'hora de creación', 'hora de creacion', 'fiat type', 'asset type'])
    is_binance_spot = ('executed' in cols_set and 'side' in cols_set and ('pair' in cols_set or 'price' in cols_set)) or ('ejecutado' in cols_set and 'lado' in cols_set and ('par' in cols_set or 'precio' in cols_set))
    is_binance_transfers = any(k in cols_set for k in ['deposit', 'withdraw', 'withdrawal', 'txid', 'change']) and any(k in cols_set for k in ['coin', 'asset', 'crypto', 'amount'])
    is_binance = 'BINANCE' in target_upper or "binance" in fn or is_binance_p2p or is_binance_spot or is_binance_transfers
    if is_binance and target_upper not in ('OKX', 'FIWIND', 'BITSO ALPHA', 'BITSO', 'RIPIO TRADE'):
        try:
            binance_fn = _resolve_helper('process_binance_csv', process_binance_csv)
            res = binance_fn(file_obj, filename)
            if res and res[0]:
                if override_exchange:
                    for r in res[0]:
                        r['Exchange'] = override_exchange
                return res
        except MissingColumnsError:
            raise
        except Exception as e:
            print(f"Binance check error: {e}")

    # 9. Dynamic user-configured CSV definitions from DB (Fail-Closed: requires explicit valid mapping)
    try:
        import db_manager
        dyn_fn = _resolve_helper('process_dynamic_csv', process_dynamic_csv)
        for ex in db_manager.get_all_exchanges():
            mapping = ex.get('mapping', {})
            if not mapping or not isinstance(mapping, dict) or not any(mapping.values()):
                continue
            if (ex['name'].lower() in fn or ex['id'].lower() in fn or ex['name'].upper() == target_upper) and (fn.endswith('.csv') or fn.endswith('.xlsx') or fn.endswith('.xls')):
                file_obj.seek(0)
                df = pd.read_csv(file_obj) if fn.endswith('.csv') else pd.read_excel(file_obj)
                clean_cols = {str(c).lower().strip() for c in df.columns}
                if not any(str(col).lower().strip() in clean_cols for col in mapping.values() if col):
                    continue
                res_df = dyn_fn(df, ex['name'], mapping, ex.get('dateFormat', '%d/%m/%Y %H:%M:%S'))
                records = res_df.to_dict('records') if not res_df.empty else []
                valid_records = [
                    r for r in records
                    if not (r.get('tipo_operacion') == 'MOVIMIENTO DESCONOCIDO' and r.get('monto_compra_cripto', 0) == 0 and r.get('monto_venta_cripto', 0) == 0)
                ]
                sample = df.head(5).to_dict('records') if not df.empty else []
                if valid_records:
                    return valid_records, sample
    except Exception as e:
        print("Dynamic CSV check error:", e)

    # 10. Other international exchanges
    if any(k in fn for k in ['lemon', 'bybit', 'belo', 'buenbit', 'kraken']) or target_upper in ('LEMON', 'BYBIT', 'BINGX'):
        try:
            other_fn = _resolve_helper('process_other_exchange', process_other_exchange)
            res = other_fn(file_obj, filename)
            if res and res[0]:
                if override_exchange:
                    for r in res[0]:
                        r['Exchange'] = override_exchange
                return res
        except Exception:
            pass

    try:
        m_recs, m_samp = multi_excel_fn(file_obj, filename)
        if m_recs:
            return m_recs, m_samp
    except Exception as e:
        print("Multi-exchange fallback error:", e)

    # Fail-closed: Unrecognized files return empty instead of blindly defaulting to Binance
    return [], []


process_file = process_uploaded_file
