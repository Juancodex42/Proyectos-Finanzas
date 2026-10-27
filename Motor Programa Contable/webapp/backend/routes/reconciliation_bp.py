from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
try:
    from services.cache_service import invalidate_Dashboard_Cache
except ImportError:
    from services.cache_service import invalidate_analytics_cache as invalidate_Dashboard_Cache

reconciliation_bp = Blueprint('reconciliation_bp', __name__)


@reconciliation_bp.route('/api/reconciliation/audit', methods=['GET'])
@reconciliation_bp.route('/api/audit/reconciliation', methods=['GET'])
def audit_reconciliation():
    try:
        from reconciliation import ReconciliationEngine
        engine = ReconciliationEngine()
        res = engine.run_full_audit()
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reconciliation_bp.route('/api/reconciliation/auto-fix', methods=['POST'])
def auto_fix_anomalies():
    try:
        from reconciliation import ReconciliationEngine
        engine = ReconciliationEngine()
        res = engine.run_auto_correction()
        invalidate_Dashboard_Cache()
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reconciliation_bp.route('/api/classify_origin', methods=['POST'])
@reconciliation_bp.route('/api/reconciliation/classify_origin', methods=['POST'])
@reconciliation_bp.route('/api/audit/classify_anomaly', methods=['POST'])
def audit_classify_anomaly():
    data = request.json or {}
    date_str = data.get('date')
    exchange_str = data.get('exchange')
    crypto_str = data.get('crypto')
    try:
        missing_amount = float(data.get('missing_amount', data.get('missing', 0.0)) or 0.0)
    except (ValueError, TypeError):
        missing_amount = 0.0
    origin_type = data.get('origin_type')
    
    if not all([date_str, exchange_str, crypto_str, origin_type]) or missing_amount <= 0:
        return jsonify({"error": "Faltan datos obligatorios o monto inválido para clasificar la anomalía."}), 400
        
    try:
        from reconciliation import ReconciliationEngine
        engine = ReconciliationEngine()
        res = engine.classify_single_anomaly(date_str, exchange_str, crypto_str, missing_amount, origin_type)
        invalidate_Dashboard_Cache()
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reconciliation_bp.route('/api/reconciliation/resolve_gap', methods=['POST'])
def resolve_gap_route():
    data = request.json or {}
    exchange = data.get('exchange')
    crypto = data.get('crypto')
    date_str = data.get('date')
    try:
        raw_amount = data.get('amount', 0)
        raw_price = data.get('price', 0)
        amount = float(0.0 if raw_amount is None or raw_amount == '' else raw_amount)
        price = float(0.0 if raw_price is None or raw_price == '' else raw_price)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Datos inválidos: monto y precio deben ser valores numéricos."}), 400
    currency = str(data.get('currency', 'USD')).strip().upper()
    gap_type = data.get('type', 'buy')
    origin = data.get('origin', 'unknown')
    notes = data.get('notes', 'Ajuste manual de hueco FIFO')
    
    if not crypto or not date_str or amount <= 0:
        return jsonify({"success": False, "error": "Datos inválidos: cripto, fecha y monto son obligatorios."}), 400
        
    try:
        import db_manager
        import pandas as pd
        from parsers.base_parser import get_usd_ars_rate
        
        raw_date = str(date_str).strip()
        if not raw_date:
            return jsonify({"success": False, "error": f"Fecha inválida: {raw_date}"}), 400
        try:
            gap_dt = pd.to_datetime(raw_date)
            if pd.isna(gap_dt):
                raise ValueError("NaT")
            if hasattr(gap_dt, 'to_pydatetime'):
                gap_dt = gap_dt.to_pydatetime()
            adj_dt = gap_dt
        except Exception:
            return jsonify({"success": False, "error": f"Fecha inválida: {raw_date}"}), 400
            
        # Handle USD vs ARS pricing accurately
        if price > 0:
            if currency == 'USD':
                fx_rate = get_usd_ars_rate(adj_dt)
                price_ars = round(price * fx_rate, 2)
            else:
                price_ars = round(price, 2)
            m_ars = round(amount * price_ars, 2)
        else:
            price_ars = 0.0
            m_ars = 0.0
            
        # Target exchange: respect the exchange where the operation/deficit occurred, recording origin in comments
        if exchange and exchange != 'Cartera Global':
            target_exchange = exchange
        elif origin and str(origin).strip().lower() not in ('unknown', 'none', '', 'cold_wallet', 'p2p'):
            target_exchange = str(origin).strip()
        else:
            target_exchange = 'Ajuste Manual'
        
        import hashlib
        res_salt = hashlib.md5(f"RESOLVE_GAP_{adj_dt.strftime('%Y%m%d%H%M%S')}_{crypto}_{target_exchange}_{amount:.8f}".encode('utf-8')).hexdigest()[:8]
        tx_dict = {
            'Fecha': adj_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'Exchange': target_exchange,
            'Tipo de Operación': 'Compra' if (gap_type in ('buy', 'initial_capital') or price_ars > 0) else 'Ingreso Cripto',
            'Moneda': crypto,
            'Monto Compra (Cripto)': amount,
            'Monto Venta (Cripto)': 0.0,
            'Cotización Compra': price_ars,
            'Cotización Venta': 0.0,
            'Monto ARS': m_ars,
            'Comentarios': f"[Ajuste FIFO ({origin}) Ref:{res_salt}] {notes} (Costo: {price} {currency})"
        }
        
        # Check if target date falls in a certified accounting period
        formatted_date = adj_dt.strftime('%Y-%m-%d %H:%M:%S')
        conn = db_manager.get_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT title, start_date, end_date FROM certifications")
            for cert_title, c_start, c_end in c.fetchall():
                if c_start and c_end:
                    from services.certifications_service import _normalize_cert_boundary
                    c_s = _normalize_cert_boundary(c_start, is_end=False)
                    c_e = _normalize_cert_boundary(c_end, is_end=True)
                    if c_s <= formatted_date <= c_e:
                        return jsonify({
                            "success": False,
                            "is_certified_conflict": True,
                            "certified_period": cert_title,
                            "error": (
                                f"La fecha del ajuste ({formatted_date[:10]}) cae dentro del período certificado "
                                f"'{cert_title}' ({c_s[:10]} al {c_e[:10]}). "
                                f"Por normativa contable, los períodos certificados están sellados e inmutables. "
                                f"Para subsanar este inventario, registrá el ingreso a partir del primer día del período posterior no certificado, "
                                f"o revocá la certificación si fue emitida con datos incompletos."
                            )
                        }), 409
        finally:
            conn.close()

        inserted, skipped = db_manager.insert_transactions([tx_dict], trigger_fifo_recalc=True)
        invalidate_Dashboard_Cache()
        if inserted == 0:
            return jsonify({
                "success": True,
                "inserted": 0,
                "skipped": skipped,
                "message": "El ajuste ya existía en la base de datos o fue subsanado."
            }), 200
            
        return jsonify({
            "success": True, 
            "inserted": inserted, 
            "message": f"Ajuste de {amount} {crypto} registrado exitosamente a ${price_ars:,.2f} ARS/u."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@reconciliation_bp.route('/api/exchange/<path:exchange>', methods=['DELETE'])
@reconciliation_bp.route('/api/reconciliation/exchange/<path:exchange>', methods=['DELETE'])
def delete_exchange_data(exchange):
    try:
        import db_manager
        body = request.get_json(silent=True) or {}
        year = request.args.get('year', type=int) or body.get('year')
        if year is not None:
            try:
                year = int(year)
            except (ValueError, TypeError):
                year = None
        try:
            deleted = db_manager.delete_transactions_by_exchange(exchange, year=year)
        except TypeError:
            deleted = db_manager.delete_transactions_by_exchange(exchange)
        invalidate_Dashboard_Cache()
        return jsonify({"success": True, "deleted_count": deleted, "exchange": exchange, "year": year})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@reconciliation_bp.route('/api/bank/upload', methods=['POST'])
def upload_bank_statement():
    """Uploads, reconciles, and persists an Argentine bank or fintech statement against P2P orders."""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No se recibió ningún archivo bancario."}), 400
        
    file = request.files['file']
    filename = file.filename or 'extracto.csv'
    
    try:
        from parsers.bank_parsers import parse_bank_statement
        from services.bank_reconciliation_service import reconcile_bank_movements
        from services.bank_persistence_service import save_reconciled_bank_movements
        
        bank_name, bank_txs = parse_bank_statement(file, filename)
        if not bank_txs:
            return jsonify({
                "success": False,
                "error": "No se pudieron extraer movimientos del archivo. Verificá que contenga columnas de Fecha e Importe."
            }), 400
            
        recon_result = reconcile_bank_movements(bank_txs)
        all_reconciled = recon_result['matched'] + recon_result['pending']
        persist_stats = save_reconciled_bank_movements(all_reconciled)
        invalidate_Dashboard_Cache()
        
        matched_dicts = [t.model_dump() if hasattr(t, 'model_dump') else t.dict() for t in recon_result['matched']]
        pending_dicts = [t.model_dump() if hasattr(t, 'model_dump') else t.dict() for t in recon_result['pending']]
        
        return jsonify({
            "success": True,
            "bank_name": bank_name,
            "filename": filename,
            "summary": {**recon_result['summary'], **persist_stats},
            "matched": matched_dicts,
            "pending": pending_dicts
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


VALID_BANK_CATEGORIES = {
    'OPERATIVA_CRIPTO', 'INYECCION', 'RETIRO_PERSONAL', 'GASTO_PERSONAL',
    'PRESTAMO_USDT', 'DEVOLUCION_PRESTAMO_USDT', 'TRANSFERENCIA_INTERNA',
    'COMISION_BANCARIA', 'IGNORAR',
    'GASTO_ARBITRAJE', 'RETIRO', 'PRESTAMO', 'PRESTAMO_RECIBIDO',
    'DEVOLUCION_PRESTAMO', 'PASE_PROPIO', 'RENDIMIENTO', 'P2P_MATCHED', 'PENDIENTE'
}


@reconciliation_bp.route('/api/bank/classify', methods=['POST'])
def classify_bank_movement():
    """Classifies and persists a bank movement."""
    data = request.get_json(silent=True) or {}
    raw_cat = data.get('categoria') or data.get('category')
    category = str(raw_cat or '').upper().strip()
    if not category or category not in VALID_BANK_CATEGORIES:
        return jsonify({"success": False, "error": "Categoría inválida o faltante"}), 400

    tx_id = data.get('tx_hash') or data.get('id') or data.get('movement_id') or data.get('raw_reference')
    nota = data.get('nota') or data.get('note') or ''
    subtipo = data.get('subtipo_cuenta_propia')

    try:
        import db_manager
        from services.bank_persistence_service import update_bank_movement_category as _update_bm_cat
        update_fn = getattr(db_manager, 'update_bank_movement_category', _update_bm_cat)
        updated = update_fn(str(tx_id or ''), category, nota=nota, subtipo_cuenta_propia=subtipo)
        if updated is None:
            return jsonify({"success": False, "error": f"Movimiento bancario {tx_id} no encontrado"}), 404
        invalidate_Dashboard_Cache()
        return jsonify({
            "success": True,
            "message": f"Movimiento clasificado como {category}.",
            "id": tx_id,
            "categoria": category,
            "updated": updated
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


classify_bank_movement_route = classify_bank_movement


@reconciliation_bp.route('/api/bank/movements', methods=['GET'])
def list_bank_movements():
    """Returns persisted bank movements filtered by date range and optional category."""
    date_start = request.args.get('dateStart') or request.args.get('start')
    date_end = request.args.get('dateEnd') or request.args.get('end')
    categoria = request.args.get('categoria')
    try:
        from services.bank_persistence_service import get_persisted_bank_movements
        movements = get_persisted_bank_movements(date_start=date_start, date_end=date_end, categoria=categoria)
        return jsonify({"success": True, "count": len(movements), "movements": movements})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@reconciliation_bp.route('/api/bank/settings', methods=['GET', 'POST'])
def bank_operational_settings():
    """Gets or updates operational accounts vs personal external accounts, thresholds, and initial/final balances."""
    try:
        from services.bank_persistence_service import get_operational_settings, save_operational_settings
        if request.method == 'POST':
            data = request.json or {}
            updated = save_operational_settings(data)
            invalidate_Dashboard_Cache()
            return jsonify({"success": True, "settings": updated})
        return jsonify({"success": True, "settings": get_operational_settings()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@reconciliation_bp.route('/api/reports/operational-defaults', methods=['POST', 'GET'])
def get_operational_report_defaults():
    """Computes auto-calculated initial/final balances, guarantee, closing rate, and bank stats for Operational Excel."""
    data = (request.get_json(silent=True) or {}) if request.method == 'POST' else request.args
    exchanges = data.get('exchanges')
    date_start = data.get('dateStart') or data.get('start')
    date_end = data.get('dateEnd') or data.get('end')
    try:
        from services.bank_persistence_service import compute_operational_defaults
        res = compute_operational_defaults(exchanges=exchanges, date_start=date_start, date_end=date_end)
        return jsonify({"success": True, **res})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@reconciliation_bp.route('/api/reconciliation/cert-cross-audit', methods=['GET'])
def get_cert_cross_audit():
    """Cross-audits certified transactions against uploaded Excel/CSV statements."""
    try:
        cert_id = request.args.get('cert_id', type=int)
        target_year = request.args.get('year', type=int)
        from services.cert_excel_cross_audit_service import audit_certification_vs_excel
        res = audit_certification_vs_excel(cert_id=cert_id, target_year=target_year)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@reconciliation_bp.route('/api/reconciliation/cert-cross-audit/resolve', methods=['POST'])
def resolve_cert_cross_audit():
    """Applies user resolution to a cross-audit discrepancy (e.g. align_with_excel_date)."""
    try:
        data = request.get_json(silent=True) or {}
        tx_id = data.get('tx_id')
        action = data.get('action')
        new_value = data.get('new_value')
        if not tx_id or not action:
            return jsonify({"success": False, "error": "Faltan parámetros tx_id o action."}), 400

        from services.cert_excel_cross_audit_service import resolve_cross_audit_discrepancy
        res = resolve_cross_audit_discrepancy(tx_id=tx_id, action=action, new_value=new_value)
        if res.get('success'):
            invalidate_Dashboard_Cache()
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500




