"""
Blueprint for user audit declarations on exchange freshness (declaring no operations,
closed platforms, and revoking exemptions).
"""

from flask import Blueprint, request, jsonify
from services.source_declarations_service import (
    get_source_declarations,
    set_source_declaration,
    revoke_source_declaration,
)

audit_declarations_bp = Blueprint('audit_declarations_bp', __name__)


@audit_declarations_bp.route('/api/audit/declarations', methods=['GET'])
@audit_declarations_bp.route('/audit/declarations', methods=['GET'])
def list_declarations():
    """Lists all current source audit declarations."""
    try:
        declarations = get_source_declarations()
        return jsonify({
            "status": "success",
            "success": True,
            "declarations": declarations
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@audit_declarations_bp.route('/api/audit/declarations', methods=['POST'])
@audit_declarations_bp.route('/audit/declarations', methods=['POST'])
def declare_source():
    """Declares an exchange as having no operations or being closed."""
    data = request.get_json(silent=True) or {}
    exchanges = data.get('exchanges')
    exchange = data.get('exchange')
    if not exchange and not exchanges:
        return jsonify({"status": "error", "error": "El campo 'exchange' o 'exchanges' es requerido."}), 400

    status = data.get('status', 'NO_OPERATIONS')
    reason = data.get('reason', '')
    effective_date = data.get('effective_date')

    target_list = exchanges if isinstance(exchanges, list) else [exchange]
    entries = []
    try:
        for ex in target_list:
            if not ex:
                continue
            e = set_source_declaration(
                exchange_root=ex,
                status=status,
                reason=reason,
                effective_date=effective_date
            )
            entries.append(e)

        return jsonify({
            "status": "success",
            "success": True,
            "exchange": exchange or (target_list[0] if target_list else None),
            "declaration": entries[0] if entries else None,
            "declarations": entries
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@audit_declarations_bp.route('/api/audit/declarations/<exchange>', methods=['DELETE'])
@audit_declarations_bp.route('/audit/declarations/<exchange>', methods=['DELETE'])
def revoke_declaration(exchange):
    """Revokes a declaration, returning the exchange to normal freshness audit."""
    if not exchange:
        return jsonify({"status": "error", "error": "Exchange es requerido."}), 400

    try:
        revoked = revoke_source_declaration(exchange)
        return jsonify({
            "status": "success",
            "success": True,
            "exchange": exchange,
            "revoked": revoked
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
