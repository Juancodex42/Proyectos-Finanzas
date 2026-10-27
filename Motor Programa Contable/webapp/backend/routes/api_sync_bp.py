from datetime import datetime
from flask import Blueprint, request, jsonify
import db_manager
import api_manager
from async_helper import run_async_safe
from status_cache import get_status_cache

api_sync_bp = Blueprint('api_sync_bp', __name__)


@api_sync_bp.route('/api/status', methods=['GET'])
def get_api_status():
    now = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    force = (request.args.get('force', '') or request.args.get('refresh', '')).lower() in ('1', 'true')

    cached, is_refreshing = get_status_cache(force=force)

    db_exchanges = db_manager.get_all_exchanges()
    res = []
    for ex in db_exchanges:
        ex_id = ex['id']
        ex_name = ex['name']
        ex_type = ex['type']
        if ex_id in cached:
            status = cached[ex_id]["status"]
            last_update = cached[ex_id].get("lastUpdate", "-")
            msg = cached[ex_id].get("msg", "")
        else:
            status = ex.get("status", "unconfigured")
            last_update = ex.get("lastUpdate", "-")
            msg = "Sin verificar" if ex_type == 'NATIVE_API' else "CSV / Manual"

        res.append({
            "id": ex_id,
            "name": ex_name,
            "type": ex_type,
            "status": status,
            "lastUpdate": last_update,
            "msg": msg
        })

    statuses_map = {}
    for item in res:
        statuses_map[item["id"]] = item

    response_payload = {
        "status": "success",
        "data": res,
        "statuses": statuses_map,
        "is_refreshing": is_refreshing,
        "checked_at": now
    }
    # Expose root-level exchange IDs for direct dictionary lookups
    for ex_id, item_obj in statuses_map.items():
        if ex_id not in response_payload:
            response_payload[ex_id] = item_obj

    return jsonify(response_payload)


@api_sync_bp.route('/api/sync', methods=['POST'])
@api_sync_bp.route('/api/sync/all', methods=['POST'])
def sync_all_apis():
    data = request.get_json(silent=True) or {}
    start_date = data.get('start_date') or request.args.get('start_date')
    since_ms = None
    if start_date:
        if isinstance(start_date, (int, float)):
            since_ms = int(start_date)
        else:
            s_str = str(start_date).strip()
            if s_str.isdigit():
                since_ms = int(s_str)
            else:
                try:
                    dt_parsed = datetime.strptime(s_str[:10], "%Y-%m-%d")
                    since_ms = int(dt_parsed.timestamp() * 1000)
                except Exception:
                    since_ms = None

    if hasattr(api_manager, 'sync_all_configured_exchanges'):
        result = api_manager.sync_all_configured_exchanges(since_ms=since_ms) or {}
    else:
        result = run_async_safe(api_manager.fetch_all_v2()) or {}
    models = result.get("data", [])
    errors = result.get("errors", [])
        
    if result.get("success") is False or (not result.get("success") and not models) or (not models and errors):
        return jsonify({"error": "All APIs failed", "details": errors}), 500
        
    dict_list = [m.to_dict() if hasattr(m, 'to_dict') else m for m in models]
    
    inserted, skipped = 0, 0
    if dict_list:
        try:
            inserted, skipped = db_manager.insert_transactions(dict_list, trigger_fifo_recalc=False, source="EXCHANGE_API")
        except TypeError:
            inserted, skipped = db_manager.insert_transactions(dict_list)
        if inserted > 0:
            db_manager.deduplicate_existing_database()
            from services.fifo_service import recalculate_fifo_costs_db
            recalc_fn = getattr(db_manager, 'recalculate_fifo_costs_db', recalculate_fifo_costs_db)
            recalc_fn()
    from services.cache_service import analytics_cache, invalidate_analytics_cache
    invalidate_analytics_cache()
    if hasattr(analytics_cache, 'clear'):
        analytics_cache.clear()
        
    details_map = {}
    for m in models:
        ex_name = getattr(m, 'exchange', None) or (m.get('Exchange') if isinstance(m, dict) else 'Otros')
        details_map[ex_name] = details_map.get(ex_name, 0) + 1
        
    db_exchanges = db_manager.get_all_exchanges()
    exchange_display_names = {
        "Binance Spot": "Binance Spot",
        "Binance P2P": "Binance P2P",
        "Bitso Alpha": "Bitso Alpha",
        "Ripio Trade": "Ripio Trade",
        "Ripio Classic": "Ripio Classic",
        "OKX": "OKX",
        "Bybit": "Bybit",
        "Bitget": "Bitget"
    }
    for ex in db_exchanges:
        ex_name = ex.get('name')
        if ex_name and ex_name not in exchange_display_names:
            exchange_display_names[ex_name] = ex_name
    
    results = []
    errors = result.get("errors", [])
    
    for internal_name, display_name in exchange_display_names.items():
        count = details_map.get(internal_name, 0)
        ex_err = ""
        for err in errors:
            if err and display_name.lower() in err.lower():
                ex_err = err
                break
        
        message = "Success" if count > 0 or not ex_err else api_manager._clean_api_error(ex_err)
        results.append({
            "exchange": display_name,
            "count": count,
            "message": message
        })
        
    return jsonify({
        "status": "success",
        "details": results,
        "total_inserted": inserted,
        "total_skipped": skipped,
        "anomalies": result.get("anomalies", [])
    })

trigger_api_sync = sync_all_apis


