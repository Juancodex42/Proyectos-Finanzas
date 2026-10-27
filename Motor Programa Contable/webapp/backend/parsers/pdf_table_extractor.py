"""
Extractor vectorial y OCR de tablas transaccionales desde dictámenes PDF.
Aplica validación de columnas, despolarización de montos y hashing canónico.
Referencia de diseño: docs/contratos_io_transacciones.md
"""

import os
import re
import fitz  # PyMuPDF
import pandas as pd
from datetime import datetime
from models.transaction_models import TransactionModel, compute_canonical_tx_hash
from .pdf_date_helpers import clean_num, _sanitize_and_build_date, parse_date_str

try:
    from .ocr_helper import _get_ocr_engine as _get_ocr, ocr_pdf_page
    from .parallel_extractor import ParallelPageExtractor
except ImportError:
    from parsers.ocr_helper import _get_ocr_engine as _get_ocr, ocr_pdf_page
    from parsers.parallel_extractor import ParallelPageExtractor

COIN_SET = {'USDT', 'BTC', 'ETH', 'DAI', 'USDC', 'BUSD', 'MATIC', 'BNB', 'XRP', 'SOL'}
KNOWN_EXCHANGES = [
    'BINANCE', 'BYBIT', 'BITSO', 'FIWIND', 'PAXFUL',
    'LOCAL BITCOIN', 'LOCALBITCOINS', 'KUCOIN', 'OKX', 'RIPIO', 'LEMON', 'BITGET'
]


def resolve_amounts(nums, coin, year=None):
    """
    Given a list of positive numbers extracted from a transaction chunk,
    identifies: (monto_ars, cotizacion, cantidad_cripto)
    using exact mathematical relationship: Qty * Price ~= Total ARS
    and currency-specific historical market bands by year.
    Discards noise triplets (e.g. 1.0 * 1.0 = 1.0) in favor of authentic trade numbers.
    """
    if not nums:
        return 0.0, 0.0, 0.0
    if len(nums) == 1:
        return nums[0], 0.0, 0.0
    coin_upper = str(coin).upper()
    price_bands = {2022: (100, 450), 2023: (300, 1150), 2024: (750, 1600), 2025: (900, 1800), 2026: (900, 2500)}
    if year and year in price_bands:
        p_min, p_max = price_bands[year]
    elif year and year > 2026:
        p_min, p_max = 900, int(2500 * (1.35 ** (year - 2026)))
    else:
        p_min, p_max = (100, 3000)

    valid_candidates = []
    # 1. Check all triplets for Qty * Price ~= Total ARS
    for i in range(len(nums)):
        for j in range(len(nums)):
            if i == j:
                continue
            for k in range(len(nums)):
                if k == i or k == j:
                    continue
                n_total, n_a, n_b = nums[i], nums[j], nums[k]
                if n_total > 0 and n_a > 0 and n_b > 0:
                    if abs(n_a * n_b - n_total) / n_total < 0.05:
                        if coin_upper in ('USDT', 'USDC', 'DAI', 'BUSD'):
                            if p_min <= n_a <= p_max and not (p_min <= n_b <= p_max):
                                valid_candidates.append((2, n_total, round(n_a, 2), round(n_total / n_a, 6)))
                            elif p_min <= n_b <= p_max and not (p_min <= n_a <= p_max):
                                valid_candidates.append((2, n_total, round(n_b, 2), round(n_total / n_b, 6)))
                            elif p_min <= n_a <= p_max and p_min <= n_b <= p_max:
                                price, qty = (n_a, n_b) if abs(n_a - 1100.0) < abs(n_b - 1100.0) else (n_b, n_a)
                                valid_candidates.append((2, n_total, round(price, 2), round(n_total / price, 6)))
                            elif n_total >= 50:
                                price, qty = (n_a, n_b) if abs(n_a - 1100.0) < abs(n_b - 1100.0) else (n_b, n_a)
                                valid_candidates.append((1, n_total, round(price, 2), round(n_total / price, 6)))
                        elif coin_upper == 'BTC':
                            price, qty = max(n_a, n_b), min(n_a, n_b)
                            if price >= 100_000:
                                valid_candidates.append((2, n_total, round(price, 2), round(n_total / price, 8)))
                            elif n_total >= 1000:
                                valid_candidates.append((1, n_total, round(price, 2), round(n_total / price, 8)))
                        else:
                            valid_candidates.append((1, n_total, round(max(n_a, n_b), 2), min(n_a, n_b)))

    if valid_candidates:
        valid_candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
        _, tot, pr, qt = valid_candidates[0]
        return tot, pr, qt

    # 2. Pair matching (len >= 2)
    nums_sorted = sorted(nums, reverse=True)
    m_ars = nums_sorted[0]
    remaining = nums_sorted[1:]
    if remaining:
        c_val = remaining[0]
        if coin_upper in ('USDT', 'USDC', 'DAI', 'BUSD'):
            if p_min <= c_val <= p_max:
                price = c_val
                qty = round(m_ars / price, 6) if price > 0 else 0.0
            else:
                qty = c_val
                price = round(m_ars / qty, 2) if qty > 0 else 0.0
        elif coin_upper == 'BTC':
            if c_val >= 500_000:
                price = c_val
                qty = round(m_ars / price, 8) if price > 0 else 0.0
            else:
                qty = c_val
                price = round(m_ars / qty, 2) if qty > 0 else 0.0
        else:
            qty = min(remaining)
            price = round(m_ars / qty, 2) if qty > 0 else 0.0
        return m_ars, price, qty
    return m_ars, 0.0, 0.0


