import os
import sys
import copy
import subprocess
import re
from flask import Blueprint, request, jsonify
from dotenv import load_dotenv
import db_manager
import config_manager
from utils.status_cache import invalidate_status_cache
from services.cache_service import invalidate_analytics_cache

settings_bp = Blueprint('settings_bp', __name__)


@settings_bp.route('/api/settings', methods=['GET'])
def get_settings():
    try:
        config = config_manager.load_config()
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/api/settings', methods=['POST'])
def update_settings():
    try:
        data = request.json or {}
        exchange = data.get('exchange')
        field = data.get('field')
        value = data.get('value')
        
        if config_manager.update_mapping(exchange, field, value):
            invalidate_analytics_cache()
            return jsonify({"status": "success"})
        else:
            return jsonify({"error": f"Exchange '{exchange}' o campo '{field}' no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

save_mapping = update_settings


@settings_bp.route('/api/exchange-configs', methods=['GET'])
@settings_bp.route('/api/exchanges', methods=['GET'])
def list_exchanges():
    exchanges = db_manager.get_all_exchanges()
    for ex in exchanges:
        if 'apiKeys' in ex and isinstance(ex['apiKeys'], dict):
            ex['apiKeys'] = {k: "***" for k in ex['apiKeys']}
    return jsonify(exchanges)


@settings_bp.route('/api/exchange-configs', methods=['POST'])
@settings_bp.route('/api/exchanges', methods=['POST'])
def create_exchange():
    data = request.json or {}
    name = data.get('name')
    if not name:
        return jsonify({"error": "El nombre del exchange es obligatorio"}), 400
    date_format = data.get('dateFormat', '%d/%m/%Y %H:%M:%S')
    mapping = data.get('mapping', {})
    res = db_manager.add_custom_exchange(name, date_format, mapping)
    invalidate_status_cache()
    invalidate_analytics_cache()
    return jsonify({"success": True, "exchange": res})


@settings_bp.route('/api/exchanges/<ex_id>/mapping', methods=['PUT'])
def update_exchange_mapping_route(ex_id):
    data = request.json or {}
    mapping = data.get('mapping', {})
    date_format = data.get('dateFormat', '%d/%m/%Y %H:%M:%S')
    db_manager.update_exchange_mapping(ex_id, mapping, date_format)
    invalidate_analytics_cache()
    return jsonify({"success": True})

save_mappings = update_exchange_mapping_route


@settings_bp.route('/api/exchanges/<ex_id>/apikeys', methods=['PUT'])
def update_exchange_apikeys_route(ex_id):
    data = request.json or {}
    api_keys = data.get('apiKeys', {})
    db_manager.update_exchange_apikeys(ex_id, api_keys)
    invalidate_status_cache()
    invalidate_analytics_cache()
    return jsonify({"success": True})

update_exchange_keys = update_exchange_apikeys_route


@settings_bp.route('/api/exchanges/<ex_id>', methods=['DELETE'])
def delete_exchange_route(ex_id):
    db_manager.delete_exchange(ex_id)
    invalidate_status_cache()
    invalidate_analytics_cache()
    return jsonify({"success": True})


@settings_bp.route('/api/scheduler/status', methods=['GET'])
def get_scheduler_status():
    from services.auto_sync_daemon import get_auto_sync_status
    daemon_status = get_auto_sync_status()
    try:
        cmd = ["schtasks", "/query", "/tn", "SistemaContable_AutoSync"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            output = res.stdout.lower()
            is_enabled = "deshabilitado" not in output and "disabled" not in output
            return jsonify({**daemon_status, "exists": True, "enabled": bool(daemon_status.get("enabled", is_enabled))})
    except Exception:
        pass
    return jsonify(daemon_status)


@settings_bp.route('/api/scheduler/toggle', methods=['POST'])
def toggle_scheduler():
    from services.auto_sync_daemon import set_auto_sync_enabled
    data = request.json or {}
    enable = bool(data.get('enabled', True))
    hour = data.get('hour', '20:00')
    frequency = str(data.get('frequency', 'hourly')).lower()
    
    if not re.match(r'^\d{2}:\d{2}$', hour):
        hour = '20:00'
        
    if frequency not in ('daily', 'hourly', 'weekly'):
        frequency = 'hourly'

    daemon_status = set_auto_sync_enabled(enable)
        
    try:
        if enable:
            bg_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workers", "auto_sync_worker.py")
            python_exe = sys.executable
            create_cmd = [
                "schtasks", "/create", "/sc", frequency.upper(), "/st", hour, 
                "/tn", "SistemaContable_AutoSync", 
                "/tr", f'"{python_exe}" "{bg_script}"', 
                "/f"
            ]
            res = subprocess.run(create_cmd, capture_output=True, text=True)
            if res.returncode == 0:
                subprocess.run(["schtasks", "/change", "/tn", "SistemaContable_AutoSync", "/enable"], capture_output=True)
        else:
            subprocess.run(["schtasks", "/change", "/tn", "SistemaContable_AutoSync", "/disable"], capture_output=True)
    except Exception:
        pass

    return jsonify({
        "success": True,
        "enabled": daemon_status["enabled"],
        "hour": hour,
        "frequency": frequency
    })


@settings_bp.route('/api/env', methods=['GET'])
def get_env():
    keys = config_manager.get_env_keys()
    masked_keys = copy.deepcopy(keys)
    sensitive_words = ('SECRET', 'PASSWORD', 'PASSPHRASE', 'KEY')
    for k, v in masked_keys.items():
        if v and any(w in k.upper() for w in sensitive_words):
            if len(v) > 6:
                masked_keys[k] = v[:3] + "***" + v[-3:]
            else:
                masked_keys[k] = "***"
    return jsonify(masked_keys)


@settings_bp.route('/api/env', methods=['POST'])
def save_env():
    data = request.json or {}
    try:
        config_manager.set_env_keys(data)
        
        from config_manager import ENV_FILE
        load_dotenv(dotenv_path=ENV_FILE, override=True)
        invalidate_status_cache()
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
