from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
import pandas as pd
import db_manager
import processor_lib
from .reports_helpers import (
    build_gaps_response_payload,
    normalize_batch_dates,
    build_preview_mapping_rows,
    build_operational_export_excel,
    build_separated_exchanges_zip,
    filter_dashboard_anomalies,
)

reports_bp = Blueprint('reports_bp', __name__)


@reports_bp.route('/api/reports/gaps', methods=['GET'])
@reports_bp.route('/api/reconciliation/gaps', methods=['GET'])
@reports_bp.route('/api/reconciliation/modes', methods=['GET'])
def get_all_gaps():
    year = request.args.get('year', type=int)
    mode = request.args.get('mode', 'global').lower()
    cache_key = f"gaps_report_{year}_{mode}"

    from services.cache_service import analytics_cache
    cached = analytics_cache.get(cache_key)
    if cached is not None:
        return jsonify(cached)

    if mode == 'exchange':
        exchange_raw = db_manager.check_history_gaps(mode='exchange', year=year)
        exchange_enriched = db_manager.enrich_gaps_with_clues(exchange_raw, year=year)
        global_enriched = {}
    elif mode == 'global':
        global_raw = db_manager.check_history_gaps(mode='global', year=year)
        global_enriched = db_manager.enrich_gaps_with_clues(global_raw, year=year)
        exchange_enriched = {}
    else:
        exchange_raw = db_manager.check_history_gaps(mode='exchange', year=year)
        exchange_enriched = db_manager.enrich_gaps_with_clues(exchange_raw, year=year)
        global_raw = db_manager.check_history_gaps(mode='global', year=year)
        global_enriched = db_manager.enrich_gaps_with_clues(global_raw, year=year)

    res = build_gaps_response_payload(mode, exchange_enriched, global_enriched)
    analytics_cache.set(cache_key, res)
    return jsonify(res)


@reports_bp.route('/api/reports/fiscal-summary', methods=['GET'])
@reports_bp.route('/api/taxes/report', methods=['GET'])
def get_fiscal_summary():
    year = request.args.get('year', datetime.now().year, type=int)
    try:
        report = db_manager.get_tax_report(year)
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reports_bp.route('/api/reports/tax-bracket', methods=['GET'])
@reports_bp.route('/api/taxes/settings', methods=['GET'])
def get_tax_bracket():
    year = request.args.get('year', datetime.now().year, type=int)
    settings = db_manager.get_tax_settings(year)
    return jsonify(settings)


@reports_bp.route('/api/reports/tax-bracket', methods=['POST'])
@reports_bp.route('/api/taxes/settings', methods=['POST'])
def save_tax_bracket():
    data = request.json or {}
    try:
        db_manager.save_tax_settings(data)
        from services.cache_service import invalidate_analytics_cache
        invalidate_analytics_cache()
        try:
            import api_manager
            api_manager.clear_exchange_rate_cache()
        except Exception:
            pass
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reports_bp.route('/api/reports/batch-generate', methods=['POST'])
def batch_generate():
    data = request.json or {}
    exchanges = data.get('exchanges', [])
    mode = data.get('mode', 'global')

    try:
        date_start, date_end = normalize_batch_dates(data.get('dateStart'), data.get('dateEnd'))
    except Exception:
        return jsonify({"error": "Formato de fecha inválido"}), 400

    real_transactions = db_manager.get_transactions(exchanges, date_start, date_end)
    raw_gaps = db_manager.check_history_gaps(exchanges, date_start, date_end, mode=mode)
    batch_year = (
        int(str(date_start)[:4])
        if date_start and len(str(date_start)) >= 4 and str(date_start)[:4].isdigit()
        else None
    )
    enriched = db_manager.enrich_gaps_with_clues(raw_gaps, year=batch_year)

    return jsonify({
        "status": "success",
        "count": len(real_transactions),
        "transactions": real_transactions,
        "gaps": enriched.get("gaps", []),
        "custody_deficits": enriched.get("custody_deficits", []),
        "source_alerts": enriched.get("source_alerts", []),
        "exchange_freshness": enriched.get("exchange_freshness", []),
        "monthly_custody": enriched.get("monthly_custody", {}),
    })


