"""
Servicio de enriquecimiento y diagnóstico de brechas históricas de inventario.
Audita pistas de transferencias inter-exchange, frescura y retiros huérfanos.
Referencia de diseño: docs/especificacion_fifo_prioridades.md
"""

from datetime import datetime, timedelta
import pandas as pd
from db.connection import get_connection
from models.transaction_models import get_canonical_exchange_root, canonicalize_ticker
from services.monthly_custody_service import calculate_monthly_custody, _is_cold_storage_transfer
from services.orphan_transfer_service import detect_orphan_withdrawals
from services.source_declarations_service import get_source_declarations, is_source_exempted
from services.source_freshness_service import evaluate_source_freshness_and_alerts
from services.gap_intervals_service import (
    _parse_gap_date,
    group_gaps_into_root_intervals,
    _generate_recommended_action
)


def enrich_gaps_with_clues(gaps, match_window_days=30, amount_tolerance_pct=0.05, year=None):
    """
    Post-processes raw FIFO gaps with cross-exchange intelligence, stale data checks,
    orphan withdrawal detection, custody deficits, and monthly custody diagnostics.
    """
    if gaps is None:
        gaps = []

    empty_res = {
        "gaps": gaps, "root_gaps": [], "total_root_gaps": 0,
        "summary": {"with_probable_match": 0, "missing_data_source": 0, "unknown_origin": len(gaps)},
        "exchange_freshness": [], "custody_deficits": [], "source_alerts": [],
        "declared_sources": [], "orphan_withdrawals": [], "monthly_custody": {}
    }
    conn = get_connection()
    try:
        all_tx_df = pd.read_sql_query(
            "SELECT fecha, exchange, moneda, tipo_operacion, monto_compra_cripto, monto_venta_cripto, comentarios FROM transactions ORDER BY fecha ASC",
            conn
        )
    except Exception as e:
        print(f"Error loading transactions for gap enrichment: {e}")
        return empty_res
    finally:
        conn.close()

    if all_tx_df.empty:
        return empty_res

    all_tx_df['exchange_root'] = all_tx_df['exchange'].apply(get_canonical_exchange_root)
    all_tx_df['tipo_lower'] = all_tx_df['tipo_operacion'].astype(str).str.lower()
    all_tx_df['fecha_dt'] = pd.to_datetime(all_tx_df['fecha'], errors='coerce')
    all_tx_df['coin_clean'] = all_tx_df['moneda'].apply(canonicalize_ticker)

    cold_pattern = r'cold|fria|fría|ledger|trezor|hardware|personal|custodia|self-custody|autocustodia|metamask|trust wallet|exodus|safepal|tangem|bitbox|keepkey|phantom|rabby'
    outflow_pattern = r'retiro|envio|envío|withdraw|transfer|send|egreso|salida|extraccion|extracción'
    sale_pattern = r'venta|sell|consumo|pago|payment'
    _top = all_tx_df['tipo_lower']
    _coment = all_tx_df['comentarios'].fillna('').astype(str).str.lower()
    _ex = all_tx_df['exchange'].fillna('').astype(str).str.lower()
    _ex_r = all_tx_df['exchange_root'].fillna('').astype(str).str.lower()
    _is_sale = _top.str.contains(sale_pattern, regex=True, na=False)
    _is_out = _top.str.contains(outflow_pattern, regex=True, na=False)
    _is_cold_top = _top.str.contains(cold_pattern, regex=True, na=False)
    _is_cold_meta = _coment.str.contains(cold_pattern, regex=True, na=False) | _ex.str.contains(cold_pattern, regex=True, na=False) | _ex_r.str.contains(cold_pattern, regex=True, na=False)
    _mv = all_tx_df['monto_venta_cripto'].fillna(0) > 0
    all_tx_df['is_cold_storage_transfer'] = (~_is_sale) & ((_is_cold_top | (_is_out & _is_cold_meta)) & (_is_out | _is_cold_top | _mv))

    # 1. Withdrawals index
    withdrawal_mask = (
        all_tx_df['tipo_lower'].str.contains('retiro|envio|withdraw', na=False) &
        (all_tx_df['monto_venta_cripto'].fillna(0) > 0)
    )
    withdrawals_df = all_tx_df[withdrawal_mask].copy()

    # 2. Deposits and P2P Funding index
    p2p_mask = (
        (all_tx_df['exchange'].astype(str).str.contains('p2p', case=False, na=False) |
         all_tx_df['comentarios'].astype(str).str.contains('p2p', case=False, na=False)) &
        (all_tx_df['monto_compra_cripto'].fillna(0) > 0)
    )
    deposit_mask = (
        (all_tx_df['tipo_lower'].str.contains('deposito|ingreso|deposit', na=False) &
         ~all_tx_df['tipo_lower'].str.contains('compra|buy', na=False) &
         (all_tx_df['monto_compra_cripto'].fillna(0) > 0)) |
        p2p_mask
    )
    deposits_df = all_tx_df[deposit_mask].copy()
    exchanges_with_deposits = set()
    if not deposits_df.empty:
        for _, row in deposits_df.iterrows():
            exchanges_with_deposits.add((row['exchange_root'], str(row['coin_clean']).upper()))

    # 3. Converts / Swaps index
    convert_mask = all_tx_df['comentarios'].astype(str).str.contains('CONVERT|AUTO-INVEST', case=False, na=False)
    converts_df = all_tx_df[convert_mask].copy()
    exchanges_with_converts = set()
    if not converts_df.empty:
        for _, row in converts_df.iterrows():
            exchanges_with_converts.add((row['exchange_root'], str(row['coin_clean']).upper()))

    # 4 & 5. Freshness, Stale Sources index, and intelligent source alerts
    today = datetime.now()
    active_declarations = get_source_declarations()
    freshness, source_alerts, declared_sources = evaluate_source_freshness_and_alerts(
        all_tx_df=all_tx_df,
        today=today,
        active_declarations=active_declarations
    )

    # 6. Physical custody deficits per exchange in target fiscal year
    if year:
        try:
            target_year = int(year)
        except (ValueError, TypeError):
            target_year = None
    else:
        target_year = None

    if target_year is None:
        v_dates = pd.to_datetime(all_tx_df['fecha'], errors='coerce').dropna()
        v_dates = v_dates[v_dates <= (today + timedelta(days=1))]
        target_year = int(v_dates.max().year) if not v_dates.empty else today.year

    all_tx_df['fecha_ts'] = pd.to_datetime(all_tx_df['fecha'], errors='coerce')
    start_ts = pd.Timestamp(f"{target_year}-01-01 00:00:00")
    end_ts = pd.Timestamp(f"{target_year}-12-31 23:59:59")
    df_target = all_tx_df[(all_tx_df['fecha_ts'] >= start_ts) & (all_tx_df['fecha_ts'] <= end_ts)].copy()

    custody_deficits = []

    for ex_root, group in df_target.groupby('exchange_root'):
        for coin, coin_group in group.groupby('coin_clean'):
            if not coin or coin in ('ARS', 'USD', 'EUR', 'NONE'):
                continue
            buys = float(coin_group['monto_compra_cripto'].sum() or 0.0)
            sells = float(coin_group[~coin_group['is_cold_storage_transfer']]['monto_venta_cripto'].sum() or 0.0)
            has_dep = (ex_root, coin) in exchanges_with_deposits
            is_stable = coin in ('USDT', 'USDC', 'DAI', 'BUSD')
            dust_tolerance = 1.0 if is_stable else 1e-4
            if sells > buys + dust_tolerance:
                def_amt = round(sells - buys, 4)

                prior_mask = (all_tx_df['fecha_ts'] < start_ts) & (all_tx_df['exchange_root'] == ex_root) & (all_tx_df['coin_clean'] == coin)
                prior_df = all_tx_df[prior_mask]
                if not prior_df.empty and 'monto_compra_cripto' in prior_df.columns and 'monto_venta_cripto' in prior_df.columns:
                    prior_b = float(prior_df['monto_compra_cripto'].sum() or 0.0)
                    prior_s = float(prior_df[~prior_df['is_cold_storage_transfer']]['monto_venta_cripto'].sum() or 0.0)
                    prior_balance = max(0.0, round(prior_b - prior_s, 4))
                else:
                    prior_balance = 0.0

                is_covered = prior_balance >= def_amt
                if not is_covered:
                    withdrawals = float(coin_group[coin_group['tipo_lower'].str.contains('retiro|envio|withdraw', na=False)]['monto_venta_cripto'].sum() or 0.0)
                    actual_sales = float(coin_group[coin_group['tipo_lower'].str.contains('venta|sell|consumo|pago', na=False)]['monto_venta_cripto'].sum() or 0.0)
                    prior_note = f" (saldo previo: {prior_balance:,.2f} {coin})" if prior_balance > 0 else ""
                    breakdown_note = f" [{actual_sales:,.2f} ventas + {withdrawals:,.2f} retiros]" if withdrawals > 0 and actual_sales > 0 else ""

                    custody_deficits.append({
                        "exchange": ex_root,
                        "coin": coin,
                        f"total_buys_{target_year}": round(buys, 2),
                        f"total_sells_{target_year}": round(sells, 2),
                        "total_buys": round(buys, 2),
                        "total_sells": round(sells, 2),
                        "year": target_year,
                        "deficit": def_amt,
                        "prior_balance": prior_balance,
                        "is_covered_by_prior": False,
                        "has_deposits": has_dep,
                        "message": (
                            f"Déficit de custodia en {ex_root}: ventas en {target_year} ({sells:,.2f} {coin}{breakdown_note}) superan a "
                            f"compras ({buys:,.2f} {coin}) por {def_amt:,.2f} {coin}{prior_note}. "
                            f"Cargá los depósitos o compras de origen de {ex_root} (o transferencias desde otros exchanges/wallets)."
                        )
                    })

                if sells >= 10000.0 and not has_dep and sells > (buys + prior_balance + dust_tolerance):
                    source_alerts.append({
                        "type": "missing_deposit_history",
                        "exchange": ex_root,
                        "coin": coin,
                        "sales_volume": round(sells, 2),
                        "year": target_year,
                        "severity": "ALTA",
                        "message": (
                            f"Falta historial de depósitos en {ex_root}: registra {sells:,.2f} {coin} de ventas en {target_year} "
                            f"pero carece de depósitos cripto registrados. Cargá el historial de depósitos."
                        )
                    })

    counters = {"with_probable_match": 0, "missing_data_source": 0, "unknown_origin": 0}

    import collections
    # 1. Precalculate sum of sales per (exchange_root, coin_clean) for fast O(1) lookup
    coin_sells_map = (
        all_tx_df.groupby(['exchange_root', 'coin_clean'])['monto_venta_cripto']
        .sum()
        .to_dict()
    )

    # 2. Pre-index deposits by exchange_root
    deposits_by_exchange = collections.defaultdict(list)
    if not deposits_df.empty:
        valid_deps = deposits_df[deposits_df['fecha_dt'].notna()]
        for d_row in valid_deps[['exchange_root', 'coin_clean', 'monto_compra_cripto', 'fecha_dt']].to_dict('records'):
            deposits_by_exchange[d_row['exchange_root']].append(d_row)

    # 3. Pre-index withdrawals by coin_clean
    withdrawals_by_coin = collections.defaultdict(list)
    if not withdrawals_df.empty:
        valid_w = withdrawals_df[withdrawals_df['fecha_dt'].notna()]
        for w_row in valid_w[['exchange', 'exchange_root', 'coin_clean', 'monto_venta_cripto', 'fecha_dt']].to_dict('records'):
            withdrawals_by_coin[w_row['coin_clean']].append(w_row)

    # 4. Pre-index custody deficits by (exchange, coin)
    custody_deficit_map = {(cd['exchange'], cd['coin']): cd for cd in custody_deficits}

    # 7. Enrich each gap
    for gap in gaps:
        clues = []
        gap_exchange_root = get_canonical_exchange_root(gap.get('origin_exchange') or gap['exchange'])
        gap_coin = canonicalize_ticker(str(gap['coin']).upper())
        gap_amount = float(gap.get('deficit', 0) or gap.get('sold_qty', 0))

        try:
            gap_date = pd.to_datetime(gap['date'], errors='coerce')
        except Exception:
            gap_date = None

        display_exchange = gap.get('origin_exchange') or gap.get('exchange', '')

        # Clue 0: Same-exchange unconsumed deposit / app swap match (100% CERTEZA)
        if gap_date is not None and gap_exchange_root in deposits_by_exchange:
            cand_deps = deposits_by_exchange[gap_exchange_root]
            s_window_start = gap_date - timedelta(days=14)
            s_window_end = gap_date + timedelta(hours=24)
            for dep_row in cand_deps:
                if dep_row['coin_clean'] == gap_coin:
                    continue
                dep_dt = dep_row['fecha_dt']
                if not (s_window_start <= dep_dt <= s_window_end):
                    continue
                dep_amount = float(dep_row['monto_compra_cripto'] or 0)
                if dep_amount <= 0:
                    continue
                dep_coin = dep_row['coin_clean']
                dep_coin_sells = coin_sells_map.get((gap_exchange_root, dep_coin), 0.0)

                if dep_coin_sells < dep_amount * 0.5:
                    date_diff_hours = int((gap_date - dep_dt).total_seconds() / 3600)
                    if abs(date_diff_hours) < 24:
                        t_desc = "el mismo día" if abs(date_diff_hours) < 8 else f"{abs(date_diff_hours)}h antes"
                    else:
                        d_days = abs((gap_date - dep_dt).days)
                        t_desc = f"{d_days} día{'s' if d_days > 1 else ''} antes"

                    clues.append({
                        "type": "same_exchange_swap_match",
                        "confidence": "certera",
                        "icon": "🎯",
                        "source_exchange": display_exchange,
                        "source_coin": dep_coin,
                        "source_date": str(dep_dt.date()),
                        "source_amount": round(dep_amount, 4),
                        "message": f"Causa 100% Certera: En {display_exchange} ingresaron {dep_amount:,.4f} {dep_coin} el {str(dep_dt.date())} ({t_desc}) y esta venta de {gap_coin} proviene de haberlos convertido en la App. La API no transmite este canje, pero SÍ figura en el reporte descargable de {display_exchange}: podés subir el extracto de conversiones para resolverlo solo, o confirmarlo con el botón Resolver."
                    })
                    break

        # Clue 1: Cross-exchange matches (chronological causality)
        if gap_date is not None and gap_coin in withdrawals_by_coin:
            cand_w = withdrawals_by_coin[gap_coin]
            window_start = gap_date - timedelta(days=match_window_days)
            window_end = gap_date + timedelta(hours=14)
            matches = []
            is_stable = gap_coin in ('USDT', 'USDC', 'DAI', 'BUSD')
            abs_tolerance = 10.0 if is_stable else (0.001 if gap_coin == 'BTC' else 0.05)

            for w_row in cand_w:
                if w_row['exchange_root'] == gap_exchange_root:
                    continue
                w_dt = w_row['fecha_dt']
                if not (window_start <= w_dt <= window_end):
                    continue
                w_amount = float(w_row['monto_venta_cripto'] or 0)
                if w_amount <= 0:
                    continue
                amount_diff_pct = abs(w_amount - gap_amount) / max(gap_amount, 0.01)

                if amount_diff_pct <= amount_tolerance_pct or (abs(w_amount - gap_amount) <= abs_tolerance and amount_diff_pct <= 0.15):
                    confidence = "alta"
                elif amount_diff_pct <= 0.25 or (w_amount > gap_amount and (gap_amount / w_amount) >= 0.33):
                    confidence = "media"
                else:
                    continue

                date_diff_days = abs((gap_date - w_dt).days)
                if w_dt > gap_date:
                    diff_hours = max(1, int((w_dt - gap_date).total_seconds() / 3600))
                    time_desc = f"{diff_hours}h después (posible desfasaje horario UTC)"
                elif date_diff_days == 0:
                    time_desc = "el mismo día"
                else:
                    time_desc = f"{date_diff_days} día{'s' if date_diff_days > 1 else ''} antes"

                matches.append({
                    "type": "cross_exchange_match", "confidence": confidence, "icon": "🔗",
                    "source_exchange": w_row['exchange'], "source_date": str(w_dt.date()),
                    "source_amount": round(w_amount, 4),
                    "message": f"Hipótesis orientativa: {w_row['exchange']} tiene un retiro de {w_amount:,.4f} {gap_coin} el {str(w_dt.date())} ({time_desc})",
                    "_score": amount_diff_pct + (date_diff_days * 0.01)
                })

            matches.sort(key=lambda m: m['_score'])
            for m in matches[:3]:
                del m['_score']
                clues.append(m)

        # Clue 2: Missing data sources
        has_deposits = (gap_exchange_root, gap_coin) in exchanges_with_deposits
        has_converts = (gap_exchange_root, gap_coin) in exchanges_with_converts

        display_exchange = gap.get('origin_exchange') or gap.get('exchange', '')
        if not has_deposits:
            clues.append({
                "type": "missing_data_source", "confidence": "media", "icon": "🔍", "data_type": "deposits",
                "message": f"Sugerencia de búsqueda: No hay historial de depósitos de {gap_coin} cargado para {display_exchange}. Descargá el historial de depósitos/transferencias desde tu cuenta."
            })

        if not has_converts and gap_coin in ('USDC', 'USDT', 'DAI', 'BTC', 'ETH', 'SOL'):
            clues.append({
                "type": "missing_data_source", "confidence": "baja", "icon": "🔄", "data_type": "converts",
                "message": f"No hay historial de conversiones/swaps cargado para {display_exchange}. Si realizaste conversiones internas, descargá ese extracto."
            })

        # Clue 3: Stale data warning
        if gap_exchange_root in freshness and freshness[gap_exchange_root]['stale']:
            f_info = freshness[gap_exchange_root]
            clues.append({
                "type": "stale_data", "confidence": "info", "icon": "📅",
                "message": f"Los datos de {gap['exchange']} están actualizados hasta {f_info['last_tx_date']} ({f_info['days_behind_latest']} días por detrás del sistema). Puede haber operaciones no cargadas."
            })

        # Clue 4: Custody deficit guide
        cd = custody_deficit_map.get((gap_exchange_root, gap_coin))
        if cd:
            clues.append({
                "type": "custody_deficit", "confidence": "alta", "icon": "⚠️",
                "message": f"Alerta de Custodia: {cd['exchange']} tiene un déficit de {cd['deficit']:,.2f} {cd['coin']} en {target_year}. Se requiere registrar los depósitos de {cd['exchange']} o transferencias de origen."
            })

        recommended_action = _generate_recommended_action(clues, gap, gap_exchange_root)
        has_match = any(c['type'] in ('cross_exchange_match', 'same_exchange_swap_match') for c in clues)
        has_missing = any(c['type'] == 'missing_data_source' for c in clues)

        if has_match:
            counters["with_probable_match"] += 1
            gap["category"] = "probable_match"
        elif has_missing:
            counters["missing_data_source"] += 1
            gap["category"] = "missing_data"
        else:
            counters["unknown_origin"] += 1
            gap["category"] = "unknown"

        gap["clues"] = clues
        gap["recommended_action"] = recommended_action
        gap["isGap"] = True

    orphan_alerts = detect_orphan_withdrawals(all_tx_df, withdrawals_df, deposits_df, freshness, target_year=target_year)
    source_alerts.extend(orphan_alerts)

    exchange_freshness_list = sorted(freshness.values(), key=lambda x: x['days_behind_latest'], reverse=True)
    root_gaps = group_gaps_into_root_intervals(gaps)

    monthly_custody = calculate_monthly_custody(
        all_tx_df=all_tx_df, exchanges_with_deposits=exchanges_with_deposits,
        target_year=year, gaps=gaps, withdrawals_df=withdrawals_df,
        match_window_days=match_window_days, amount_tolerance_pct=amount_tolerance_pct
    )

    return {
        "gaps": gaps, "root_gaps": root_gaps, "total_root_gaps": len(root_gaps),
        "summary": counters, "exchange_freshness": exchange_freshness_list,
        "custody_deficits": custody_deficits, "source_alerts": source_alerts,
        "declared_sources": declared_sources,
        "orphan_withdrawals": orphan_alerts, "monthly_custody": monthly_custody
    }
