import os
import sys
import logging
from flask import Flask, jsonify
from flask_cors import CORS

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
COMPAT_DIR = os.path.join(BACKEND_DIR, "compat")
for _p in [BACKEND_DIR, COMPAT_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import db_manager
from parsers.pdf_cert_helper import (
    extract_info_from_pdf_stream,
    normalize_issue_date,
    normalize_date_str,
    normalize_full_timestamp
)
from routes import (
    transactions_bp,
    reports_bp,
    certifications_bp,
    reconciliation_bp,
    settings_bp,
    api_sync_bp,
    audit_declarations_bp
)

app = Flask(__name__)

# [Decisión de diseño / Arquitectura]:
# CryptoTax Pro es una aplicación de escritorio local monousuario en Windows.
# Se ejecuta exclusivamente sobre localhost (127.0.0.1) sirviendo la interfaz React local.
CORS(app, resources={r"/*": {"origins": [
    r"http://localhost:\d+",
    r"http://127.0.0.1:\d+",
    r"http://\[::1\]:\d+"
]}})

# Uploads directory and limits configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
CERT_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'certifications')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CERT_UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max upload limit

# Initialize database on startup
db_manager.init_db()

# Register modular Blueprints
app.register_blueprint(transactions_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(certifications_bp)
app.register_blueprint(reconciliation_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(api_sync_bp)
app.register_blueprint(audit_declarations_bp)

# Start background auto-sync daemon (automatically skipped under pytest)
from services.auto_sync_daemon import start_auto_sync_daemon
start_auto_sync_daemon()


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


# Global error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Recurso no encontrado", "code": 404}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Error interno del servidor", "code": 500}), 500


@app.errorhandler(Exception)
def unhandled_exception(e):
    logging.exception(e)
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return jsonify({"error": e.description, "code": e.code}), e.code
    return jsonify({"error": str(e), "type": type(e).__name__}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False, threaded=True)
