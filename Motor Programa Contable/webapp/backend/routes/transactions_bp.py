import io
import os
import logging
from flask import Blueprint, request, jsonify, send_file
import db_manager
import processor_lib
from utils.exceptions import MissingColumnsError
try:
    from services.cache_service import invalidate_Dashboard_Cache
except ImportError:
    from services.cache_service import invalidate_analytics_cache as invalidate_Dashboard_Cache

transactions_bp = Blueprint('transactions_bp', __name__)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')


@transactions_bp.route('/api/transactions', methods=['GET'])
def get_transactions_route():
    start = request.args.get('start')
    end = request.args.get('end')
    exchanges = request.args.get('exchanges')
    status = request.args.get('status')
    exch_list = [e.strip() for e in exchanges.split(',')] if exchanges else None
    return jsonify(db_manager.get_transactions(exchanges=exch_list, date_start=start, date_end=end, status_filter=status))


@transactions_bp.route('/api/upload/inspect', methods=['POST'])
def inspect_upload():
    files = request.files.getlist('files') or request.files.getlist('files[]') or request.files.getlist('file')
    if not files:
        return jsonify({'error': 'No file provided', 'success': False}), 400
    
    inspections = []
    for f in files:
        fname = os.path.basename(f.filename or '') or 'upload.csv'
        content = f.read()
        f_obj = io.BytesIO(content)
        cols = processor_lib.extract_preview_columns(f_obj, fname)
        meta = processor_lib.detect_exchange(f_obj, fname, preview_cols=cols)
        inspections.append({
            'filename': fname,
            'detected_exchange': meta.get('detected_exchange') or 'Otros',
            'confidence': meta.get('confidence', 0.0),
            'match_reasons': meta.get('match_reasons', []),
            'preview_columns': list(cols)[:20]
        })
    return jsonify({'success': True, 'inspections': inspections})