def _normalize_single_sync_res(res):
    if isinstance(res, dict):
        return res
    if isinstance(res, tuple) and len(res) == 2:
        txs, status = res
        if isinstance(status, dict):
            ok = status.get("status") in ("online", "success", "ok", True) or bool(status.get("success"))
            err = None if ok else (status.get("error") or status.get("msg") or str(status))
        elif isinstance(status, bool):
            ok = status
            err = None if ok else "Sync failed"
        else:
            s_str = str(status or "").strip()
            ok = s_str.lower() in ("online", "success", "ok", "") or bool(txs)
            err = None if ok else s_str
        return {"success": ok, "data": list(txs or []), "error": err, "anomalies": []}
    return {"success": False, "error": str(res), "data": []}


@api_sync_bp.route('/api/sync/<exchange>', methods=['POST'])
@api_sync_bp.route('/api/api_sync/<exchange>', methods=['POST'])
def sync_single_exchange(exchange):
    ex_lower = exchange.lower().strip()
    ex_id = ex_lower
    run_async = run_async_safe
    
    async def _fetch_target():
        import asyncio
        if ex_lower in ('binance', 'binance_spot', 'binance_p2p'):
            r1 = await api_manager.fetch_binance_v2()
            r2 = await api_manager.fetch_binance_p2p_v2()
            r3 = await api_manager.fetch_binance_transfers_v2()
            return [r1, r2, r3]
        elif ex_lower in ('bitget', 'bitget_spot', 'bitget_p2p'):
            r1 = await api_manager.fetch_bitget_v2()
            r2 = await api_manager.fetch_bitget_p2p_v2()
            r3 = await api_manager.fetch_bitget_transfers_v2()
            return [r1, r2, r3]
        elif ex_lower == 'bitso':
            return [await api_manager.fetch_bitso_v2()]
        elif ex_lower == 'bybit':
            r1 = await api_manager.fetch_bybit_v2()
            r2 = await api_manager.fetch_bybit_transfers_v2()
            return [r1, r2]
        elif ex_lower in ('ripio', 'ripio_trade'):
            return [await api_manager.fetch_ripio_trade_v2()]
        elif ex_lower == 'okx':
            r1 = await api_manager.fetch_okx_v2()
            r2 = await api_manager.fetch_okx_transfers_v2()
            return [r1, r2]
        elif ex_id in ('lemon', 'lemon_cash'):
            if hasattr(api_manager, 'fetch_lemon_v2'):
                fn = api_manager.fetch_lemon_v2
                res = fn()
                if hasattr(res, '__await__'):
                    res = await res
                return [_normalize_single_sync_res(res)]
            return [{
                "success": True,
                "skipped": True,
                "data": [],
                "message": "Lemon Cash no cuenta con API pública. Operaciones disponibles mediante importación CSV."
            }]
        elif ex_id == 'fiwind':
            if hasattr(api_manager, 'fetch_fiwind_v2'):
                fn = api_manager.fetch_fiwind_v2
                res = fn()
                if hasattr(res, '__await__'):
                    res = await res
                return [_normalize_single_sync_res(res)]
            return [{
                "success": True,
                "skipped": True,
                "data": [],
                "message": "Fiwind no cuenta con API pública configurada. Operaciones disponibles mediante importación CSV."
            }]
        elif ex_lower == 'all':
            res = await api_manager.fetch_all_v2()
            return [res]
        else:
            return [{"success": False, "error": f"Exchange '{exchange}' no reconocido", "data": []}]

    try:
        raw_results = run_async(_fetch_target())
        all_models = []
        errors = []
        anomalies = []
        for r in raw_results:
            if isinstance(r, dict):
                if r.get('success'):
                    all_models.extend(r.get('data', []))
                    anomalies.extend(r.get('anomalies', []))
                else:
                    errors.append(r.get('error'))
            else:
                errors.append(str(r))
        if ex_lower == 'all':
            for r in raw_results:
                if isinstance(r, dict) and (r.get("success") is False or (not r.get("data") and r.get("errors"))):
                    err_details = r.get("errors") or ([r.get("error")] if r.get("error") else errors)
                    return jsonify({"error": "All APIs failed", "details": err_details}), 500
            if not all_models and errors:
                return jsonify({"error": "All APIs failed", "details": errors}), 500

        dict_list = [m.to_dict() if hasattr(m, 'to_dict') else (m.model_dump() if hasattr(m, 'model_dump') else m) for m in all_models]
        inserted, skipped = 0, 0
        if dict_list:
            try:
                inserted, skipped = db_manager.insert_transactions(dict_list, trigger_fifo_recalc=False, source="EXCHANGE_API")
            except TypeError:
                inserted, skipped = db_manager.insert_transactions(dict_list)
            if inserted > 0:
                db_manager.deduplicate_existing_database()
                from services.fifo_service import recalculate_fifo_costs_db
                recalc_fn = getattr(db_manager, 'recalculate_fifo_costs_db', recalculate_fifo_costs_db)
                recalc_fn()
        from services.cache_service import analytics_cache, invalidate_analytics_cache
        invalidate_analytics_cache()
        if hasattr(analytics_cache, 'clear'):
            analytics_cache.clear()

        resp_payload = {
            "status": "success" if (dict_list or not errors) else "error",
            "exchange": exchange,
            "total_inserted": inserted,
            "total_skipped": skipped,
            "errors": errors,
            "anomalies": anomalies
        }
        for r in raw_results:
            if isinstance(r, dict):
                if r.get("skipped"):
                    resp_payload["skipped"] = True
                if r.get("message"):
                    resp_payload["message"] = r.get("message")

        return jsonify(resp_payload)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
