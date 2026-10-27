import re
from datetime import datetime, timedelta
import pandas as pd
from models.transaction_models import get_canonical_exchange_root, canonicalize_ticker, extract_transfer_txid
from services.monthly_custody_service import _is_cold_storage_transfer
from services.source_declarations_service import is_source_exempted

_extract_transfer_txid = extract_transfer_txid


def _format_exchange_display(ex_root: str) -> str:
    u = str(ex_root or "").strip().upper()
    if u in ("OKX", "BUSD"):
        return u
    return u.title()


def detect_orphan_withdrawals(
    all_tx_df: pd.DataFrame, withdrawals_df: pd.DataFrame = None,
    deposits_df: pd.DataFrame = None, freshness: dict = None, target_year: int = None
) -> list:
    """
    Universal cross-exchange orphan withdrawal detector (Any Exchange -> Any Exchange).
    Identifies outgoing crypto withdrawals that lack a corresponding incoming deposit
    in any other exchange within the system.
    """
    if all_tx_df is None or all_tx_df.empty:
        return []

    def _ensure_cols(frame):
        cols_needed = {'exchange_root', 'tipo_lower', 'fecha_dt', 'coin_clean'}
        if cols_needed.issubset(frame.columns):
            return frame
        f = frame.copy()
        if 'exchange_root' not in f.columns:
            f['exchange_root'] = f['exchange'].apply(get_canonical_exchange_root)
        if 'tipo_lower' not in f.columns:
            f['tipo_lower'] = f['tipo_operacion'].astype(str).str.lower()
        if 'fecha_dt' not in f.columns:
            f['fecha_dt'] = pd.to_datetime(f['fecha'], errors='coerce')
        if 'coin_clean' not in f.columns:
            f['coin_clean'] = f['moneda'].apply(canonicalize_ticker)
        return f

    df = _ensure_cols(all_tx_df)
    if withdrawals_df is None:
        w_mask = df['tipo_lower'].str.contains('retiro|envio|withdraw', na=False) & (df['monto_venta_cripto'].fillna(0) > 0)
        withdrawals_df = df[w_mask].copy()
    else:
        withdrawals_df = _ensure_cols(withdrawals_df)

    if withdrawals_df.empty:
        return []

    if deposits_df is None:
        d_mask = (
            df['tipo_lower'].str.contains('deposito|ingreso|deposit', na=False) &
            ~df['tipo_lower'].str.contains('compra|buy', na=False) &
            (df['monto_compra_cripto'].fillna(0) > 0)
        )
        deposits_df = df[d_mask].copy()
    else:
        deposits_df = _ensure_cols(deposits_df)

    today = datetime.now()
    valid_dates = df.loc[df['fecha_dt'] <= (today + timedelta(days=1)), 'fecha_dt'].dropna()
    latest_system_date = None
    if target_year is not None:
        year_dates = df.loc[(df['fecha_dt'].dt.year == int(target_year)) & (df['fecha_dt'] <= (today + timedelta(days=1))), 'fecha_dt'].dropna()
        if not year_dates.empty:
            latest_system_date = year_dates.max()
        else:
            try:
                from db.connection import get_connection
                conn = get_connection()
                c = conn.cursor()
                c.execute("SELECT MAX(fecha) FROM transactions WHERE fecha LIKE ?", (f"{target_year}%",))
                row_max = c.fetchone()
                if not row_max or not row_max[0]:
                    c.execute("SELECT MAX(fecha) FROM transactions WHERE fecha <= ?", (str(today.date()),))
                    row_max = c.fetchone()
                conn.close()
                if row_max and row_max[0]:
                    latest_system_date = pd.to_datetime(row_max[0], errors='coerce')
            except Exception:
                pass
    if latest_system_date is None or pd.isna(latest_system_date) or latest_system_date > today:
        latest_system_date = valid_dates.max() if not valid_dates.empty else today
        if latest_system_date > today:
            latest_system_date = today
    cutoff_date = latest_system_date - timedelta(days=30)

    if freshness is None:
        freshness = {}
        for ex_root, grp in df.groupby('exchange_root'):
            vd = grp.loc[grp['fecha_dt'] <= (today + timedelta(days=1)), 'fecha_dt'].dropna()
            if vd.empty:
                vd = grp['fecha_dt'].dropna()
            if not vd.empty:
                freshness[ex_root] = {"exchange": ex_root, "last_tx_date": str(vd.max().date())}

    import collections
    dep_list = []
    deps_by_coin = collections.defaultdict(list)
    txid_to_deps = collections.defaultdict(list)
    if not deposits_df.empty:
        for idx, row in enumerate(deposits_df.to_dict('records')):
            c_text = str(row.get('comentarios', '') or '').lower()
            d_hash = row.get('tx_hash') if pd.notna(row.get('tx_hash')) and str(row.get('tx_hash')).strip() else f"idx_{idx}"
            txid = _extract_transfer_txid(c_text)
            entry = {
                'tx_hash': d_hash,
                'exchange': str(row.get('exchange', '')),
                'exchange_root': str(row.get('exchange_root', '')),
                'coin_clean': str(row.get('coin_clean', '')),
                'monto_compra_cripto': float(row.get('monto_compra_cripto') or 0.0),
                'fecha_dt': row.get('fecha_dt'),
                'comentarios_lower': c_text,
                'txid': txid.lower() if txid else None
            }
            dep_list.append(entry)
            deps_by_coin[entry['coin_clean']].append(entry)
            if entry['txid']:
                txid_to_deps[entry['txid']].append(entry)

    alerts = []
    used_dep_hashes = set()
    from services.source_freshness_service import resolve_exchange_api_info
    exempted_sources = {
        ex_r for ex_r in freshness.keys()
        if is_source_exempted(ex_r) or (
            resolve_exchange_api_info(ex_r).get("is_api") and
            resolve_exchange_api_info(ex_r).get("has_credentials") and
            resolve_exchange_api_info(ex_r).get("status") == "online"
        )
    }

    for w_row in withdrawals_df.to_dict('records'):
        if _is_cold_storage_transfer(w_row):
            continue
        w_date = w_row.get('fecha_dt')
        if pd.isna(w_date):
            continue
        if target_year and int(w_date.year) != int(target_year):
            continue

        w_ex_root = w_row['exchange_root']
        w_coin = str(w_row['coin_clean']).upper()
        w_amount = float(w_row.get('monto_venta_cripto') or 0.0)
        if w_amount <= 0 or w_coin in ('ARS', 'USD', 'EUR', ''):
            continue

        w_txid = _extract_transfer_txid(w_row.get('comentarios', ''))
        matched = False
        if dep_list:
            if w_txid:
                w_txid_l = w_txid.lower()
                cand_txid = txid_to_deps.get(w_txid_l, [])
                if not cand_txid:
                    cand_txid = [d for d in dep_list if w_txid_l in d['comentarios_lower']]
                for d_row in cand_txid:
                    dep_hash = d_row['tx_hash']
                    if dep_hash not in used_dep_hashes:
                        used_dep_hashes.add(dep_hash)
                        matched = True
                        break

            if not matched:
                cand_coin = deps_by_coin.get(w_coin, [])
                w_start = w_date - timedelta(hours=24)
                w_end = w_date + timedelta(hours=72)
                is_stable = w_coin in ('USDT', 'USDC', 'DAI', 'BUSD', 'FDUSD', 'U')
                for d_row in cand_coin:
                    if d_row['exchange'] == w_row['exchange'] or d_row['exchange_root'] == w_ex_root:
                        continue
                    d_dt = d_row['fecha_dt']
                    if not (w_start <= d_dt <= w_end):
                        continue
                    dep_hash = d_row['tx_hash']
                    if dep_hash in used_dep_hashes:
                        continue
                    d_amount = d_row['monto_compra_cripto']
                    diff = abs(w_amount - d_amount)
                    if (diff / max(w_amount, 0.01) <= 0.05) or (is_stable and diff <= 5.0) or (diff <= 1e-6):
                        used_dep_hashes.add(dep_hash)
                        matched = True
                        break

        if not matched:
            w_date_str = str(w_date.date())
            candidate_destinations = [
                _format_exchange_display(ex_r)
                for ex_r, f_info in freshness.items()
                if ex_r != w_ex_root and ex_r not in ('LOCALBITCOINS', 'PAXFUL') and ex_r not in exempted_sources and str(f_info.get('last_tx_date', '')) <= w_date_str
            ]
            w_ex_str = str(w_row['exchange'])
            dest_hint = (
                f"Posible extracto pendiente en: {', '.join(candidate_destinations)} (o retiro hacia wallet externa / tercero)."
                if candidate_destinations
                else "Posible transferencia hacia wallet personal / autocustodia o pago a tercero."
            )
            alerts.append({
                "type": "orphan_withdrawal",
                "exchange": w_ex_str,
                "coin": w_coin,
                "amount": round(w_amount, 4),
                "date": str(w_row['fecha'])[:19],
                "candidate_destinations": candidate_destinations,
                "severity": "ALTA",
                "message": (
                    f"Transferencia saliente sin ingreso registrado: Retiro de {w_amount:,.4f} {w_coin} "
                    f"desde {w_ex_str} el {str(w_row['fecha'])[:16]} no figura ingresado en ningún otro exchange. "
                    f"{dest_hint}"
                )
            })

    return alerts


detect_orphan_transfers = detect_orphan_withdrawals