@reports_bp.route('/api/reports/preview-mapping', methods=['POST'])
def preview_mapping():
    data = request.json or {}
    exchanges_names = data.get('exchanges', [])
    date_start = data.get('dateStart')
    date_end = data.get('dateEnd')
    return jsonify(build_preview_mapping_rows(exchanges_names, date_start, date_end))


@reports_bp.route('/api/reports/batch-download', methods=['POST'])
def batch_download():
    data = request.json or {}
    exchanges = data.get('exchanges', [])
    date_start = data.get('dateStart')
    date_end = data.get('dateEnd')
    export_format = data.get('format', 'consolidated')

    real_transactions = db_manager.get_transactions(exchanges, date_start, date_end)
    if not real_transactions:
        return jsonify({"error": "No valid data found for selected criteria"}), 404

    year = date_start[:4] if (date_start and len(date_start) >= 4) else "Batch"

    if export_format == 'operational':
        opts = data.get('options') or {}
        excel_io = build_operational_export_excel(real_transactions, date_start, date_end, opts)
        if not excel_io:
            return jsonify({"error": "No valid data found for selected criteria"}), 404
        return send_file(
            excel_io,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Reporte_Operativo_Stock_Caja_{year}.xlsx',
        )
    elif export_format == 'separated':
        zip_buffer = build_separated_exchanges_zip(real_transactions, year)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'Reporte_Consolidado_{year}.zip',
        )
    else:
        excel_io = processor_lib.generate_master_excel(real_transactions)
        if not excel_io:
            return jsonify({"error": "No valid data found for selected criteria"}), 404
        return send_file(
            excel_io,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Reporte_Consolidado_{year}.xlsx',
        )


@reports_bp.route('/api/stats/kpi', methods=['GET'])
def stats_kpi():
    start = request.args.get('start')
    end = request.args.get('end')
    exchanges = request.args.get('exchanges')
    status = request.args.get('status')
    return jsonify(db_manager.get_kpis(start, end, exchanges, status_filter=status))


@reports_bp.route('/api/stats/daily_volume', methods=['GET'])
def stats_daily():
    start = request.args.get('start')
    end = request.args.get('end')
    exchanges = request.args.get('exchanges')
    status = request.args.get('status')
    return jsonify(db_manager.get_daily_volume(start, end, exchanges, status_filter=status))


@reports_bp.route('/api/stats/exchange_distribution', methods=['GET'])
def stats_exchange():
    start = request.args.get('start')
    end = request.args.get('end')
    exchanges = request.args.get('exchanges')
    status = request.args.get('status')
    return jsonify(db_manager.get_exchange_distribution(start, end, exchanges, status_filter=status))


@reports_bp.route('/api/stats/equity', methods=['GET'])
@reports_bp.route('/api/reports/equity', methods=['GET'])
def stats_equity():
    start = request.args.get('date_start') or request.args.get('dateStart') or request.args.get('start')
    end = request.args.get('date_end') or request.args.get('dateEnd') or request.args.get('end')
    exchanges = request.args.get('exchanges')
    interval = request.args.get('interval', 'daily')
    status = request.args.get('status')

    if start:
        try:
            start = pd.to_datetime(start).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return jsonify({"error": "Formato de fecha inválido"}), 400
    if end:
        try:
            end = pd.to_datetime(end).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return jsonify({"error": "Formato de fecha inválido"}), 400

    return jsonify(db_manager.get_equity_curve(start, end, exchanges, interval, status_filter=status))


get_equity_curve = stats_equity


@reports_bp.route('/api/stats/spread', methods=['GET'])
def stats_spread():
    start = request.args.get('start')
    end = request.args.get('end')
    exchanges = request.args.get('exchanges')
    status = request.args.get('status')
    return jsonify(db_manager.get_modal_spread(start, end, exchanges, status_filter=status))


