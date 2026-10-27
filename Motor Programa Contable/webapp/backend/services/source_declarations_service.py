"""
Service to manage user declarations and exemptions for exchange sources that have
no operations, are closed, or should be excluded from stale-data warning alerts.
Persisted in the operational_settings table in SQLite.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from db.connection import get_connection
from models.transaction_models import get_canonical_exchange_root
from services.cache_service import invalidate_analytics_cache

logger = logging.getLogger(__name__)

SETTINGS_KEY = 'source_audit_declarations'

DEFAULT_CLOSED_EXCHANGES = {
    "LOCALBITCOINS": {
        "status": "CLOSED",
        "reason": "Plataforma cerrada permanentemente (febrero 2023)",
        "effective_date": "2023-02-12",
        "declared_at": "2023-02-12 00:00:00",
        "auto_exempted": True
    },
    "PAXFUL": {
        "status": "CLOSED",
        "reason": "Plataforma cerrada / operaciones suspendidas (abril 2023)",
        "effective_date": "2023-04-01",
        "declared_at": "2023-04-01 00:00:00",
        "auto_exempted": True
    }
}


def _ensure_settings_table(conn) -> None:
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS operational_settings (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def get_source_declarations() -> Dict[str, dict]:
    """
    Returns all active source declarations indexed by canonical exchange root.
    Seeds default closed platforms (LocalBitcoins, Paxful) if not present.
    """
    conn = get_connection()
    try:
        _ensure_settings_table(conn)
        c = conn.cursor()
        c.execute("SELECT value_json FROM operational_settings WHERE key = ?", (SETTINGS_KEY,))
        row = c.fetchone()
        if not row or not row[0]:
            # Seed defaults
            merged = dict(DEFAULT_CLOSED_EXCHANGES)
            c.execute(
                "INSERT OR REPLACE INTO operational_settings (key, value_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (SETTINGS_KEY, json.dumps(merged))
            )
            conn.commit()
            return merged

        saved = json.loads(row[0]) if row[0] else {}
        # Ensure default closed platforms are included unless explicitly revoked
        changed = False
        for k, v in DEFAULT_CLOSED_EXCHANGES.items():
            if k not in saved:
                saved[k] = v
                changed = True
        if changed:
            c.execute(
                "UPDATE operational_settings SET value_json = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ?",
                (json.dumps(saved), SETTINGS_KEY)
            )
            conn.commit()
        return saved
    except Exception as e:
        logger.error(f"Error fetching source declarations: {e}")
        return dict(DEFAULT_CLOSED_EXCHANGES)
    finally:
        conn.close()


def set_source_declaration(exchange_root: str, status: str = "NO_OPERATIONS", reason: str = "", effective_date: Optional[str] = None) -> dict:
    """
    Records or updates a user declaration that an exchange has no operations or is closed.
    """
    canon = get_canonical_exchange_root(exchange_root).upper()
    current = get_source_declarations()

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry = {
        "status": str(status).upper(),
        "reason": reason or ("Plataforma cerrada" if status.upper() == 'CLOSED' else "Declarado sin operaciones posteriores"),
        "effective_date": effective_date or now_str[:10],
        "declared_at": now_str,
        "auto_exempted": False,
        "revoked": False
    }

    current[canon] = entry

    conn = get_connection()
    try:
        _ensure_settings_table(conn)
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO operational_settings (key, value_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (SETTINGS_KEY, json.dumps(current))
        )
        conn.commit()
    finally:
        conn.close()

    invalidate_analytics_cache()
    return entry


def revoke_source_declaration(exchange_root: str) -> bool:
    """
    Revokes/retracts a declaration for an exchange, re-enabling continuous freshness audit.
    """
    canon = get_canonical_exchange_root(exchange_root).upper()
    current = get_source_declarations()

    if canon in current:
        if canon in DEFAULT_CLOSED_EXCHANGES:
            # Mark as revoked so it isn't automatically re-seeded
            current[canon]["revoked"] = True
        else:
            del current[canon]

        conn = get_connection()
        try:
            _ensure_settings_table(conn)
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO operational_settings (key, value_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (SETTINGS_KEY, json.dumps(current))
            )
            conn.commit()
        finally:
            conn.close()

        invalidate_analytics_cache()
        return True

    return False


def is_source_exempted(exchange_root: str) -> bool:
    """
    Returns True if the given exchange is currently declared as exempt/closed.
    """
    canon = get_canonical_exchange_root(exchange_root).upper()
    declarations = get_source_declarations()
    if canon in declarations:
        decl = declarations[canon]
        return not bool(decl.get("revoked", False))
    return False
