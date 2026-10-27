"""
Service to evaluate source freshness, detect stale exchanges, resolve API connections,
and generate accurate audit alerts distinguishing API sources from manual CSV statements.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
import pandas as pd
from dotenv import load_dotenv

from utils.status_cache import get_status_cache

ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=ENV_FILE, override=True)

# Map canonical exchange root to API client identifier
API_ROOT_MAP = {
    'BINANCE': 'binance',
    'BITSO': 'bitso',
    'RIPIO': 'ripio_trade',
    'OKX': 'okx',
    'BYBIT': 'bybit',
    'BITGET': 'bitget',
}


def resolve_exchange_api_info(ex_root: str) -> dict:
    """
    Determines whether an exchange root is supported via API, whether it has
    active credentials configured (.env or database), and its current cached status.
    """
    load_dotenv(dotenv_path=ENV_FILE, override=True)
    canon = str(ex_root).strip().upper()
    api_id = API_ROOT_MAP.get(canon)

    # Check if a custom API is registered in exchanges_config
    if not api_id:
        try:
            from db.connection import get_connection
            conn = get_connection()
            c = conn.cursor()
            c.execute(
                "SELECT id FROM exchanges_config WHERE is_active=1 AND type='CUSTOM_API' AND UPPER(name)=?",
                (canon,)
            )
            row = c.fetchone()
            if row:
                api_id = row[0]
            conn.close()
        except Exception:
            pass

    if not api_id:
        return {
            "is_api": False,
            "api_id": None,
            "has_credentials": False,
            "status": "csv",
            "msg": "CSV / Manual"
        }

    # Verify credentials in .env
    key_env = f"{canon}_API_KEY"
    has_creds = bool(os.getenv(key_env) or (canon == 'RIPIO' and os.getenv("RIPIO_API_KEY")))

    # Verify credentials in database exchanges_config if not in .env
    if not has_creds:
        try:
            from db.connection import get_connection
            import json
            conn = get_connection()
            c = conn.cursor()
            c.execute(
                "SELECT api_keys_json FROM exchanges_config WHERE id=? OR UPPER(name)=?",
                (api_id, canon)
            )
            row = c.fetchone()
            if row and row[0]:
                keys_dict = json.loads(row[0])
                has_creds = any(bool(v) for v in keys_dict.values())
            conn.close()
        except Exception:
            pass

    # Status check from status_cache
    cached, _ = get_status_cache(force=False)
    cached_info = cached.get(api_id) or {}
    api_status = cached_info.get("status")
    api_msg = cached_info.get("msg", "")

    if not api_status:
        api_status = "online" if has_creds else "unconfigured"
        api_msg = "API conectada" if has_creds else "Sin credenciales"

    return {
        "is_api": True,
        "api_id": api_id,
        "has_credentials": has_creds,
        "status": api_status,
        "msg": api_msg
    }


def format_stale_source_alert(ex_root: str, f_info: dict, api_info: dict) -> dict:
    """
    Builds a structured audit alert for an exchange behind schedule, adapting
    instructions depending on whether the source uses an automated API or manual statements.
    """
    last_tx_date = f_info["last_tx_date"]
    days_behind = f_info["days_behind_latest"]
    latest_system_date = f_info["latest_system_date"]

    is_api = api_info["is_api"]
    api_id = api_info["api_id"]
    api_status = api_info["status"]
    api_msg = api_info["msg"]

    if is_api and api_info["has_credentials"]:
        if api_status == "expired":
            severity = "ALTA"
            err_detail = f" ({api_msg})" if api_msg else ""
            message = (
                f"API de {ex_root} desincronizada: las credenciales API expiraron{err_detail}. "
                f"Actualizá tu API Key en la sección APIs o sincronizá manualmente para traer operaciones recientes."
            )
        elif api_status in ("offline", "error"):
            severity = "ALTA"
            err_detail = f" ({api_msg})" if api_msg else ""
            message = (
                f"API de {ex_root} sin conexión{err_detail}. "
                f"Verificá tus credenciales en APIs o reintentá la sincronización."
            )
        else:
            # Online or configured without known error
            severity = "MEDIA" if days_behind > 60 else "BAJA"
            message = (
                f"Fuente API de {ex_root} conectada ({api_msg or 'online'}): última operación registrada el {last_tx_date} "
                f"({days_behind} días sin nuevos movimientos). Podés sincronizar la API para verificar órdenes recientes, o declararla al día si ya no operás allí."
            )
    elif is_api and not api_info["has_credentials"]:
        severity = "MEDIA"
        message = (
            f"Fuente {ex_root} sin API configurada: última operación registrada el {last_tx_date} "
            f"({days_behind} días por detrás). Podés conectar su API o importar extractos."
        )
    else:
        # Native CSV or manual statements
        severity = "ALTA" if days_behind > 60 else "MEDIA"
        message = (
            f"Extracto desactualizado en {ex_root}: última operación registrada el {last_tx_date} "
            f"({days_behind} días por detrás de la actividad más reciente al {latest_system_date}). "
            f"Cargá un extracto reciente si operaste en este período, o declaralo al día."
        )

    return {
        "type": "stale_source",
        "exchange": ex_root,
        "days_behind": days_behind,
        "last_date": last_tx_date,
        "severity": severity,
        "is_api": is_api,
        "api_id": api_id,
        "api_status": api_status,
        "api_msg": api_msg,
        "source_type": "API" if (is_api and api_info["has_credentials"]) else "CSV",
        "message": message
    }


def evaluate_source_freshness_and_alerts(
    all_tx_df: pd.DataFrame,
    today: datetime,
    active_declarations: Dict[str, dict]
) -> Tuple[Dict[str, dict], List[dict], List[dict]]:
    """
    Computes freshness per exchange root, filters declared sources,
    and returns (freshness_dict, source_alerts, declared_sources).
    """
    freshness = {}
    valid_dates_all = all_tx_df.loc[all_tx_df['fecha_dt'] <= (today + timedelta(days=1)), 'fecha_dt'].dropna()
    latest_system_date = valid_dates_all.max() if not valid_dates_all.empty else today
    if latest_system_date > today:
        latest_system_date = today

    for ex_root, group in all_tx_df.groupby('exchange_root'):
        valid_dates = group.loc[group['fecha_dt'] <= (today + timedelta(days=1)), 'fecha_dt'].dropna()
        if valid_dates.empty:
            valid_dates = group['fecha_dt'].dropna()
        if not valid_dates.empty:
            last_date = valid_dates.max()
            days_ago = max(0, (today - last_date).days)
            days_behind_latest = max(0, (latest_system_date - last_date).days)
            is_stale = (days_ago > 30) or (days_behind_latest > 30)
            freshness[ex_root] = {
                "exchange": ex_root,
                "last_tx_date": str(last_date.date()),
                "days_ago": days_ago,
                "days_behind_latest": days_behind_latest,
                "stale": bool(is_stale),
                "latest_system_date": str(latest_system_date.date())
            }

    source_alerts = []
    declared_sources = []

    for ex_root, f_info in freshness.items():
        if ex_root in active_declarations:
            decl = active_declarations[ex_root]
            if not decl.get("revoked", False):
                declared_sources.append({
                    "exchange": ex_root,
                    "last_date": f_info["last_tx_date"],
                    "days_behind": f_info["days_behind_latest"],
                    "status": decl.get("status", "NO_OPERATIONS"),
                    "reason": decl.get("reason", "Sin operaciones posteriores"),
                    "declared_at": decl.get("declared_at", ""),
                    "auto_exempted": decl.get("auto_exempted", False)
                })
                continue

        if f_info["days_behind_latest"] >= 30:
            api_info = resolve_exchange_api_info(ex_root)
            # If the exchange connects via API, has valid credentials and is online:
            # It has no missing manual statements. Inactivity simply means no new trades were made.
            if api_info["is_api"] and api_info["has_credentials"] and api_info["status"] == "online":
                declared_sources.append({
                    "exchange": ex_root,
                    "last_date": f_info["last_tx_date"],
                    "days_behind": f_info["days_behind_latest"],
                    "status": "API_ONLINE",
                    "reason": "API conectada y al día (sin operaciones recientes)",
                    "declared_at": str(today.date()),
                    "auto_exempted": True
                })
                continue

            alert = format_stale_source_alert(ex_root, f_info, api_info)
            source_alerts.append(alert)

    return freshness, source_alerts, declared_sources