@reports_bp.route('/api/stats/recalculate', methods=['POST'])
def stats_recalculate():
    try:
        from services.fifo_service import recalculate_fifo_costs_db
        res = recalculate_fifo_costs_db()
        try:
            from services.cache_service import invalidate_analytics_cache
            invalidate_analytics_cache()
        except Exception:
            pass
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@reports_bp.route('/api/stats/available_exchanges', methods=['GET'])
def stats_available_exchanges():
    configured = [ex['name'] for ex in db_manager.get_all_exchanges()]
    history = db_manager.get_processing_history()
    from_history = [h['exchange'] for h in history if h.get('exchange')]
    all_exchanges = list(dict.fromkeys(configured + from_history))
    return jsonify(all_exchanges)


@reports_bp.route('/api/dashboard', methods=['GET'])
def get_dashboard_data():
    start = request.args.get('start_date') or request.args.get('start')
    end = request.args.get('end_date') or request.args.get('end')
    exchanges_param = request.args.get('exchanges')
    status_filter = request.args.get('status')
    interval = request.args.get('interval', 'daily')

    exchanges_list = [e.strip() for e in exchanges_param.split(',')] if exchanges_param else None

    cache_key = f"dashboard_{start}_{end}_{exchanges_param}_{status_filter}_{interval}"
    from services.cache_service import analytics_cache
    cached_payload = analytics_cache.get(cache_key)
    if cached_payload is not None:
        return jsonify(cached_payload)

    configured = [ex['name'] for ex in db_manager.get_all_exchanges()]
    history = db_manager.get_processing_history()
    from_history = [h['exchange'] for h in history if h.get('exchange')]
    all_exchanges = list(dict.fromkeys(configured + from_history))

    kpis = db_manager.get_kpis(start, end, exchanges_list, status_filter=status_filter)
    daily_vol = db_manager.get_daily_volume(start, end, exchanges_list, status_filter=status_filter)
    exchange_dist = db_manager.get_exchange_distribution(start, end, exchanges_list, status_filter=status_filter)
    equity_curve = db_manager.get_equity_curve(start, end, exchanges_list, interval, status_filter=status_filter)
    modal_spread = db_manager.get_modal_spread(start, end, exchanges_list, status_filter=status_filter)

    audit_cache_key = "recon_full_audit"
    audit_res = analytics_cache.get(audit_cache_key)
    if audit_res is None:
        from reconciliation import ReconciliationEngine
        recon_engine = ReconciliationEngine()
        audit_res = recon_engine.run_full_audit()
        analytics_cache.set(audit_cache_key, audit_res)
    anomalies = filter_dashboard_anomalies(audit_res.get('anomalies', []), start, end, exchanges_list)

    cross_audit_res = None
    try:
        from services.cert_excel_cross_audit_service import audit_certification_vs_excel
        target_y = int(str(start)[:4]) if start and len(str(start)) >= 4 else None
        cross_audit_res = audit_certification_vs_excel(target_year=target_y)
    except Exception:
        cross_audit_res = {"discrepancies": [], "summary": {}}

    res = {
        "status": "success",
        "available_exchanges": all_exchanges,
        "kpis": kpis,
        "anomalies": anomalies,
        "cert_discrepancies": (cross_audit_res or {}).get("discrepancies", []),
        "cert_discrepancies_summary": (cross_audit_res or {}).get("summary", {}),
        "equity_curve": equity_curve,
        "daily_volume": daily_vol,
        "exchange_distribution": exchange_dist,
        "modal_spread": modal_spread,
    }
    analytics_cache.set(cache_key, res)
    return jsonify(res)


@reports_bp.route('/api/cache/clear', methods=['POST'])
def clear_cache_route():
    try:
        from services.cache_service import invalidate_analytics_cache
        invalidate_analytics_cache()
        return jsonify({"success": True, "message": "Caché analítico limpiado correctamente."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
