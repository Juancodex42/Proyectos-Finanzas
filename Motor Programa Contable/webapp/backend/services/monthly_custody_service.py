from datetime import datetime, timedelta
import pandas as pd
from models.transaction_models import get_canonical_exchange_root, canonicalize_ticker


def _is_cold_storage_transfer(row) -> bool:
    top = str(row.get('tipo_lower') if 'tipo_lower' in row else row.get('tipo_operacion', '')).lower()
    coment = str(row.get('comentarios_lower') if 'comentarios_lower' in row else row.get('comentarios', '')).lower()
    ex = str(row.get('exchange', '')).lower()
    ex_root = str(row.get('exchange_root', '')).lower()

    cold_keywords = (
        'cold', 'fria', 'fría', 'ledger', 'trezor', 'hardware', 'personal',
        'custodia', 'self-custody', 'autocustodia', 'metamask', 'trust wallet', 'exodus',
        'safepal', 'tangem', 'bitbox', 'keepkey', 'phantom', 'rabby'
    )
    is_outflow = any(k in top for k in (
        'retiro', 'envio', 'envío', 'withdraw', 'transfer', 'send',
        'egreso', 'salida', 'extraccion', 'extracción'
    ))
    is_cold_top = any(k in top for k in cold_keywords)
    is_cold_meta = any(k in coment or k in ex or k in ex_root for k in cold_keywords)

    is_sale = any(k in top for k in ('venta', 'sell', 'consumo', 'pago', 'payment'))
    if is_sale:
        return False

    mv = float(row.get('monto_venta_cripto') or 0.0)
    return bool((is_cold_top or (is_outflow and is_cold_meta)) and (is_outflow or is_cold_top or mv > 0))


