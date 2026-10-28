"""
Helper functions for report generation, preview mapping, and export formatting in reports_bp.
"""

import io
import re
import zipfile
import pandas as pd
import db_manager
import processor_lib
import config_manager
from utils.status_cache import get_status_cache


def build_gaps_response_payload(mode: str, exchange_enriched: dict, global_enriched: dict) -> dict:
    """Builds the unified reconciliation gaps response dictionary for exchange and global modes."""
    active_enriched = global_enriched if mode == 'global' else exchange_enriched

    def _mode_block(enriched_obj: dict) -> dict:
        return {
            "total_gaps": len(enriched_obj.get("gaps", [])),
            "total_root_gaps": len(enriched_obj.get("root_gaps", [])),
            "root_gaps": enriched_obj.get("root_gaps", []),
            "summary": enriched_obj.get("summary", {}),
            "gaps": enriched_obj.get("gaps", []),
            "custody_deficits": enriched_obj.get("custody_deficits", []),
            "source_alerts": enriched_obj.get("source_alerts", []),
            "declared_sources": enriched_obj.get("declared_sources", []),
            "monthly_custody": enriched_obj.get("monthly_custody", {}),
        }

    return {
        "status": "success",
        "success": True,
        "mode": mode,
        "total_gaps": len(active_enriched.get("gaps", [])),
        "total_root_gaps": len(active_enriched.get("root_gaps", [])),
        "root_gaps": active_enriched.get("root_gaps", []),
        "summary": active_enriched.get("summary", {}),
        "gaps": active_enriched.get("gaps", []),
        "exchange_freshness": active_enriched.get("exchange_freshness", []),
        "custody_deficits": active_enriched.get("custody_deficits", []),
        "source_alerts": active_enriched.get("source_alerts", []),
        "declared_sources": active_enriched.get("declared_sources", []),
        "orphan_withdrawals": active_enriched.get("orphan_withdrawals", []),
        "monthly_custody": active_enriched.get("monthly_custody", {}),
        "modes": {
            "exchange": _mode_block(exchange_enriched),
            "global": _mode_block(global_enriched),
        },
    }


def normalize_batch_dates(date_start, date_end):
    """Normalizes start and end dates for batch report generation. Raises ValueError on invalid dates."""
    norm_start = date_start
    norm_end = date_end
    if norm_start:
        norm_start = pd.to_datetime(norm_start, dayfirst=True).strftime('%Y-%m-%d %H:%M:%S')
    if norm_end:
        dt_e = pd.to_datetime(norm_end, dayfirst=True)
        if dt_e.hour == 0 and dt_e.minute == 0 and dt_e.second == 0:
            norm_end = dt_e.strftime('%Y-%m-%d 23:59:59')
        else:
            norm_end = dt_e.strftime('%Y-%m-%d %H:%M:%S')
    return norm_start, norm_end


def build_preview_mapping_rows(exchanges_names: list, date_start, date_end) -> list:
    """Builds the exchange status, freshness, and schema mapping rows for report preview."""
    cached, _ = get_status_cache()
    all_ex = db_manager.get_all_exchanges()
    res = []
    mappings = config_manager.load_config()

    for ex in all_ex:
        if ex['name'] not in exchanges_names:
            continue

        ex_id = ex['id']
        ex_name = ex['name']
        ex_type = ex['type']
        is_api = (ex_type == 'NATIVE_API')

        db_last_tx = db_manager.get_exchange_last_tx_date(ex_name)

        if ex_id in cached:
            status = cached[ex_id]["status"]
            cached_lu = cached[ex_id].get("lastUpdate")
            last_update = cached_lu if (cached_lu and cached_lu != '-') else (db_last_tx if db_last_tx != '-' else '-')
            msg = cached[ex_id].get("msg", "")
        else:
            status = ex.get("status", "online")
            ex_lu = ex.get("lastUpdate")
            last_update = db_last_tx if db_last_tx != '-' else (ex_lu if ex_lu != '-' else '-')
            msg = "CSV / Manual"

        txs = db_manager.get_transactions([ex_name], date_start, date_end)
        tx_count = len(txs)

        is_stale = False
        if date_end and last_update != '-':
            try:
                date_part = last_update.split(' ')[0]
                parts = date_part.split('/')
                iso_date = f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else date_part
                clean_date_end = str(date_end).split(' ')[0]
                if iso_date < clean_date_end:
                    is_stale = True
            except Exception:
                pass

        mapping_schema = {}
        if ex_type == 'CUSTOM_CSV':
            mapping_schema = ex.get('mapping', {})
        elif ex_id in mappings:
            mapping_schema = mappings[ex_id].get('columns', {})

        is_ready = (status == 'online') if is_api else (tx_count > 0 and not is_stale)

        res.append({
            "id": ex_id,
            "name": ex_name,
            "type": ex_type,
            "status": status,
            "lastUpdate": last_update,
            "msg": msg,
            "transactionCount": tx_count,
            "mapping": mapping_schema,
            "isApi": is_api,
            "isReady": is_ready,
            "isStale": is_stale,
        })

    return res


def build_operational_export_excel(real_transactions: list, date_start, date_end, opts: dict):
    """Generates the operational stock & cash Excel buffer merging crypto and bank ledger rows."""
    from services.operational_excel_service import generate_operational_excel
    from services.bank_persistence_service import get_bank_ledger_transactions, save_operational_settings

    if opts:
        save_operational_settings(opts)
    seen_hashes = {t.get('tx_hash') for t in real_transactions if t.get('tx_hash')}
    bank_txs = [
        b for b in get_bank_ledger_transactions(date_start, date_end)
        if b.get('tx_hash') not in seen_hashes
    ]
    return generate_operational_excel(real_transactions + bank_txs, options=opts)


def build_separated_exchanges_zip(real_transactions: list, year: str) -> io.BytesIO:
    """Packages per-exchange master Excel workbooks into a single ZIP archive buffer."""
    by_exchange = {}
    for tx in real_transactions:
        ex = tx.get('Exchange', 'Generic')
        by_exchange.setdefault(ex, []).append(tx)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for ex_name, ex_txs in by_exchange.items():
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', ex_name.replace(' ', '_'))
            excel_io = processor_lib.generate_master_excel(ex_txs)
            if excel_io:
                zip_file.writestr(f"{clean_name}_Reporte_{year}.xlsx", excel_io.getvalue())

    zip_buffer.seek(0)
    return zip_buffer


def filter_dashboard_anomalies(anomalies: list, start, end, exchanges_list) -> list:
    """Filters audit anomalies by date range and canonical exchange roots for the dashboard."""
    if not (start or end or exchanges_list):
        return list(anomalies)
    from models.transaction_models import get_canonical_exchange_root

    ex_roots = {get_canonical_exchange_root(e) for e in exchanges_list if e} if exchanges_list else None
    s_str = str(start)[:10] if start else None
    e_str = str(end)[:10] if end else None
    return [
        item for item in anomalies
        if (not s_str or str(item.get('date') or item.get('fecha') or '')[:10] >= s_str)
        and (not e_str or str(item.get('date') or item.get('fecha') or '')[:10] <= e_str)
        and (
            not ex_roots
            or get_canonical_exchange_root(str(item.get('exchange') or '')) in ex_roots
            or str(item.get('exchange') or '').strip() in exchanges_list
        )
    ]
