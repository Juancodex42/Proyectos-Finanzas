import os
import uuid
import time as time_module
import logging
from datetime import timedelta
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
import db_manager
import pdf_table_extractor
from pdf_cert_helper import extract_info_from_pdf_stream
try:
    from services.cache_service import invalidate_Dashboard_Cache
except ImportError:
    from services.cache_service import invalidate_analytics_cache as invalidate_Dashboard_Cache

certifications_bp = Blueprint('certifications_bp', __name__)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads', 'certifications')


def _validate_and_save_pdf(file_storage) -> tuple:
    """Validates PDF magic header (%PDF-) and saves file with unique prefix to prevent collisions."""
    safe_name = secure_filename(os.path.basename(file_storage.filename or "")) or "certification.pdf"
    file_bytes = file_storage.read()
    if len(file_bytes) < 5 or file_bytes[:5] != b'%PDF-':
        return None, None, "El archivo no es un PDF válido."
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    unique_tag = uuid.uuid4().hex[:8]
    file_filename = f"{int(time_module.time())}_{unique_tag}_{safe_name}"
    saved_path = os.path.join(UPLOAD_FOLDER, file_filename)
    with open(saved_path, 'wb') as f_out:
        f_out.write(file_bytes)
    return f"uploads/certifications/{file_filename}", file_bytes, None


@certifications_bp.route('/api/certifications', methods=['GET'])
def get_certifications_route():
    try:
        data = db_manager.get_certifications()
        if isinstance(data, dict):
            data["success"] = True
        return jsonify(data)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@certifications_bp.route('/api/certifications', methods=['POST'])
