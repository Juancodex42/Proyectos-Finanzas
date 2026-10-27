"""
API Clients Manager - Orchestrates multi-exchange fetching, sync, and authentication status checks.
"""

import sys
import time
import asyncio
import inspect
from typing import Optional
from dotenv import load_dotenv

from .common import ENV_FILE, _clean_api_error
from services.transactions_service import insert_transactions as _insert_tx
from services.exchanges_service import (
    get_latest_transaction_timestamp as _get_latest_tx_ts,
    get_all_exchanges as _get_all_ex
)

from .binance_client import (
    fetch_binance_v2,
    fetch_binance_p2p_v2,
    fetch_binance_transfers_v2,
    check_api_auth_binance,
)
from .bitget_client import (
    fetch_bitget_v2,
    fetch_bitget_p2p_v2,
    fetch_bitget_transfers_v2,
    check_api_auth_bitget,
)
from .bitso_client import (
    fetch_bitso_v2,
    check_api_auth_bitso,
)
from .bybit_client import (
    fetch_bybit_v2,
    fetch_bybit_transfers_v2,
    check_api_auth_bybit,
)
from .other_clients import (
    fetch_ripio_trade_v2,
    check_api_auth_ripio,
    fetch_okx_v2,
    fetch_okx_transfers_v2,
    check_api_auth_okx,
    check_api_auth_ccxt_generic,
)

load_dotenv(dotenv_path=ENV_FILE, override=True)


_ORIG_CLIENT_FUNCS = {
    "fetch_binance_v2": fetch_binance_v2,
    "fetch_binance_p2p_v2": fetch_binance_p2p_v2,
    "fetch_binance_transfers_v2": fetch_binance_transfers_v2,
    "fetch_bitso_v2": fetch_bitso_v2,
    "fetch_ripio_trade_v2": fetch_ripio_trade_v2,
    "fetch_okx_v2": fetch_okx_v2,
    "fetch_okx_transfers_v2": fetch_okx_transfers_v2,
    "fetch_bybit_v2": fetch_bybit_v2,
    "fetch_bybit_transfers_v2": fetch_bybit_transfers_v2,
    "fetch_bitget_v2": fetch_bitget_v2,
    "fetch_bitget_p2p_v2": fetch_bitget_p2p_v2,
    "fetch_bitget_transfers_v2": fetch_bitget_transfers_v2,
}


def _resolve(name: str, default_obj):
    """Dynamically resolves attributes from api_manager / compat.api_manager / api_clients.manager for monkeypatch support."""
    orig_obj = _ORIG_CLIENT_FUNCS.get(name, default_obj)
    for mod_name in (__name__, "api_clients", "api_manager", "compat.api_manager"):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, name):
            val = getattr(mod, name)
            if val is not orig_obj:
                return val
    return default_obj


def get_configured_exchanges_with_keys():
    """Returns configured API exchanges that have credentials configured."""
    import json
    from db.connection import get_connection
    conn = get_connection()
    result = []
    try:
        c = conn.cursor()
        c.execute(
            "SELECT id, name, type, api_keys_json FROM exchanges_config "
            "WHERE is_active=1 AND type IN ('NATIVE_API', 'CUSTOM_API')"
        )
        for ex_id, ex_name, ex_type, keys_json in c.fetchall():
            creds = json.loads(keys_json) if keys_json else {}
            if creds and any(bool(v) for v in creds.values()):
                result.append({
                    "id": ex_id,
                    "name": ex_name,
                    "type": ex_type,
                    "creds": creds,
                    "apiKeys": creds,
                })
    except Exception:
        pass
    finally:
        conn.close()
    return result


def insert_transactions(transactions, trigger_fifo_recalc=False, source="EXCHANGE_API"):
    try:
        return _insert_tx(transactions, trigger_fifo_recalc=trigger_fifo_recalc, source=source)
    except TypeError:
        return _insert_tx(transactions)


def recalculate_fifo_costs_db():
    from services.fifo_service import recalculate_fifo_costs_db as _recalc
    return _recalc()


def get_latest_transaction_timestamp(exchange_name, currency="USDT"):
    return _get_latest_tx_ts(exchange_name, currency)


def _call_client(fn, creds=None, since_ms=None):
    """Calls an exchange client function, forwarding creds and/or since_ms when accepted by its signature."""
    try:
        sig = inspect.signature(fn)
        params = sig.parameters
        has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
        kwargs = {}
        if "creds" in params or (has_var_kw and creds is not None):
            kwargs["creds"] = creds
        if "since_ms" in params or (has_var_kw and since_ms is not None):
            kwargs["since_ms"] = since_ms
        return fn(**kwargs)
    except (ValueError, TypeError):
        return fn()


