import json
import re
import time
import logging
from datetime import datetime
import pandas as pd
from db.connection import get_connection

logger = logging.getLogger(__name__)


def get_all_exchanges():
    """Retrieves all active configured exchanges from database."""
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT id, name, type, status, last_update, date_format, mapping_json, api_keys_json, is_active FROM exchanges_config WHERE is_active=1")
        rows = c.fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        raw_keys = json.loads(r[7]) if r[7] else {}
        masked_keys = {k: ("***" if v else "") for k, v in raw_keys.items()}
        result.append({
            "id": r[0],
            "name": r[1],
            "type": r[2],
            "status": r[3],
            "lastUpdate": r[4],
            "dateFormat": r[5],
            "mapping": json.loads(r[6]) if r[6] else {},
            "apiKeys": masked_keys,
            "hasApiKeys": bool(raw_keys and any(bool(v) for v in raw_keys.values())),
            "isActive": bool(r[8])
        })
    return result


def add_custom_exchange(name, date_format='%d/%m/%Y %H:%M:%S', mapping=None):
    """Registers a new custom CSV exchange profile."""
    if mapping is None:
        mapping = {}
    conn = get_connection()
    try:
        c = conn.cursor()
        ex_id = re.sub(r'[^a-z0-9_]', '', name.lower().replace(' ', '_'))
        if not ex_id:
            ex_id = f"custom_{int(time.time())}"
        c.execute('''
            INSERT OR REPLACE INTO exchanges_config (id, name, type, status, last_update, date_format, mapping_json, api_keys_json, is_active)
            VALUES (?, ?, 'CUSTOM_CSV', 'online', '-', ?, ?, '{}', 1)
        ''', (ex_id, name, date_format, json.dumps(mapping)))
        conn.commit()
    finally:
        conn.close()
    return {"id": ex_id, "name": name}


def update_exchange_mapping(ex_id, mapping, date_format='%d/%m/%Y %H:%M:%S'):
    """Updates CSV column mapping for an exchange."""
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute('''
            UPDATE exchanges_config 
            SET mapping_json = ?, date_format = ?
            WHERE id = ?
        ''', (json.dumps(mapping), date_format, ex_id))
        conn.commit()
    finally:
        conn.close()
    return True


