"""
Servicio de agrupamiento de brechas temporales en intervalos raíz.
Particiona cascadas de descubiertos contables y formula acciones recomendadas.
Referencia de diseño: docs/especificacion_fifo_prioridades.md
"""

import re
import pandas as pd
from collections import defaultdict


def _parse_gap_date(val):
    if not val:
        return pd.Timestamp.min
    try:
        val_s = str(val).strip()
        val_norm = re.sub(
            r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sept|sep|set|oct|nov|dic)\b',
            lambda m: {
                'ene': 'jan', 'enero': 'january', 'feb': 'feb', 'febrero': 'february', 'mar': 'mar', 'marzo': 'march',
                'abr': 'apr', 'abril': 'april', 'may': 'may', 'mayo': 'may', 'jun': 'jun', 'junio': 'june',
                'jul': 'jul', 'julio': 'july', 'ago': 'aug', 'agosto': 'august', 'sep': 'sep', 'sept': 'sep',
                'septiembre': 'september', 'set': 'sep', 'setiembre': 'september', 'oct': 'oct', 'octubre': 'october',
                'nov': 'nov', 'noviembre': 'november', 'dic': 'dec', 'diciembre': 'december'
            }.get(m.group(0).lower(), m.group(0)),
            val_s,
            flags=re.IGNORECASE
        )
        dayfirst = not bool(re.match(r'^\d{4}', val_norm))
        parsed = pd.to_datetime(val_norm, dayfirst=dayfirst, errors='coerce')
        return parsed if pd.notna(parsed) else pd.Timestamp.min
    except Exception:
        return pd.Timestamp.min


def group_gaps_into_root_intervals(gaps):
    """
    Groups cascading deficit gaps into discrete, actionable Root Gaps (Baches Raíz).
    Partitions intervals across prolonged time breaks (>30 days) and calculates
    the true cumulative deficit required to resolve the entire uncovered sale chain.
    """
    if not gaps:
        return []

    sorted_gaps = sorted(gaps, key=lambda g: _parse_gap_date(g.get('date')))
    grouped = defaultdict(list)
    for g in sorted_gaps:
        ex = g.get('origin_exchange') or g.get('exchange') or 'General'
        coin = g.get('coin') or g.get('crypto') or 'USDT'
        grouped[(ex, coin)].append(g)

    root_gaps = []
    for (ex, coin), ex_gaps in grouped.items():
        current_root = None
        batch_base_rd = 0.0
        batch_start_def = 0.0
        prev_running = None
        for g in ex_gaps:
            g_date = str(g.get('date', ''))
            g_def = float(g.get('deficit', 0) or 0)
            g_sold = float(g.get('sold_qty', 0) or 0)
            g_running = float(g.get('running_deficit', g_def) if g.get('running_deficit') is not None else g_def)

            time_gap = False
            deficit_reset = False
            if current_root:
                dt_curr = _parse_gap_date(g_date)
                dt_prev = _parse_gap_date(current_root["end_date"])
                if dt_curr != pd.Timestamp.min and dt_prev != pd.Timestamp.min:
                    if abs((dt_curr - dt_prev).days) > 30:
                        time_gap = True
                if prev_running is not None and g_running < prev_running - 1e-6:
                    deficit_reset = True

            if current_root is None or time_gap or deficit_reset:
                if current_root:
                    root_gaps.append(current_root)
                batch_base_rd = g_running
                batch_start_def = g_def
                current_root = {
                    "root_id": f"root_{ex}_{coin}_{g_date[:10]}_{len(root_gaps)+1}",
                    "exchange": ex, "coin": coin,
                    "start_date": g_date, "end_date": g_date,
                    "peak_deficit": g_def, "deficit": g_def,
                    "total_sold": g_sold, "affected_tx_count": 1,
                    "target_exchange": ex,
                    "target_hint": f"Ventas en descubierto sin lote de compra previo en {ex} ({coin})",
                    "sample_gap": g
                }
            else:
                current_root["end_date"] = g_date
                current_root["total_sold"] = round(current_root["total_sold"] + g_sold, 8)
                current_root["affected_tx_count"] += 1
                rd_delta = max(0.0, g_running - batch_base_rd)
                batch_peak = max(current_root["peak_deficit"], round(batch_start_def + rd_delta, 8))
                current_root["peak_deficit"] = batch_peak
                current_root["deficit"] = current_root["peak_deficit"]

            prev_running = g_running

        if current_root:
            root_gaps.append(current_root)

    root_gaps.sort(key=lambda r: _parse_gap_date(r["start_date"]))
    return root_gaps


def _generate_recommended_action(clues, gap, exchange_root):
    """Generate a human-readable recommended action based on the clues found."""
    parts = []
    swap_clues = [c for c in clues if c['type'] == 'same_exchange_swap_match']
    match_clues = [c for c in clues if c['type'] == 'cross_exchange_match']
    missing_clues = [c for c in clues if c['type'] == 'missing_data_source']
    custody_clues = [c for c in clues if c['type'] == 'custody_deficit']
    display_ex = gap.get('origin_exchange') or gap.get('exchange', exchange_root)

    if swap_clues:
        sc = swap_clues[0]
        parts.append(f"Cargá el extracto de conversiones de {display_ex} (descargable desde su web) para conciliarlo automáticamente, o confirmalo con el botón Resolver")
    elif custody_clues:
        parts.append(f"Cargá depósitos de {display_ex} o transferencias de origen")
    elif match_clues:
        parts.append(f"Verificá si el retiro de {match_clues[0].get('source_exchange', 'otro exchange')} corresponde a esta operación")

    if missing_clues:
        data_types = set(c.get('data_type', 'deposits') for c in missing_clues)
        if 'deposits' in data_types and not custody_clues:
            parts.append(f"Descargá el historial de depósitos de {display_ex}")
        if 'converts' in data_types:
            parts.append(f"Descargá el historial de conversiones de {display_ex}")

    if not parts:
        parts.append(f"Investigá el origen de {gap.get('deficit', 0):.4f} {gap['coin']}: posible depósito desde wallet personal, airdrop, o exchange no registrado")

    return ". ".join(parts) + "."
