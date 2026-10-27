import os
import json
import time
import subprocess
from flask import Blueprint, jsonify, request
from routes.utils import (
    get_genetic_optimizer_path,
    extract_json_from_output,
    clean_json_data,
    is_safe_symbol,
    is_safe_interval,
    sse_response,
    get_data_dir,
)

genetic_bp = Blueprint('genetic', __name__)


@genetic_bp.route('/api/genetic/run', methods=['POST'])
def run_genetic_optimization():
    try:
        req = request.json or {}
        pair = req.get('pair', 'BTCUSDT')
        interval = req.get('interval', '1h')
        if not is_safe_symbol(pair) or not is_safe_interval(interval):
            return jsonify({'error': 'Par o intervalo no válido.'}), 400
        expiry = int(req.get('expiry', 1))
        min_trades = float(req.get('min_trades', 5.0))
        generations = int(req.get('generations', 50))
        population = int(req.get('population', 200))
        
        if expiry < 1:
            return jsonify({'error': 'expiry debe ser mayor o igual a 1.'}), 400
        if min_trades < 0.1:
            return jsonify({'error': 'min_trades debe ser al menos 0.1.'}), 400
        if generations < 1 or generations > 500:
            return jsonify({'error': 'generations debe estar entre 1 y 500.'}), 400
        if population < 10 or population > 1000:
            return jsonify({'error': 'population debe estar entre 10 y 1000.'}), 400
        
        filename = f"{pair}_{interval}.csv"
        data_dir = get_data_dir()
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': f'Datos no encontrados para {pair} {interval}'}), 404
            
        exe_path = get_genetic_optimizer_path()
        if not exe_path:
            return jsonify({'error': 'El ejecutable del optimizador genetico en Rust no ha sido compilado. Ejecuta cargo build --release en la carpeta correspondiente.'}), 500
                
        cmd = [
            exe_path,
            "--csv", filepath,
            "--expiry", str(expiry),
            "--min-trades", str(min_trades),
            "--generations", str(generations),
            "--population", str(population)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        try:
            output_json = extract_json_from_output(result.stdout)
            return jsonify(clean_json_data(output_json))
        except Exception as json_err:
            return jsonify({'error': 'Error al parsear el JSON retornado por el optimizador.', 'details': result.stdout, 'stderr': result.stderr, 'exception': str(json_err)}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@genetic_bp.route('/api/genetic/run-stream', methods=['GET'])
def run_genetic_optimization_stream():
    pair = request.args.get('pair', 'BTCUSDT')
    interval = request.args.get('interval', '1h')
    if not is_safe_symbol(pair) or not is_safe_interval(interval):
        return jsonify({'error': 'Par o intervalo no válido.'}), 400
    expiry = int(request.args.get('expiry', 1))
    min_trades = float(request.args.get('min_trades', 5.0))
    generations = int(request.args.get('generations', 50))
    population = int(request.args.get('population', 200))
    
    if expiry < 1:
        return jsonify({'error': 'expiry debe ser mayor o igual a 1.'}), 400
    if min_trades < 0.1:
        return jsonify({'error': 'min_trades debe ser al menos 0.1.'}), 400
    if generations < 1 or generations > 500:
        return jsonify({'error': 'generations debe estar entre 1 y 500.'}), 400
    if population < 10 or population > 1000:
        return jsonify({'error': 'population debe estar entre 10 y 1000.'}), 400

    def event_stream():
        try:
            filename = f"{pair}_{interval}.csv"
            data_dir = get_data_dir()
            filepath = os.path.join(data_dir, filename)
            if not os.path.exists(filepath):
                yield f"data: {json.dumps({'type': 'error', 'message': f'Datos no encontrados para {pair} {interval}'})}\n\n"
                return
                
            exe_path = get_genetic_optimizer_path()
            if not exe_path:
                yield f"data: {json.dumps({'type': 'error', 'message': 'El ejecutable en Rust no está compilado.'})}\n\n"
                return
                    
            cmd = [
                exe_path,
                "--csv", filepath,
                "--expiry", str(expiry),
                "--min-trades", str(min_trades),
                "--generations", str(generations),
                "--population", str(population)
            ]
            
            yield f"data: {json.dumps({'type': 'log', 'message': 'Ejecutando algoritmo genético en Rust...'})}\n\n"
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            start_time = time.time()
            final_output = ""
            
            try:
                for line in process.stdout:
                    line_str = line.strip()
                    if line_str.startswith("PROGRESS:"):
                        parts = line_str.split(" ")[1].split("/")
                        current_gen = int(parts[0])
                        total_gens = int(parts[1])
                        progress_pct = (current_gen / total_gens) * 100
                        
                        elapsed = time.time() - start_time
                        eta = (elapsed / current_gen) * (total_gens - current_gen) if current_gen > 0 else 0
                        
                        yield f"data: {json.dumps({'type': 'progress', 'progress': progress_pct, 'eta': eta, 'log': f'Generación {current_gen}/{total_gens} completada.'})}\n\n"
                    else:
                        final_output += line
                        
                process.wait()
            except (GeneratorExit, BaseException) as e:
                if process.poll() is None:
                    try:
                        process.kill()
                        process.wait(timeout=1.0)
                    except Exception:
                        pass
                raise e
            finally:
                if process.poll() is None:
                    try:
                        process.kill()
                    except Exception:
                        pass
            if process.returncode != 0:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Fallo del optimizador Rust con código de salida {process.returncode}'})}\n\n"
                return
                
            try:
                output_json = extract_json_from_output(final_output)
                yield f"data: {json.dumps({'type': 'result', 'data': output_json})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Error al decodificar salida: {str(e)}', 'details': final_output})}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return sse_response(event_stream())