def update_exchange_apikeys(ex_id, api_keys):
    """Updates exchange API credentials and syncs to environment configuration."""
    conn = get_connection()
    try:
        c = conn.cursor()
        if isinstance(api_keys, dict):
            c.execute("SELECT api_keys_json FROM exchanges_config WHERE id = ?", (ex_id,))
            row = c.fetchone()
            existing_keys = json.loads(row[0]) if row and row[0] else {}
            if not isinstance(existing_keys, dict):
                existing_keys = {}
            merged_keys = dict(existing_keys)
            prefix = ex_id.upper()
            for k, v in api_keys.items():
                is_masked = isinstance(v, str) and len(v.strip()) > 0 and set(v.strip()) == {'*'}
                if is_masked:
                    if k in existing_keys and existing_keys[k] and set(str(existing_keys[k]).strip()) != {'*'}:
                        merged_keys[k] = existing_keys[k]
                    else:
                        k_upper = str(k).upper()
                        env_var = None
                        if 'KEY' in k_upper or k_upper == 'APIKEY':
                            env_var = f"{prefix}_API_KEY"
                        elif 'SECRET' in k_upper or k_upper == 'APISECRET':
                            env_var = f"{prefix}_API_SECRET"
                        elif 'PASSPHRASE' in k_upper or 'PASSWORD' in k_upper:
                            env_var = f"{prefix}_API_PASSWORD"
                        if env_var and os.environ.get(env_var):
                            merged_keys[k] = os.environ[env_var]
                else:
                    merged_keys[k] = v
            api_keys = merged_keys
        c.execute('''
            UPDATE exchanges_config 
            SET api_keys_json = ?
            WHERE id = ?
        ''', (json.dumps(api_keys), ex_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating API keys in DB for {ex_id}: {e}", exc_info=True)
        return False
    finally:
        conn.close()

    try:
        try:
            from services.config_service import set_env_keys
        except ImportError:
            import config_manager
            set_env_keys = config_manager.set_env_keys

        env_dict = {}
        prefix = ex_id.upper()
        if isinstance(api_keys, dict):
            for k, v in api_keys.items():
                if isinstance(v, str) and len(v.strip()) > 0 and set(v.strip()) == {'*'}:
                    continue
                k_upper = str(k).upper()
                if 'KEY' in k_upper or k_upper == 'APIKEY':
                    env_dict[f"{prefix}_API_KEY"] = v
                elif 'SECRET' in k_upper or k_upper == 'APISECRET':
                    env_dict[f"{prefix}_API_SECRET"] = v
                elif 'PASSPHRASE' in k_upper or 'PASSWORD' in k_upper:
                    env_dict[f"{prefix}_API_PASSWORD"] = v
                else:
                    env_dict[k] = v
        if env_dict:
            set_env_keys(env_dict)
            from dotenv import load_dotenv
            load_dotenv(override=True)
    except Exception as e:
        logger.error(f"Error syncing API keys to .env for {ex_id}: {e}", exc_info=True)
        return False

    return True


def delete_exchange(ex_id):
    """Marks an exchange as inactive in database."""
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("UPDATE exchanges_config SET is_active = 0 WHERE id = ?", (ex_id,))
        conn.commit()
    finally:
        conn.close()
    return True


def get_latest_transaction_timestamp(exchange_name, currency, lookback_days: int = 0):
    """Returns the latest transaction timestamp in milliseconds for sync checkpoints."""
    conn = get_connection()
    row = None
    try:
        c = conn.cursor()
        exchanges = [exchange_name]
        if exchange_name == 'Bitso Alpha':
            exchanges.append('Bitso')
        elif exchange_name == 'Ripio Trade':
            exchanges.append('Ripio')
        placeholders = ','.join(['?'] * len(exchanges))
        c.execute(f"""
            SELECT MAX(fecha) FROM transactions 
            WHERE exchange IN ({placeholders})
              AND moneda = ?
              AND tipo_operacion IN ('Compra', 'Venta', 'Ingreso Cripto', 'Retiro Cripto', 'Depósito', 'Retiro')
              AND (comentarios IS NULL OR comentarios NOT LIKE '%P2P%')
        """, (*exchanges, currency))
        row = c.fetchone()
    finally:
        conn.close()

    if row and row[0]:
        try:
            from datetime import timezone, timedelta
            dt = pd.to_datetime(row[0], errors='coerce')
            if pd.isna(dt):
                return None
            is_arg_exchange = any(k in str(exchange_name).lower() for k in ('bitso', 'ripio', 'fiwind', 'lemon', 'belo', 'buenbit'))
            if dt.tzinfo is None:
                s_val = str(row[0])
                if is_arg_exchange and 'Z' not in s_val and '+' not in s_val and 'UTC' not in s_val:
                    dt = dt.tz_localize(timezone(timedelta(hours=-3))).tz_convert(timezone.utc)
                else:
                    dt = dt.tz_localize(timezone.utc)
            else:
                dt = dt.tz_convert(timezone.utc)
            ts_ms = int(dt.timestamp() * 1000)
            return max(0, ts_ms - max(0, int(lookback_days)) * 86400 * 1000)
        except Exception:
            return None
    return None


def get_exchange_last_tx_date(exchange_name):
    """Returns the maximum transaction date string for an exchange, formatted as DD/MM/YYYY HH:MM:SS or '-'."""
    conn = get_connection()
    row = None
    try:
        c = conn.cursor()
        c.execute("SELECT MAX(fecha) FROM transactions WHERE exchange = ?", (exchange_name,))
        row = c.fetchone()
    finally:
        conn.close()
    if row and row[0]:
        val = str(row[0])
        try:
            parts = val.split(' ')
            d_parts = parts[0].split('-')
            if len(d_parts) == 3:
                formatted_date = f"{d_parts[2]}/{d_parts[1]}/{d_parts[0]}"
                if len(parts) > 1:
                    t_str = parts[1].strip()
                    if len(t_str) == 5:
                        t_str += ":00"
                    formatted_date += f" {t_str[:8]}"
                return formatted_date
        except Exception:
            return val
    return '-'
