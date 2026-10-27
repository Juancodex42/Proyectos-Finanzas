"""Punto de entrada principal del servidor Flask para Nexus Quant Terminal.
Configura el entorno de rutas modulares, cabeceras de seguridad HTTP y ciclo de vida de bots.
Referencia de diseño: docs/ARQUITECTURA.md"""

import os
import sys

# Garantiza que el paquete modular `src/` esté en sys.path al ejecutar `python app.py`
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from flask import Flask, render_template
from flask_cors import CORS

from config import Config
from routes import register_blueprints
from routes.bot_routes import init_bot_system
from routes.utils import (
    _cache_lock,
    _data_cache,
    clean_json_data,
    extract_json_from_output,
    extract_markov_params,
    fetch_and_save_binance_klines,
    get_data_dir,
    get_genetic_optimizer_path,
    is_safe_interval,
    is_safe_symbol,
    load_csv_data,
    optimizer,
    preserve_peaks_subsample,
    simulator,
    sort_intervals,
    sse_response,
    stats_engine,
)

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "nexus-quant-demo-secret-key")
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5001", "http://127.0.0.1:5001"]}})

# Register modular Blueprints
register_blueprints(app)


@app.after_request
def add_security_headers(response):
    """Agrega cabeceras de endurecimiento HTTP a todas las respuestas."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.route("/")
def index():
    """Renderiza la interfaz principal de Nexus Quant Terminal."""
    return render_template("index.html")


if __name__ == "__main__":
    os.makedirs(Config.DATA_DIR, exist_ok=True)
    PORT = int(os.environ.get("PORT", 5001))
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    use_debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")
    use_reloader = os.environ.get("FLASK_USE_RELOADER", "0").lower() in ("1", "true")

    if not use_reloader or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        try:
            init_bot_system()
        except Exception as e:
            print(f"[App] Notice: Dual Bot system initialization skipped or deferred: {e}")

    print(f"[App] Starting Nexus Quant Terminal v2.0 on http://{host}:{PORT} ...")
    app.run(host=host, port=PORT, debug=use_debug, use_reloader=use_reloader)