@transactions_bp.route('/api/upload', methods=['POST'])
@transactions_bp.route('/process', methods=['POST'])
@transactions_bp.route('/upload', methods=['POST'])
def process_files():
    files = request.files.getlist('files') or request.files.getlist('files[]') or request.files.getlist('file')
    if not files:
        return jsonify({'error': 'No files provided', 'status': 'error', 'success': False}), 400
        
    override_exchange = request.form.get('exchange') or request.form.get('override_exchange')
    results = []
    warnings = []
    total_tx = 0
    
    for file in files:
        safe_name = os.path.basename(file.filename or '') or 'upload.csv'
        filename = safe_name
        _ = os.path.join(UPLOAD_FOLDER, safe_name)
        content = file.read()
        file_obj = io.BytesIO(content)
        
        try:
            processed_data, raw_sample = processor_lib.process_uploaded_file(file_obj, filename, override_exchange=override_exchange)
            # Semantic Guardrail: Filter out empty dummy rows and spurious fiat crypto assets
            clean_processed = []
            for tx in (processed_data or []):
                if tx is None:
                    continue
                coin = str(tx.get('Moneda') or tx.get('moneda') or '').upper().strip()
                tipo = str(tx.get('Tipo de Operación') or tx.get('tipo_operacion') or '').upper().strip()
                mc = float(tx.get('Monto Compra (Cripto)', 0.0) or tx.get('monto_compra_cripto', 0.0) or 0.0)
                mv = float(tx.get('Monto Venta (Cripto)', 0.0) or tx.get('monto_venta_cripto', 0.0) or 0.0)
                ma = float(tx.get('Monto ARS', 0.0) or tx.get('monto_ars', 0.0) or 0.0)
                if coin in ('ARS', '$', 'PESO', 'PESOS', 'ARGENTIN'):
                    continue
                if 'DESCONOCIDO' in tipo and mc == 0 and mv == 0 and ma == 0:
                    continue
                clean_processed.append(tx)
            processed_data = clean_processed
            
            warned_negative = False
            for tx in processed_data:
                tx['filename'] = filename
                if 'source' not in tx:
                    tx['source'] = 'FILE_UPLOAD'
                m_compra = float(tx.get('Monto Compra (Cripto)', 0.0) or 0.0)
                m_venta = float(tx.get('Monto Venta (Cripto)', 0.0) or 0.0)
                cot_compra = float(tx.get('Cotización Compra', 0.0) or 0.0)
                cot_venta = float(tx.get('Cotización Venta', 0.0) or 0.0)
                
                if (m_compra < 0 or m_venta < 0 or cot_compra < 0 or cot_venta < 0) and not warned_negative:
                    neg_msg = f"El archivo {filename} contiene registros con montos o cotizaciones negativas. Esto generará inconsistencias."
                    logging.warning(neg_msg)
                    warnings.append(neg_msg)
                    warned_negative = True
            
            inserted, skipped = db_manager.insert_transactions(processed_data, trigger_fifo_recalc=False)
            total_tx += inserted
            
            total_ex_counts = {}
            sample_by_ex = {}
            for tx in processed_data:
                ex_val = tx.get('Exchange') or tx.get('exchange') or 'Otros'
                ex = str(ex_val).strip()
                if not ex or ex.lower() in ('none', 'nan', 'null', ''):
                    ex = 'Otros'
                if 'Exchange' in tx:
                    tx['Exchange'] = ex
                elif 'exchange' in tx:
                    tx['exchange'] = ex

                total_ex_counts[ex] = total_ex_counts.get(ex, 0) + 1

                if ex not in sample_by_ex:
                    sample_by_ex[ex] = []
                if len(sample_by_ex[ex]) < 10:
                    sample_by_ex[ex].append(tx)

            representative_sample = []
            for ex_name, ex_rows in sample_by_ex.items():
                representative_sample.extend(ex_rows)

            results.append({
                'filename': filename,
                'count': len(processed_data),
                'inserted': inserted,
                'skipped': skipped,
                'processed_sample': representative_sample,
                'exchange_counts': total_ex_counts,
                'raw_sample': raw_sample
            })
        except MissingColumnsError as e:
            return jsonify({
                'error': 'missing_columns',
                'exchange': e.exchange,
                'missing': e.missing,
                'available': e.available,
                'filename': filename
            }), 400
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            warnings.append(f"No se pudo procesar el archivo {filename}: {str(e)}")
            results.append({
                'filename': filename,
                'error': str(e),
                'count': 0
            })
            
    fifo_warning = None
    cache_warning = None
    if total_tx > 0:
        try:
            from services.fifo_service import recalculate_fifo_costs_db
            recalculate_fifo_costs_db()
        except Exception as e:
            logging.error(f"Error executing batch recalculate_fifo_costs_db: {e}")
            fifo_warning = f"Error al recalcular FIFO: {e}"
            warnings.append(fifo_warning)
            
        try:
            from services.cache_service import invalidate_analytics_cache
            invalidate_analytics_cache()
        except Exception as e_cache:
            logging.error(f"Error invalidating cache after upload: {e_cache}")
            cache_warning = f"Error al invalidar caché: {e_cache}"
            warnings.append(cache_warning)
            
    try:
        gaps = db_manager.check_history_gaps()
        if gaps:
            for gap in gaps:
                deficit_val = gap.get('deficit', gap.get('monto_deficit', 0.0))
                coin_val = gap.get('coin', gap.get('moneda', ''))
                date_val = gap.get('date', gap.get('fecha', ''))
                exch_val = gap.get('exchange', '')
                warnings.append(
                    f"Faltante detectado: Venta de {deficit_val:.4f} {coin_val} en {exch_val} el {date_val} sin compra previa registrada."
                )
    except Exception as e:
        logging.error(f"Error checking gaps for warnings: {e}")
        
    if total_tx == 0 and any('error' in r for r in results):
        first_err = warnings[0] if warnings else (results[0].get('error') if results else 'Error procesando archivos')
        err_res = {
            'status': 'error',
            'success': False,
            'files': results,
            'total_transactions': 0,
            'has_imported_rows': False,
            'warnings': warnings,
            'error': first_err
        }
        if fifo_warning:
            err_res['fifo_warning'] = fifo_warning
        if cache_warning:
            err_res['cache_warning'] = cache_warning
        return jsonify(err_res), 400

    resp_payload = {
        'status': 'success',
        'success': True,
        'files': results, 
        'total_transactions': total_tx,
        'has_imported_rows': total_tx > 0,
        'warnings': warnings
    }
    if fifo_warning:
        resp_payload['fifo_warning'] = fifo_warning
    if cache_warning:
        resp_payload['cache_warning'] = cache_warning
    return jsonify(resp_payload)

upload_files = process_files


@transactions_bp.route('/api/export/excel', methods=['POST'])
@transactions_bp.route('/download', methods=['POST'])
def download_excel():
    data = request.json or {}
    filenames = data.get('filenames', [])
    
    if not filenames:
        return jsonify({"error": "No filenames provided"}), 400
        
    try:
        all_tx_df = db_manager.get_all_transactions_df(include_filename=True)
    except TypeError:
        all_tx_df = db_manager.get_all_transactions_df()
        if not all_tx_df.empty and 'filename' not in all_tx_df.columns:
            try:
                from services.transactions_service import get_all_transactions_df as _get_all_tx_df
                all_tx_df = _get_all_tx_df(include_filename=True)
            except Exception:
                pass
    
    if all_tx_df.empty:
        return jsonify({"error": "No processing history found for these files"}), 404
        
    exchanges_to_keep = []
    real_filenames = []
    for fname in filenames:
        if fname and fname.startswith("Historial_") and fname.endswith(".xlsx"):
            ex_name = fname[10:-5].replace("_", " ")
            exchanges_to_keep.append(ex_name)
        elif fname:
            real_filenames.append(fname)
    if exchanges_to_keep:
        all_tx_df = all_tx_df[all_tx_df['Exchange'].isin(exchanges_to_keep)]
    elif real_filenames and 'filename' in all_tx_df.columns:
        if (all_tx_df['filename'].fillna('') != '').any():
            all_tx_df = all_tx_df[all_tx_df['filename'].isin(real_filenames)]
    all_tx_df = all_tx_df.drop(columns=['filename'], errors='ignore')
        
    if all_tx_df.empty:
        return jsonify({"error": "No data found for the selected exchange"}), 404

    excel_io = processor_lib.generate_excel_bytes(all_tx_df.to_dict(orient='records'))
    if not excel_io:
        return jsonify({"error": "No valid data to generate Excel"}), 400
        
    from datetime import datetime
    year = data.get('year', datetime.now().year)
    
    return send_file(
        excel_io, 
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'Certificacion_Ingresos_{year}_Completo.xlsx'
    )