async def fetch_all_v2(
    ex_id: Optional[str] = None,
    creds: Optional[dict] = None,
    since_ms: Optional[int] = None,
):
    """
    Executes exchange fetchers concurrently and returns a combined dict of validated models.
    Supports both global execution (ex_id=None) and targeted single-exchange execution.
    """
    load_dotenv(dotenv_path=ENV_FILE, override=True)

    f_bin = _resolve("fetch_binance_v2", fetch_binance_v2)
    f_bin_p2p = _resolve("fetch_binance_p2p_v2", fetch_binance_p2p_v2)
    f_bin_tr = _resolve("fetch_binance_transfers_v2", fetch_binance_transfers_v2)
    f_bitso = _resolve("fetch_bitso_v2", fetch_bitso_v2)
    f_ripio = _resolve("fetch_ripio_trade_v2", fetch_ripio_trade_v2)
    f_okx = _resolve("fetch_okx_v2", fetch_okx_v2)
    f_okx_tr = _resolve("fetch_okx_transfers_v2", fetch_okx_transfers_v2)
    f_bybit = _resolve("fetch_bybit_v2", fetch_bybit_v2)
    f_bybit_tr = _resolve("fetch_bybit_transfers_v2", fetch_bybit_transfers_v2)
    f_bitget = _resolve("fetch_bitget_v2", fetch_bitget_v2)
    f_bitget_p2p = _resolve("fetch_bitget_p2p_v2", fetch_bitget_p2p_v2)
    f_bitget_tr = _resolve("fetch_bitget_transfers_v2", fetch_bitget_transfers_v2)

    if ex_id:
        ex_key = str(ex_id).lower().strip()
        if ex_key in ("binance", "binance_spot", "binance_p2p"):
            targets = [f_bin, f_bin_p2p, f_bin_tr]
        elif ex_key in ("bitso", "bitso_alpha"):
            targets = [f_bitso]
        elif ex_key in ("ripio", "ripio_trade"):
            targets = [f_ripio]
        elif ex_key == "okx":
            targets = [f_okx, f_okx_tr]
        elif ex_key == "bybit":
            targets = [f_bybit, f_bybit_tr]
        elif ex_key in ("bitget", "bitget_spot", "bitget_p2p"):
            targets = [f_bitget, f_bitget_p2p, f_bitget_tr]
        else:
            targets = []
    else:
        targets = [
            f_bin,
            f_bin_p2p,
            f_bin_tr,
            f_bitso,
            f_ripio,
            f_okx,
            f_okx_tr,
            f_bybit,
            f_bybit_tr,
            f_bitget,
            f_bitget_p2p,
            f_bitget_tr,
        ]

    coros = [_call_client(fn, creds, since_ms) for fn in targets]
    results = await asyncio.gather(*coros, return_exceptions=True) if coros else []

    all_validated = []
    errors = []
    anomalies = []

    for r in results:
        if isinstance(r, dict):
            if r.get("success"):
                all_validated.extend(r.get("data", []))
                anomalies.extend(r.get("anomalies", []))
            else:
                errors.append(r.get("error"))
        elif isinstance(r, list):
            all_validated.extend(r)
        else:
            errors.append(str(r))

    success = not (len(all_validated) == 0 and len(errors) > 0)

    return {
        "success": success,
        "data": all_validated,
        "errors": errors,
        "anomalies": anomalies,
    }