def extract_cpa_summary_table(doc):
    """
    Extracts the official CPA summary table (Anexo I) from certification PDF.
    Returns dictionary with total_ventas, total_compras, ganancia_neta, and monthly breakdown.
    """
    res = {"total_ventas": 0.0, "total_compras": 0.0, "ganancia_neta": 0.0, "monthly_breakdown": {}}
    for p_idx in range(len(doc)):
        text = doc[p_idx].get_text()
        if not text or len(text.strip()) < 10:
            if p_idx < 3:
                text = ocr_pdf_page(doc[p_idx], dpi=150)
        if not text:
            continue
        if "Certifico que el monto total" in text or "cuyo monto total en cifras historicas asciende a" in text:
            m_pnl = re.search(r'suma de \$\s*([\d\.,]+)', text)
            if m_pnl:
                try:
                    res["ganancia_neta"] = float(m_pnl.group(1).replace('.', '').replace(',', '.'))
                except ValueError:
                    pass
            m_sells = re.search(r'movimientos bancarios por \$\s*([\d\.,]+)', text)
            if m_sells:
                try:
                    res["total_ventas"] = float(m_sells.group(1).replace('.', '').replace(',', '.'))
                except ValueError:
                    pass
            m_alt_sells = re.search(r'asciende a \$\s*([\d\.,]+)', text)
            if m_alt_sells and res["total_ventas"] == 0.0:
                try:
                    res["total_ventas"] = float(m_alt_sells.group(1).replace('.', '').replace(',', '.'))
                except ValueError:
                    pass
            m_alt_pnl = re.search(r'obtenidos por dicha actividad.*?asciende a \$\s*([\d\.,]+)', text, re.DOTALL)
            if m_alt_pnl and res["ganancia_neta"] == 0.0:
                try:
                    res["ganancia_neta"] = float(m_alt_pnl.group(1).replace('.', '').replace(',', '.'))
                except ValueError:
                    pass
        if res["total_ventas"] > 0 and (res.get("total_compras", 0.0) == 0.0):
            res["total_compras"] = round(res["total_ventas"] - float(res.get("ganancia_neta", 0.0)), 2)
    return res