def calculate_monthly_custody(
    all_tx_df: pd.DataFrame,
    exchanges_with_deposits: set,
    target_year: int = None,
    gaps: list = None,
    withdrawals_df: pd.DataFrame = None,
    match_window_days: int = 30,
    amount_tolerance_pct: float = 0.05
) -> dict:
    """
    Computes monthly custody diagnostics per calendar month of target_year.
    For each month (e.g. '2026-07'):
      - exchanges: [{exchange, coin, buys, sells, net, has_deposits}]
      - total_deficit: Sum of net deficits where sells > buys
      - has_observations: True if deficit > 0 or sells without deposits or stale sources
      - stale_sources: [{exchange, last_date}] of exchanges whose last historical op was before month
      - probable_matches: Pairs of withdrawals in other exchanges near month sales
      - recommendations: Actionable discard suggestions
    """
    if all_tx_df is None or all_tx_df.empty:
        return {}

    # Defensive check on required columns
    all_tx_df = all_tx_df.copy()
    if 'exchange_root' not in all_tx_df.columns and 'exchange' in all_tx_df.columns:
        all_tx_df['exchange_root'] = all_tx_df['exchange'].apply(get_canonical_exchange_root)
    if 'tipo_lower' not in all_tx_df.columns and 'tipo_operacion' in all_tx_df.columns:
        all_tx_df['tipo_lower'] = all_tx_df['tipo_operacion'].astype(str).str.lower()
    if 'fecha_dt' not in all_tx_df.columns and 'fecha' in all_tx_df.columns:
        all_tx_df['fecha_dt'] = pd.to_datetime(all_tx_df['fecha'], errors='coerce')
    if 'coin_clean' not in all_tx_df.columns and 'moneda' in all_tx_df.columns:
        all_tx_df['coin_clean'] = all_tx_df['moneda'].apply(canonicalize_ticker)
    if 'comentarios_lower' not in all_tx_df.columns:
        if 'comentarios' in all_tx_df.columns:
            all_tx_df['comentarios_lower'] = all_tx_df['comentarios'].fillna('').astype(str).str.lower()
        else:
            all_tx_df['comentarios_lower'] = ''
    if 'is_cold_storage_transfer' not in all_tx_df.columns:
        cold_pattern = r'cold|fria|fría|ledger|trezor|hardware|personal|custodia|self-custody|autocustodia|metamask|trust wallet|exodus|safepal|tangem|bitbox|keepkey|phantom|rabby'
        outflow_pattern = r'retiro|envio|envío|withdraw|transfer|send|egreso|salida|extraccion|extracción'
        sale_pattern = r'venta|sell|consumo|pago|payment'
        _top = all_tx_df['tipo_lower']
        _coment = all_tx_df['comentarios_lower']
        _ex = all_tx_df['exchange'].fillna('').astype(str).str.lower() if 'exchange' in all_tx_df.columns else ''
        _ex_r = all_tx_df['exchange_root'].fillna('').astype(str).str.lower()
        _is_sale = _top.str.contains(sale_pattern, regex=True, na=False)
        _is_out = _top.str.contains(outflow_pattern, regex=True, na=False)
        _is_cold_top = _top.str.contains(cold_pattern, regex=True, na=False)
        _is_cold_meta = _coment.str.contains(cold_pattern, regex=True, na=False) | _ex.str.contains(cold_pattern, regex=True, na=False) | _ex_r.str.contains(cold_pattern, regex=True, na=False)
        _mv = all_tx_df['monto_venta_cripto'].fillna(0) > 0
        all_tx_df['is_cold_storage_transfer'] = (~_is_sale) & ((_is_cold_top | (_is_out & _is_cold_meta)) & (_is_out | _is_cold_top | _mv))

    # 1. Determine target year
    if target_year is not None:
        try:
            target_year = int(target_year)
        except (ValueError, TypeError):
            target_year = None

    if target_year is None:
        if gaps:
            for g in gaps:
                d = str(g.get('date', ''))
                if len(d) >= 4 and d[:4].isdigit():
                    target_year = int(d[:4])
                    break
        if target_year is None:
            today_now = datetime.now()
            v_dates = all_tx_df.loc[all_tx_df['fecha_dt'] <= (today_now + timedelta(days=1)), 'fecha_dt'].dropna()
            target_year = int(v_dates.max().year) if not v_dates.empty else today_now.year

    # 2. Pre-index exchange last historical dates and active exchanges in year
    today_now = datetime.now()
    exchange_last_dates = {}
    for ex_root, grp in all_tx_df.groupby('exchange_root'):
        valid_grp = grp[
            (grp['monto_compra_cripto'].fillna(0) > 0) |
            (grp['monto_venta_cripto'].fillna(0) > 0)
        ]
        v_dates = valid_grp.loc[valid_grp['fecha_dt'] <= (today_now + timedelta(days=1)), 'fecha_dt'].dropna() if not valid_grp.empty else grp.loc[grp['fecha_dt'] <= (today_now + timedelta(days=1)), 'fecha_dt'].dropna()
        if v_dates.empty:
            v_dates = valid_grp['fecha_dt'].dropna() if not valid_grp.empty else grp['fecha_dt'].dropna()
        if not v_dates.empty:
            exchange_last_dates[ex_root] = v_dates.max()

    valid_dates_all = all_tx_df.loc[all_tx_df['fecha_dt'] <= (today_now + timedelta(days=1)), 'fecha_dt'].dropna()
    latest_system_dt = valid_dates_all.max() if not valid_dates_all.empty else None
    if latest_system_dt and latest_system_dt > today_now:
        latest_system_dt = today_now

    year_mask = (all_tx_df['fecha_dt'].dt.year == target_year)
    if year_mask.any():
        year_active_exchanges = set(all_tx_df[year_mask]['exchange_root'].unique())
    else:
        year_active_exchanges = set()

    # Ensure withdrawals are ready if not provided
    if withdrawals_df is None:
        w_mask = (
            all_tx_df['tipo_lower'].str.contains('retiro|envio|withdraw', na=False) &
            (all_tx_df['monto_venta_cripto'].fillna(0) > 0)
        )
        withdrawals_df = all_tx_df[w_mask].copy()

    monthly_custody = {}

    # Track accumulated monthly balance carryover (arrastre de saldos) per exchange and coin
    cumulative_balances = {}
    prior_year_mask = all_tx_df['fecha_dt'] < pd.to_datetime(f"{target_year}-01-01 00:00:00")
    prior_tx = all_tx_df[prior_year_mask]
    if not prior_tx.empty:
        for (ex_root, coin), p_grp in prior_tx.groupby(['exchange_root', 'coin_clean']):
            if not coin or coin in ('ARS', 'USD', 'EUR', 'NONE'):
                continue
            pb = float(p_grp['monto_compra_cripto'].fillna(0).sum())
            ps = float(p_grp[~p_grp['is_cold_storage_transfer']]['monto_venta_cripto'].fillna(0).sum())
            cumulative_balances[(ex_root, coin)] = max(0.0, pb - ps)

    import collections
    withdrawals_by_coin = collections.defaultdict(list)
    if withdrawals_df is not None and not withdrawals_df.empty:
        w_valid = withdrawals_df[withdrawals_df['fecha_dt'].notna()]
        for w_dict in w_valid[['exchange', 'exchange_root', 'coin_clean', 'monto_venta_cripto', 'fecha_dt']].to_dict('records'):
            withdrawals_by_coin[w_dict['coin_clean']].append(w_dict)

    # 3. Iterate 12 calendar months
    for m in range(1, 13):
        month_str = f"{target_year}-{m:02d}"
        month_start_dt = pd.to_datetime(f"{month_str}-01 00:00:00")
        month_mask = (all_tx_df['fecha_dt'].dt.year == target_year) & (all_tx_df['fecha_dt'].dt.month == m)
        month_tx = all_tx_df[month_mask].copy()

        exchanges_list = []
        month_deficit = 0.0
        deficits_by_coin = {}

        if not month_tx.empty:
            for (ex_root, coin), c_grp in month_tx.groupby(['exchange_root', 'coin_clean']):
                if not coin or coin in ('ARS', 'USD', 'EUR', 'NONE'):
                    continue
                b = float(round(c_grp['monto_compra_cripto'].fillna(0).sum(), 8))
                s = float(round(c_grp[~c_grp['is_cold_storage_transfer']]['monto_venta_cripto'].fillna(0).sum(), 8))
                if b == 0 and s == 0:
                    continue
                net = round(b - s, 8)
                has_dep = (ex_root, coin) in exchanges_with_deposits
                prev_balance = cumulative_balances.get((ex_root, coin), 0.0)
                exchanges_list.append({
                    "exchange": ex_root,
                    "coin": coin,
                    "buys": b,
                    "sells": s,
                    "net": net,
                    "prior_balance": prev_balance,
                    "has_deposits": has_dep
                })
                available = prev_balance + b
                if s > available + 1e-4:
                    c_def = round(s - available, 8)
                    from models.transaction_models import get_quote_usd_value
                    usd_val = get_quote_usd_value(coin, c_def, fecha=month_start_dt)
                    month_deficit += usd_val
                    deficits_by_coin[coin] = round(deficits_by_coin.get(coin, 0.0) + c_def, 8)
                    cumulative_balances[(ex_root, coin)] = 0.0
                else:
                    cumulative_balances[(ex_root, coin)] = max(0.0, available - s)

        exchanges_list.sort(key=lambda x: (x['exchange'], x['coin']))
        total_deficit = round(month_deficit, 2)

        # 4. Stale sources: last historical operation was strictly before this month
        stale_sources = []
        if latest_system_dt is not None and month_start_dt <= latest_system_dt:
            from services.source_declarations_service import is_source_exempted
            for ex_root in sorted(year_active_exchanges):
                last_dt = exchange_last_dates.get(ex_root)
                if last_dt and last_dt < month_start_dt and not is_source_exempted(ex_root):
                    stale_sources.append({
                        "exchange": ex_root,
                        "last_date": str(last_dt.date())
                    })

        # 5. Probable cross-exchange matches for the month
        probable_matches = []
        seen_matches = set()

        # A. From gaps
        if gaps:
            for g in gaps:
                g_date = str(g.get('date', ''))
                if g_date.startswith(month_str):
                    for clue in g.get('clues', []):
                        if clue.get('type') == 'cross_exchange_match':
                            m_key = (clue.get('source_exchange'), clue.get('source_date'), clue.get('source_amount'))
                            if m_key not in seen_matches:
                                seen_matches.add(m_key)
                                probable_matches.append({
                                    "target_exchange": g.get('origin_exchange') or g.get('exchange'),
                                    "target_date": g_date[:10],
                                    "target_amount": float(g.get('deficit') or g.get('sold_qty') or 0.0),
                                    "source_exchange": clue.get('source_exchange'),
                                    "source_date": clue.get('source_date'),
                                    "source_amount": clue.get('source_amount'),
                                    "coin": g.get('coin'),
                                    "confidence": clue.get('confidence', 'media'),
                                    "message": clue.get('message', '')
                                })

        # B. Fallback: match monthly deficit sales against nearby withdrawals in other exchanges
        if not probable_matches and not month_tx.empty and withdrawals_by_coin:
            sales_mask = (
                (~month_tx['is_cold_storage_transfer']) &
                (month_tx['monto_venta_cripto'].fillna(0) > 0) &
                (~month_tx['tipo_lower'].str.contains('retiro|envio|withdraw|transfer|egreso|salida|extraccion', na=False)) &
                (month_tx['fecha_dt'].notna())
            )
            sales_records = month_tx[sales_mask][['exchange', 'exchange_root', 'coin_clean', 'monto_venta_cripto', 'fecha_dt']].to_dict('records')
            for s_row in sales_records:
                s_coin = s_row['coin_clean']
                s_amt = float(s_row['monto_venta_cripto'])
                s_date = s_row['fecha_dt']
                s_ex = s_row['exchange_root']

                cand_w = withdrawals_by_coin.get(s_coin, [])
                if not cand_w:
                    continue

                w_start = s_date - timedelta(days=match_window_days)
                w_end = s_date + timedelta(hours=14)
                for w_row in cand_w:
                    if w_row['exchange_root'] == s_ex:
                        continue
                    w_date = w_row['fecha_dt']
                    if not (w_start <= w_date <= w_end):
                        continue
                    w_amt = float(w_row['monto_venta_cripto'])
                    if w_amt <= 0:
                        continue
                    amt_diff = abs(w_amt - s_amt) / max(s_amt, 0.01)
                    if amt_diff <= amount_tolerance_pct or (abs(w_amt - s_amt) <= 10.0 and amt_diff <= 0.15):
                        m_key = (w_row['exchange'], str(w_date.date()), round(w_amt, 4))
                        if m_key not in seen_matches:
                            seen_matches.add(m_key)
                            probable_matches.append({
                                "target_exchange": s_row['exchange'],
                                "target_date": str(s_date.date()),
                                "target_amount": round(s_amt, 4),
                                "source_exchange": w_row['exchange'],
                                "source_date": str(w_date.date()),
                                "source_amount": round(w_amt, 4),
                                "coin": s_coin,
                                "confidence": "alta" if amt_diff <= amount_tolerance_pct else "media",
                                "message": f"Retiro coincidente en {w_row['exchange']} ({w_amt:,.4f} {s_coin}) el {str(w_date.date())}"
                            })
                            if len(probable_matches) >= 10:
                                break
                if len(probable_matches) >= 10:
                    break

        # 6. Actionable recommendations
        recommendations = []
        rec_exchanges_seen = set()

        for ex_item in exchanges_list:
            ex_name = ex_item['exchange']
            c_name = ex_item['coin']
            ex_prior = ex_item.get('prior_balance', 0.0)
            if (ex_item['sells'] > (ex_prior + ex_item['buys'] + 1e-4)) and not ex_item['has_deposits']:
                from services.source_declarations_service import is_source_exempted
                if not is_source_exempted(ex_name) and ex_name not in rec_exchanges_seen:
                    rec_exchanges_seen.add(ex_name)
                    recommendations.append(f"Cargar depósitos de {ex_name}")

        for stale in stale_sources:
            from services.source_freshness_service import resolve_exchange_api_info
            ex_info = resolve_exchange_api_info(stale['exchange'])
            if ex_info.get("is_api") and ex_info.get("has_credentials"):
                recommendations.append(f"Sincronizar API de {stale['exchange']}")
            else:
                recommendations.append(f"Cargar extracto de {stale['exchange']}")

        for match in probable_matches[:2]:
            recommendations.append(
                f"Verificar retiro de {match['source_exchange']} hacia {match['target_exchange']}"
            )

        if not recommendations:
            if total_deficit > 0:
                recommendations.append("Investigar fuentes de compras o depósitos faltantes.")
            else:
                recommendations.append("Sin observaciones de custodia para este período.")

        # 7. Observations flag
        from services.source_declarations_service import is_source_exempted
        has_obs = (
            (total_deficit > 1e-4) or
            len(deficits_by_coin) > 0 or
            any((e['sells'] > (e.get('prior_balance', 0.0) + e['buys'] + 1e-4)) and not e['has_deposits'] and not is_source_exempted(e['exchange']) for e in exchanges_list) or
            len(stale_sources) > 0
        )

        monthly_custody[month_str] = {
            "month": month_str,
            "year": target_year,
            "exchanges": exchanges_list,
            "total_deficit": total_deficit,
            "deficits_by_coin": deficits_by_coin,
            "has_observations": bool(has_obs),
            "stale_sources": stale_sources,
            "probable_matches": probable_matches,
            "recommendations": recommendations
        }

    return monthly_custody