def add_certification_route():
    try:
        json_body = request.get_json(silent=True) or {}
        title = request.form.get('title') or json_body.get('title')
        start_date = request.form.get('start_date') or json_body.get('start_date')
        end_date = request.form.get('end_date') or json_body.get('end_date')
        issue_date = request.form.get('issue_date') or json_body.get('issue_date')
        cpa_name = request.form.get('cpa_name') or json_body.get('cpa_name')
        notes = request.form.get('notes') or json_body.get('notes')
        try:
            sales_ars = float(request.form.get('certified_sales_ars') or request.form.get('sales_ars') or json_body.get('certified_sales_ars') or json_body.get('sales_ars') or 0.0)
            buys_ars = float(request.form.get('certified_buys_ars') or request.form.get('buys_ars') or json_body.get('certified_buys_ars') or json_body.get('buys_ars') or 0.0)
            pnl_ars = float(request.form.get('certified_pnl_ars') or request.form.get('pnl_ars') or json_body.get('certified_pnl_ars') or json_body.get('pnl_ars') or 0.0)
        except (ValueError, TypeError):
            sales_ars, buys_ars, pnl_ars = 0.0, 0.0, 0.0

        if not title or not start_date or not end_date:
            return jsonify({"error": "Faltan campos obligatorios (título, fecha de inicio y fecha de fin)."}), 400

        file_path = None
        file_bytes = None
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename != '':
                file_path, file_bytes, pdf_err = _validate_and_save_pdf(file)
                if pdf_err:
                    return jsonify({"error": pdf_err}), 400

        try:
            cert_id = db_manager.add_certification(
                title=title,
                start_date=start_date,
                end_date=end_date,
                issue_date=issue_date,
                cpa_name=cpa_name,
                notes=notes,
                file_path=file_path,
                sync_status=not bool(file_bytes)
            )
        except TypeError:
            cert_id = db_manager.add_certification(
                title=title,
                start_date=start_date,
                end_date=end_date,
                issue_date=issue_date,
                cpa_name=cpa_name,
                notes=notes,
                file_path=file_path
            )

        extracted_txs_count = 0
        purged_provisional_count = 0
        auth_ids = {c.get('id') if isinstance(c, dict) else c for c in getattr(db_manager, 'AUTHENTIC_CERTIFICATIONS', [])}
        if file_bytes:
            extracted_txs = []
            try:
                extracted_txs = pdf_table_extractor.extract_transactions_from_pdf_stream(file_bytes, filename=title) or []
                if extracted_txs and len(extracted_txs) > 0:
                    rep_res = db_manager.apply_certified_period_replacement(cert_id, start_date, end_date, extracted_txs)
                    if rep_res.get('success'):
                        extracted_txs_count = rep_res.get('inserted_count', 0)
                        purged_provisional_count = rep_res.get('purged_count', 0)
            except Exception as e:
                print(f"[ADD CERT EXTRACTION ERROR] {e}")
            finally:
                try:
                    db_manager.sync_certified_transactions_status()
                except Exception as e_sync:
                    print(f"[ADD CERT SYNC ERROR] {e_sync}")

            if sales_ars == 0.0 and buys_ars == 0.0 and pnl_ars == 0.0 and cert_id not in auth_ids:
                try:
                    import fitz
                    from parsers.pdf_table_extractor import extract_cpa_summary_table
                    summary_fn = getattr(pdf_table_extractor, 'extract_cpa_summary_table', extract_cpa_summary_table)
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    try:
                        cpa_sum = summary_fn(doc) or {}
                    finally:
                        doc.close()
                    sales_ars = float(cpa_sum.get("total_ventas") or 0.0)
                    buys_ars = float(cpa_sum.get("total_compras") or 0.0)
                    pnl_ars = float(cpa_sum.get("ganancia_neta") or 0.0)
                except Exception:
                    pass

                if sales_ars == 0.0 and buys_ars == 0.0 and pnl_ars == 0.0 and extracted_txs:
                    for tx in extracted_txs:
                        op = str(tx.get('Tipo de Operación') or tx.get('tipo_operacion') or '').strip().lower()
                        m_ars = float(tx.get('Monto ARS') or tx.get('monto_ars') or 0.0)
                        if 'venta' in op or 'sell' in op:
                            sales_ars += m_ars
                        elif 'compra' in op or 'buy' in op:
                            buys_ars += m_ars
                    sales_ars = round(sales_ars, 2)
                    buys_ars = round(buys_ars, 2)
                    pnl_ars = round(sales_ars - buys_ars, 2)

        if (sales_ars != 0.0 or buys_ars != 0.0 or pnl_ars != 0.0) and cert_id not in auth_ids:
            try:
                conn = db_manager.get_connection()
                try:
                    conn.cursor().execute(
                        "UPDATE certifications SET certified_sales_ars = ?, certified_buys_ars = ?, certified_pnl_ars = ? WHERE id = ?",
                        (sales_ars, buys_ars, pnl_ars, cert_id)
                    )
                    conn.commit()
                finally:
                    conn.close()
            except Exception as e_tot:
                print(f"[ADD CERT TOTALS UPDATE ERROR] {e_tot}")

        invalidate_Dashboard_Cache()
        cert = db_manager.get_certification_by_id(cert_id)
        if isinstance(cert, dict):
            cert.setdefault("certified_sales_ars", sales_ars)
            cert.setdefault("certified_buys_ars", buys_ars)
            cert.setdefault("certified_pnl_ars", pnl_ars)
        return jsonify({
            "success": True, 
            "certification": cert,
            "extracted_txs_count": extracted_txs_count,
            "purged_provisional_count": purged_provisional_count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


upload_certification = add_certification_route


@certifications_bp.route('/api/certifications/replace-period', methods=['POST'])
def replace_period():
    data = request.get_json(silent=True) or {}
    cert_id = data.get('cert_id') or request.form.get('cert_id')
    start_date = data.get('start_date') or request.form.get('start_date')
    end_date = data.get('end_date') or request.form.get('end_date')
    certified_txs = data.get('certified_txs', [])

    if not cert_id or not start_date or not end_date:
        return jsonify({"success": False, "error": "Faltan parámetros cert_id, start_date o end_date"}), 400

    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename != '':
            _, file_bytes, pdf_err = _validate_and_save_pdf(file)
            if pdf_err:
                return jsonify({"success": False, "error": pdf_err}), 400
            if not certified_txs and file_bytes:
                certified_txs = pdf_table_extractor.extract_transactions_from_pdf_stream(
                    file_bytes, filename=os.path.basename(file.filename)
                )

    try:
        res = db_manager.apply_certified_period_replacement(cert_id, start_date, end_date, certified_txs)
        invalidate_Dashboard_Cache()
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


replace_period_certified = replace_period
replace_certified_period_route = replace_period


@certifications_bp.route('/api/certifications/upload-pdf', methods=['POST'])
@certifications_bp.route('/api/certifications/parse_pdf', methods=['POST'])
def parse_certification_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No se envió ningún archivo."}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"error": "Archivo vacío o no válido."}), 400

    try:
        file_bytes = file.read()
        if len(file_bytes) < 5 or file_bytes[:5] != b'%PDF-':
            return jsonify({"success": False, "error": "El archivo no es un PDF válido."}), 400
        fname = os.path.basename(request.form.get('filename') or file.filename)
        extracted = extract_info_from_pdf_stream(file_bytes, filename=fname)

        if len(file_bytes) < 15 * 1024 * 1024 and request.args.get('count_txs') == 'true':
            try:
                extracted_txs = pdf_table_extractor.extract_transactions_from_pdf_stream(file_bytes, filename=fname)
                extracted["detected_transactions_count"] = len(extracted_txs)
            except Exception:
                extracted["detected_transactions_count"] = 0
        else:
            extracted["detected_transactions_count"] = 0
        
        start_d = extracted.get('start_date')
        end_d = extracted.get('end_date')
        if start_d and end_d:
            extracted["provisional_to_replace_count"] = db_manager.count_provisional_transactions_in_range(start_d, end_d)
        else:
            extracted["provisional_to_replace_count"] = 0

        return jsonify({"success": True, "extracted": extracted})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@certifications_bp.route('/api/certifications/preview_pdf', methods=['POST'])
def preview_certification_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No se envió ningún archivo."}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"error": "Archivo vacío o no válido."}), 400

    try:
        file_bytes = file.read()
        if len(file_bytes) < 5 or file_bytes[:5] != b'%PDF-':
            return jsonify({"success": False, "error": "El archivo no es un PDF válido."}), 400
        fname = os.path.basename(request.form.get('filename') or file.filename)
        extracted_cpa = extract_info_from_pdf_stream(file_bytes, filename=fname)
        
        extracted_txs = pdf_table_extractor.extract_transactions_from_pdf_stream(file_bytes, filename=fname)
        
        start_d = extracted_cpa.get('start_date')
        end_d = extracted_cpa.get('end_date')
        provisional_count = 0
        if start_d and end_d:
            provisional_count = db_manager.count_provisional_transactions_in_range(start_d, end_d)
            
        exchanges_map = {}
        coins_map = {}
        for tx in extracted_txs:
            ex = tx.get('Exchange', 'Desconocido')
            c = tx.get('Moneda', 'USDT')
            exchanges_map[ex] = exchanges_map.get(ex, 0) + 1
            coins_map[c] = coins_map.get(c, 0) + 1

        return jsonify({
            "success": True,
            "cpa_info": extracted_cpa,
            "transactions_count": len(extracted_txs),
            "transactions_preview": extracted_txs[:50],
            "exchanges_summary": exchanges_map,
            "coins_summary": coins_map,
            "provisional_to_replace_count": provisional_count
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@certifications_bp.route('/api/certifications/sync_all_tables', methods=['POST'])
def sync_all_certifications_tables():
    try:
        certs = db_manager.get_certifications().get('certifications', [])
        total_inserted = 0
        total_purged = 0
        processed_certs = []
        
        for c in certs:
            c_id = c.get('id')
            f_path = c.get('file_path')
            s_date = c.get('start_date')
            e_date = c.get('end_date')
            
            if not f_path or not s_date or not e_date:
                continue
                
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            full_path = os.path.realpath(os.path.join(base_dir, f_path))
            real_upload_dir = os.path.realpath(UPLOAD_FOLDER)
            if not (full_path == real_upload_dir or full_path.startswith(real_upload_dir + os.sep)):
                continue
            if not os.path.exists(full_path):
                continue
                
            try:
                with open(full_path, 'rb') as fp:
                    f_bytes = fp.read()
                txs = pdf_table_extractor.extract_transactions_from_pdf_stream(f_bytes, filename=os.path.basename(f_path))
                if txs and len(txs) > 0:
                    rep = db_manager.apply_certified_period_replacement(c_id, s_date, e_date, txs)
                    if rep.get('success'):
                        ins = rep.get('inserted_count', 0)
                        pur = rep.get('purged_count', 0)
                        total_inserted += ins
                        total_purged += pur
                        processed_certs.append({
                            "id": c_id,
                            "title": c.get('title'),
                            "inserted": ins,
                            "purged": pur
                        })
            except Exception as ex:
                print(f"[SYNC ALL TABLES ERROR] Cert ID {c_id}: {ex}")
                
        try:
            db_manager.sync_certified_transactions_status()
        except Exception as e_sync:
            print(f"[SYNC ALL TABLES STATUS ERROR] {e_sync}")
        invalidate_Dashboard_Cache()
        return jsonify({
            "success": True,
            "total_inserted": total_inserted,
            "total_purged": total_purged,
            "processed_certifications": processed_certs
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@certifications_bp.route('/api/certifications/<int:cert_id>', methods=['DELETE'])
def delete_certification_route(cert_id):
    try:
        cert = db_manager.get_certification_by_id(cert_id)
        if not cert:
            return jsonify({"error": "Certificado no encontrado."}), 404
        
        if cert.get('file_path'):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            full_path = os.path.realpath(os.path.join(base_dir, cert['file_path']))
            real_upload_dir = os.path.realpath(UPLOAD_FOLDER)
            if (full_path == real_upload_dir or full_path.startswith(real_upload_dir + os.sep)) and os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except Exception as ex:
                    logging.warning(f"Error al eliminar archivo físico de certificación {cert_id} ({full_path}): {ex}")

        db_manager.delete_certification(cert_id)
        invalidate_Dashboard_Cache()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

delete_certification_endpoint = delete_certification_route


@certifications_bp.route('/api/certifications/download/<int:cert_id>', methods=['GET'])
def download_certification_file(cert_id):
    try:
        from flask import send_from_directory
        cert = db_manager.get_certification_by_id(cert_id)
        if not cert or not cert.get('file_path'):
            return jsonify({"error": "Archivo no encontrado"}), 404
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        real_upload_dir = os.path.realpath(UPLOAD_FOLDER)
        full_path = os.path.realpath(os.path.join(base_dir, cert['file_path']))
        
        if not (full_path == real_upload_dir or full_path.startswith(real_upload_dir + os.sep)):
            return jsonify({"error": "Acceso denegado a la ruta del archivo"}), 403
            
        if not os.path.exists(full_path):
            return jsonify({"error": "El archivo adjunto no existe en el servidor."}), 404

        directory = os.path.dirname(full_path)
        filename = os.path.basename(full_path)
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

serve_certification_pdf = download_certification_file


@certifications_bp.route('/api/certifications/next_start', methods=['GET'])
def get_next_cert_start():
    try:
        last_end_dt = db_manager.get_last_certification_end_datetime()
        if last_end_dt:
            next_start = (last_end_dt + timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')
            return jsonify({
                "next_start_date": next_start,
                "last_cert_end": last_end_dt.strftime('%Y-%m-%d %H:%M:%S')
            })
        return jsonify({"next_start_date": None, "last_cert_end": None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@certifications_bp.route('/api/certifications/sync', methods=['POST'])
def sync_certifications_route():
    try:
        db_manager.sync_certified_transactions_status()
        invalidate_Dashboard_Cache()
        return jsonify({"success": True, "message": "Estado de certificaciones sincronizado correctamente."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