def extract_transactions_from_pdf_stream(file_bytes, filename="", progress_callback=None):
    """
    Extracts structured transactions from a CPA certification PDF file stream.
    Supports both vector text PDFs (instant) and scanned image PDFs via ParallelPageExtractor.
    Returns a chronologically sorted list of transaction dictionaries.
    """
    if hasattr(file_bytes, 'seek'):
        try:
            file_bytes.seek(0)
        except Exception:
            pass
    if hasattr(file_bytes, 'read'):
        file_bytes = file_bytes.read()
    elif isinstance(file_bytes, (str, os.PathLike)) and os.path.isfile(file_bytes):
        with open(file_bytes, 'rb') as f:
            file_bytes = f.read()

    current_exchange = "Binance"
    fn_upper = filename.upper()
    for kw, ex_name in (('BYBIT', 'Bybit'), ('BITSO', 'Bitso'), ('FIWIND', 'Fiwind'), ('PAXFUL', 'Paxful')):
        if kw in fn_upper:
            current_exchange = ex_name
            break

    if not file_bytes:
        return []

    # Parallel extraction: instant for vector text, multi-core concurrent OCR for scanned pages
    try:
        extractor = ParallelPageExtractor()
        page_texts = extractor.extract_document_hybrid(
            file_bytes=file_bytes,
            dpi=150,
            progress_callback=progress_callback
        )
    except Exception as e:
        print(f"[EXTRACT TRANSACTIONS ERROR] PDF open/extract failed: {e}")
        return []

    extracted_txs = []
    total_pages = len(page_texts)

    for p_idx in range(total_pages):
        text = page_texts.get(p_idx, "")
        if not text or len(text.strip()) < 10:
            continue
        if ("ACTIVIDAD: ENAJENACIÓN DE MONEDAS DIGITALES" in text and p_idx == 0) or (
            "EXPLICACION DEL ALCANCE DE UNA CERTIFICACION" in text
        ) or ("Legalizamos, de acuerdo con las facultades" in text):
            continue

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        first_chunk = " ".join(lines[:8]).upper()
        for ex in KNOWN_EXCHANGES:
            if ex in first_chunk:
                current_exchange = "LocalBitcoins" if ex.title() in ("Local Bitcoin", "Localbitcoins") else ex.title()
                break

        page_sig_counts = {}
        last_row_end = 0
        i = 0
        while i < len(lines):
            l_upper = lines[i].upper()
            has_op = any(re.search(rf'\b{w}\b', l_upper) for w in ('SELL', 'BUY', 'VENTA', 'COMPRA', 'ONLINE_BUY', 'ONLINE_SELL', 'ORDEN'))
            is_summary = any(k in l_upper for k in ('RESUMEN', 'OPERACION/MES', 'TOTAL VENTAS', 'TOTAL COMPRAS', 'TOTAL EN PESOS'))
            if has_op and not is_summary:
                op_type = 'Venta' if any(re.search(rf'\b{w}\b', l_upper) for w in ['SELL', 'VENTA']) else 'Compra'
                start_win = i
                max_end = min(len(lines), i + 12)
                end_win = max_end
                hit_boundary = False
                for k in range(i + 1, max_end):
                    k_upper = lines[k].upper()
                    k_is_summary = any(kw in k_upper for kw in ('RESUMEN', 'OPERACION/MES', 'TOTAL VENTAS', 'TOTAL COMPRAS', 'TOTAL EN PESOS', 'VENTAS', 'COMPRAS', 'MES'))
                    k_has_op = any(re.search(rf'\b{w}\b', k_upper) for w in ('SELL', 'BUY', 'VENTA', 'COMPRA', 'ONLINE_BUY', 'ONLINE_SELL', 'ORDEN'))
                    if k_has_op and not k_is_summary:
                        end_win = k
                        hit_boundary = True
                        break
                next_i = end_win if hit_boundary else (i + 1)
                chunk_lines = lines[start_win:end_win]
                chunk_upper = " ".join(chunk_lines).upper()
                if any(cw in chunk_upper for cw in ('CANCELLED', 'CANCELADO', 'CANCELED')):
                    last_row_end = end_win if hit_boundary else (i + 1)
                    i = next_i
                    continue

                date_val = ''
                for cl in chunk_lines:
                    d_parsed = parse_date_str(cl)
                    if d_parsed:
                        date_val = d_parsed
                        break

                if date_val:
                    coin_val = 'BTC' if current_exchange == 'LocalBitcoins' else 'USDT'
                    found_coin = False
                    for cl in chunk_lines:
                        c_up = cl.upper()
                        for c in sorted(COIN_SET, key=lambda x: -len(x)):
                            if re.search(rf'\b{c}\b', c_up):
                                coin_val = c
                                found_coin = True
                                break
                        if found_coin:
                            break

                    nums = []
                    for cl in chunk_lines:
                        cl_clean = re.sub(r'\d{2,4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{2,4}|\d{2}:\d{2}(?::\d{1,2})?', '', cl)
                        for tok in cl_clean.split():
                            n = clean_num(tok)
                            if n > 0:
                                nums.append(n)
                                if '.' in tok and tok.count('.') > 1 and ',' not in tok:
                                    parts = tok.split('.')
                                    try:
                                        n_alt = float(parts[0] + '.' + ''.join(parts[1:]))
                                        if n_alt > 0 and n_alt not in nums:
                                            nums.append(n_alt)
                                    except Exception:
                                        pass
                                    if len(parts) > 2 and all(p.isdigit() for p in parts):
                                        if all(len(p) == 3 for p in parts[1:]):
                                            try:
                                                n_int = float(''.join(parts))
                                                if n_int > 0 and n_int not in nums:
                                                    nums.append(n_int)
                                            except Exception:
                                                pass

                    year_val = None
                    if date_val and len(date_val) >= 4:
                        try:
                            year_val = int(date_val[:4])
                        except ValueError:
                            pass
                    m_ars, price, qty = resolve_amounts(nums, coin_val, year=year_val)

                    if coin_val == 'USDT' and price >= 5_000_000:
                        coin_val = 'BTC'
                    elif coin_val == 'USDT' and price >= 1_000_000:
                        coin_val = 'ETH'
                    elif coin_val == 'USDT' and price >= 100_000:
                        coin_val = 'BNB'
                    elif coin_val == 'BTC' and 0 < price < 1_500_000:
                        coin_val = 'USDT'

                    if m_ars > 0 or qty > 0:
                        m_compra = qty if op_type == 'Compra' else 0.0
                        m_venta = qty if op_type == 'Venta' else 0.0
                        c_compra = price if op_type == 'Compra' else 0.0
                        c_venta = price if op_type == 'Venta' else 0.0
                        if c_compra == 0.0 and m_compra > 0 and m_ars > 0:
                            c_compra = round(m_ars / m_compra, 2)
                        if c_venta == 0.0 and m_venta > 0 and m_ars > 0:
                            c_venta = round(m_ars / m_venta, 2)

                        sig = (date_val, op_type, coin_val, round(qty, 8), round(m_ars, 2))
                        occ_idx = page_sig_counts.get(sig, 0) + 1
                        page_sig_counts[sig] = occ_idx
                        unique_ref = f"Certificación C.P.N. (Pág {p_idx+1})" if occ_idx == 1 else f"Certificación C.P.N. (Pág {p_idx+1} #{occ_idx})"
                        tx_hash = compute_canonical_tx_hash(
                            date_val, current_exchange, op_type, coin_val,
                            m_compra, m_venta, m_ars, unique_ref
                        )
                        extracted_txs.append({
                            "tx_hash": tx_hash, "Fecha": date_val, "Exchange": current_exchange,
                            "Tipo de Operación": op_type, "Moneda": coin_val,
                            "Monto Compra (Cripto)": m_compra, "Monto Venta (Cripto)": m_venta,
                            "Cotización Compra": c_compra, "Cotización Venta": c_venta,
                            "Monto ARS": m_ars, "Comentarios": unique_ref
                        })
                        last_row_end = end_win if hit_boundary else (i + 1)
                        i = next_i
                        continue
            i += 1

    unique_txs = []
    seen = set()
    for tx in extracted_txs:
        if tx['tx_hash'] not in seen:
            seen.add(tx['tx_hash'])
            unique_txs.append(tx)
    unique_txs.sort(key=lambda x: x['Fecha'])
    return unique_txs