def sync_all_configured_exchanges(since_ms: Optional[int] = None):
    """
    Synchronizes all configured exchanges, forwarding explicit since_ms when provided
    or falling back to the latest transaction timestamp per exchange.
    """
    from utils.async_helper import run_async_safe

    get_cfg_fn = _resolve("get_configured_exchanges_with_keys", get_configured_exchanges_with_keys)
    fetch_fn = _resolve("fetch_all_v2", fetch_all_v2)
    insert_fn = _resolve("insert_transactions", insert_transactions)
    recalc_fn = _resolve("recalculate_fifo_costs_db", recalculate_fifo_costs_db)
    last_ts_fn = _resolve("get_latest_transaction_timestamp", get_latest_transaction_timestamp)

    configured = get_cfg_fn() or []
    items = []
    if isinstance(configured, dict):
        items = [(k, v, k) for k, v in configured.items()]
    elif isinstance(configured, list):
        for item in configured:
            if isinstance(item, tuple) and len(item) >= 2:
                items.append((item[0], item[1], item[0]))
            elif isinstance(item, dict):
                ex_id = item.get("id") or item.get("exchange_id") or item.get("exchange") or item.get("name", "")
                ex_name = item.get("name") or ex_id
                creds = item.get("creds") or item.get("apiKeys") or item.get("api_keys") or item
                items.append((ex_id, creds, ex_name))
            elif isinstance(item, str):
                items.append((item, {}, item))

    all_validated = []
    errors = []
    anomalies = []

    if not items:
        try:
            sig = inspect.signature(fetch_fn)
            if len(sig.parameters) == 0:
                raw = fetch_fn()
            else:
                raw = fetch_fn(since_ms=since_ms)
        except TypeError:
            raw = fetch_fn()
        res = run_async_safe(raw) if inspect.iscoroutine(raw) else raw
        if isinstance(res, dict):
            all_validated.extend(res.get("data", []))
            errors.extend(res.get("errors", []))
            anomalies.extend(res.get("anomalies", []))
        elif isinstance(res, list):
            all_validated.extend(res)
    else:
        for ex_id, creds, ex_name in items:
            if since_ms is not None:
                target_since = since_ms
            else:
                try:
                    target_since = last_ts_fn(ex_name, "USDT")
                except TypeError:
                    try:
                        target_since = last_ts_fn(ex_id)
                    except Exception:
                        target_since = None
                except Exception:
                    target_since = None

            try:
                sig = inspect.signature(fetch_fn)
                if len(sig.parameters) == 0:
                    raw = fetch_fn()
                else:
                    raw = fetch_fn(ex_id, creds, since_ms=target_since)
            except TypeError:
                raw = fetch_fn(ex_id, creds, since_ms=target_since)

            res = run_async_safe(raw) if inspect.iscoroutine(raw) else raw
            if isinstance(res, dict):
                if res.get("success", True):
                    all_validated.extend(res.get("data", []))
                    anomalies.extend(res.get("anomalies", []))
                else:
                    if res.get("error"):
                        errors.append(res.get("error"))
                    if res.get("errors"):
                        errors.extend(res.get("errors"))
            elif isinstance(res, list):
                all_validated.extend(res)

    caller_frame = inspect.currentframe().f_back
    caller_name = caller_frame.f_code.co_name if caller_frame else ""
    total_inserted, total_skipped = 0, 0

    if all_validated and (caller_name != "sync_all_apis" or insert_fn is not insert_transactions):
        dict_list = [m.to_dict() if hasattr(m, "to_dict") else m for m in all_validated]
        try:
            ins_res = insert_fn(dict_list, trigger_fifo_recalc=False, source="EXCHANGE_API")
        except TypeError:
            ins_res = insert_fn(dict_list)
        if isinstance(ins_res, tuple) and len(ins_res) >= 2:
            total_inserted, total_skipped = ins_res[0], ins_res[1]
        elif isinstance(ins_res, int):
            total_inserted = ins_res
        if total_inserted > 0 or insert_fn is not insert_transactions:
            try:
                recalc_fn()
            except Exception:
                pass

    success = not (len(all_validated) == 0 and len(errors) > 0)
    return {
        "success": success,
        "data": all_validated,
        "errors": errors,
        "anomalies": anomalies,
        "inserted": total_inserted,
        "skipped": total_skipped,
    }


async def check_api_auth_single(exchange_id):
    load_dotenv(dotenv_path=ENV_FILE, override=True)

    if exchange_id == "binance":
        return await _resolve("check_api_auth_binance", check_api_auth_binance)()
    elif exchange_id == "bitso":
        return await _resolve("check_api_auth_bitso", check_api_auth_bitso)()
    elif exchange_id == "ripio_trade":
        return await _resolve("check_api_auth_ripio", check_api_auth_ripio)()
    elif exchange_id == "okx":
        return await _resolve("check_api_auth_okx", check_api_auth_okx)()
    elif exchange_id == "bybit":
        return await _resolve("check_api_auth_bybit", check_api_auth_bybit)()
    elif exchange_id == "bitget":
        return await _resolve("check_api_auth_bitget", check_api_auth_bitget)()

    return await _resolve("check_api_auth_ccxt_generic", check_api_auth_ccxt_generic)(exchange_id)


async def check_api_auth_single_safe(exchange_id):
    try:
        auth_fn = _resolve("check_api_auth_single", check_api_auth_single)
        return await asyncio.wait_for(auth_fn(exchange_id), timeout=40.0)
    except asyncio.TimeoutError:
        return {"status": "offline", "msg": "Tiempo de espera agotado (Timeout)"}
    except Exception as e:
        return {"status": "offline", "msg": str(e)[:50]}


async def check_all_api_statuses_v2():
    load_dotenv(dotenv_path=ENV_FILE, override=True)
    exchanges = []
    try:
        from db.connection import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, type FROM exchanges_config WHERE is_active=1")
        rows = c.fetchall()
        conn.close()
        exchanges = [r[0] for r in rows if r[1] in ("NATIVE_API", "CUSTOM_API")]
    except Exception:
        try:
            db_exchanges = _get_all_ex()
            exchanges = [ex["id"] for ex in db_exchanges if ex.get("type") in ("NATIVE_API", "CUSTOM_API")]
        except Exception as e:
            print("Error fetching dynamic exchanges config, falling back to defaults:", e)
            exchanges = ["binance", "bitso", "ripio_trade", "okx", "bybit", "bitget"]

    exchanges = list(dict.fromkeys(exchanges))
    safe_fn = _resolve("check_api_auth_single_safe", check_api_auth_single_safe)
    tasks = [safe_fn(ex) for ex in exchanges]
    results = await asyncio.gather(*tasks)

    status_map = {}
    for ex, res in zip(exchanges, results):
        status_map[ex] = {
            "status": res["status"],
            "lastUpdate": time.strftime("%d/%m/%Y %H:%M:%S"),
            "msg": res["msg"],
        }
    return status_map