@transactions_bp.route('/api/deduplicate', methods=['POST'])
def deduplicate_route():
    try:
        purged = db_manager.deduplicate_existing_database()
        fifo_warning = None
        cache_warning = None
        if purged > 0:
            try:
                from services.fifo_service import recalculate_fifo_costs_db
                recalculate_fifo_costs_db()
            except Exception as e_fifo:
                logging.error(f"Error recalculating FIFO after deduplication: {e_fifo}")
                fifo_warning = f"Error al recalcular FIFO: {e_fifo}"
            try:
                invalidate_Dashboard_Cache()
            except Exception as e_cache:
                logging.error(f"Error invalidating cache after deduplication: {e_cache}")
                cache_warning = f"Error al invalidar caché: {e_cache}"
        
        response_payload = {
            "success": True,
            "purged": purged,
            "message": f"Deduplicación completada con éxito. Se purgaron {purged} registros duplicados."
        }
        if fifo_warning:
            response_payload["fifo_warning"] = fifo_warning
        if cache_warning:
            response_payload["cache_warning"] = cache_warning
        return jsonify(response_payload)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@transactions_bp.route('/api/history', methods=['GET'])
def get_history():
    mode = request.args.get('mode', 'exchanges')

    def format_db_date(date_str):
        if not date_str or date_str == '-':
            return '-'
        try:
            dt_part = str(date_str).split(' ')[0]
            parts = dt_part.split('-')
            if len(parts) == 3:
                return f"{parts[2]}/{parts[1]}/{parts[0]}"
        except Exception:
            pass
        return str(date_str)

    if mode == 'files':
        file_history = db_manager.get_uploaded_files_history()
        res = []
        for r in file_history:
            first = format_db_date(r.get('first_tx'))
            last = format_db_date(r.get('last_tx'))
            date_range = f"{first} a {last}" if first != '-' else "-"
            res.append({
                'filename': r.get('filename'),
                'exchange': r.get('exchange'),
                'count': r.get('count', 0),
                'date_range': date_range,
                'first_tx': first,
                'last_tx': last,
                'is_file': True
            })
        return jsonify(res)

    history = db_manager.get_processing_history()
    res = []
    for r in history:
        first = format_db_date(r.get('first_tx'))
        last = format_db_date(r.get('last_tx'))
        date_range = f"{first} a {last}" if first != '-' else "-"
        
        api_first = format_db_date(r.get('api_first_tx'))
        api_last = format_db_date(r.get('api_last_tx'))
        api_range = f"{api_first} a {api_last}" if api_first != '-' and r.get('api_count', 0) > 0 else "-"
        
        file_first = format_db_date(r.get('file_first_tx'))
        file_last = format_db_date(r.get('file_last_tx'))
        file_range = f"{file_first} a {file_last}" if file_first != '-' and r.get('file_count', 0) > 0 else "-"

        clean_name = r.get('exchange', 'Exchange').replace(' ', '_')
        filename = f"Historial_{clean_name}.xlsx"
        
        res.append({
            'exchange': r.get('exchange'),
            'count': r.get('count', 0),
            'filename': filename,
            'date_range': date_range,
            'api_count': r.get('api_count', 0),
            'api_range': api_range,
            'file_count': r.get('file_count', 0),
            'file_range': file_range
        })
    return jsonify(res)


@transactions_bp.route('/api/history/exchange/<path:exchange_name>', methods=['DELETE'])
def delete_exchange_transactions(exchange_name):
    try:
        body = request.get_json(silent=True) or {}
        year = request.args.get('year', type=int) or body.get('year')
        if year is not None:
            try:
                year = int(year)
            except (ValueError, TypeError):
                year = None
        try:
            deleted = db_manager.delete_transactions_by_exchange(exchange_name, year=year)
        except TypeError:
            deleted = db_manager.delete_transactions_by_exchange(exchange_name)
        invalidate_Dashboard_Cache()
        return jsonify({"success": True, "deleted_count": deleted, "exchange": exchange_name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

delete_transactions_bulk_endpoint = delete_exchange_transactions


@transactions_bp.route('/api/history/file/<path:filename>', methods=['DELETE'])
def delete_file_transactions(filename):
    try:
        deleted = db_manager.delete_transactions_by_filename(filename)
        invalidate_Dashboard_Cache()
        return jsonify({"success": True, "deleted_count": deleted, "filename": filename})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

