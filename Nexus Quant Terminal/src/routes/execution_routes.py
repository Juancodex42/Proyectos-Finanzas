"""
routes/execution_routes.py
Endpoints para el Módulo de Ejecución Automática Dual-Bot en Binance.
"""

import json
import time
from flask import Blueprint, request, jsonify, Response
from engine.execution.dual_bot_manager import DualBotManager

execution_bp = Blueprint('execution', __name__, url_prefix='/api/execution')
manager = DualBotManager()


@execution_bp.route('/config', methods=['POST'])
def configure_api():
    """Configura las claves de API de Binance y valida la conectividad."""
    data = request.get_json() or {}
    api_key = data.get('api_key', '').strip()
    api_secret = data.get('api_secret', '').strip()
    testnet = bool(data.get('testnet', True))

    if not api_key or not api_secret:
        return jsonify({"success": False, "error": "API Key y Secret son requeridos"}), 400

    result = manager.set_credentials(api_key, api_secret, testnet=testnet)
    return jsonify(result)


@execution_bp.route('/status', methods=['GET'])
def get_status():
    """Obtiene el estado completo de ambos bots, balances y gráficas de equidad."""
    status = manager.get_status()
    return jsonify(status)


@execution_bp.route('/ping', methods=['GET'])
def ping_binance():
    """Endpoint de Heartbeat activo para la UI (mide latencia en tiempo real)."""
    if manager.client and not manager.mock_mode:
        res = manager.client.ping()
    else:
        res = {"connected": False, "mock_mode": True, "latency_ms": 14.2, "status": "sandbox_active"}
    return jsonify(res)



@execution_bp.route('/toggle-bot', methods=['POST'])
def toggle_bot():
    """Enciende, pausa o apaga uno de los bots (bot_1 o bot_2)."""
    data = request.get_json() or {}
    bot_id = data.get('bot_id')
    new_state = data.get('state')  # RUNNING, PAUSED, STOPPED

    if not bot_id or not new_state:
        return jsonify({"success": False, "error": "bot_id y state son requeridos"}), 400

    result = manager.toggle_bot(bot_id, new_state)
    return jsonify(result)


@execution_bp.route('/bot1-reset-streak', methods=['POST'])
def reset_streak():
    """Resetea manualmente la racha del Bot 1 o deposita ganancias a la base."""
    data = request.get_json() or {}
    deposit = bool(data.get('deposit_to_base', True))
    result = manager.reset_bot1_streak(deposit_to_base=deposit)
    return jsonify(result)


@execution_bp.route('/update-config', methods=['POST'])
def update_config():
    """Actualiza parámetros de estrategia, par, ratio o presupuesto."""
    data = request.get_json() or {}
    bot_id = data.get('bot_id')
    updates = data.get('updates', {})

    if not bot_id or not updates:
        return jsonify({"success": False, "error": "bot_id y updates son requeridos"}), 400

    result = manager.update_bot_config(bot_id, updates)
    return jsonify(result)


@execution_bp.route('/panic-close', methods=['POST'])
def panic_close():
    """BOTÓN DE PÁNICO (KILL SWITCH): Detiene ambos bots y cierra posiciones inmediatamente."""
    result = manager.panic_close_all()
    return jsonify(result)


@execution_bp.route('/simulate-trade', methods=['POST'])
def simulate_trade():
    """Permite simular un trade en el sandbox para ver reaccionar las gráficas en vivo."""
    data = request.get_json() or {}
    bot_id = data.get('bot_id', 'bot_1')
    is_win = bool(data.get('is_win', True))
    pnl = float(data.get('pnl', 12.50))
    symbol = data.get('symbol', 'BTC/USDT')

    manager.record_simulated_trade(bot_id=bot_id, is_win=is_win, pnl_usd=pnl, symbol=symbol)
    return jsonify({"success": True, "status": manager.get_status()})


@execution_bp.route('/stream')
def execution_stream():
    """SSE Stream en tiempo real que emite el estado del Dual-Bot cada 2 segundos."""
    def generate():
        while True:
            st = manager.get_status()
            yield f"data: {json.dumps(st)}\n\n"
            time.sleep(2.0)

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive'
    })


@execution_bp.route('/telegram/config', methods=['POST'])
def configure_telegram():
    """Configura las credenciales de Telegram Bot Token y Chat ID."""
    data = request.get_json() or {}
    token = data.get('token', '').strip()
    chat_ids = data.get('chat_ids', [])

    if isinstance(chat_ids, (str, int)):
        chat_ids = [chat_ids]

    if not token or not chat_ids:
        return jsonify({"success": False, "error": "Token y Chat ID son requeridos"}), 400

    res = manager.set_telegram_credentials(bot_token=token, allowed_chat_ids=chat_ids)
    return jsonify(res)


@execution_bp.route('/telegram/test', methods=['POST'])
def test_telegram_message():
    """Envía un mensaje de prueba al Telegram configurado."""
    if not manager.telegram_bot or not manager.telegram_bot.is_configured():
        return jsonify({"success": False, "error": "Telegram Bot no está configurado aún"}), 400

    for cid in manager.telegram_bot.allowed_chat_ids:
        manager.telegram_bot.send_message(
            cid,
            "🧪 *MENSAJE DE PRUEBA EXITOSO*\n"
            "Tu conexión desde la terminal de trading a tu celular funciona a la perfección. 🚀",
            reply_markup=manager.telegram_bot._get_main_keyboard()
        )
    return jsonify({"success": True, "message": "Mensaje de prueba enviado."})

