import os
import sys
import json
import time
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "auto_sync_state.json")
_DEFAULT_LOCK_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", ".auto_sync.lock")
_LOCK_FILE = _DEFAULT_LOCK_FILE
LOCK_FILE = _DEFAULT_LOCK_FILE
_lock = threading.Lock()
_daemon_thread = None
_state = {"enabled": True, "interval_seconds": 3600, "last_run": None, "last_inserted": 0, "last_skipped": 0}


def _load_persisted_state():
    try:
        if os.path.exists(_STATE_FILE):
            with open(_STATE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    _state.update(saved)
    except Exception as e:
        logger.warning(f"No se pudo leer estado de auto_sync_daemon: {e}")


def _save_persisted_state():
    try:
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(_state, f, indent=2)
    except Exception as e:
        logger.warning(f"No se pudo guardar estado de auto_sync_daemon: {e}")


_load_persisted_state()


def get_auto_sync_status() -> dict:
    with _lock:
        return {
            "exists": True,
            "enabled": bool(_state.get("enabled", True)),
            "interval_seconds": int(_state.get("interval_seconds", 3600)),
            "last_run": _state.get("last_run"),
            "last_inserted": _state.get("last_inserted", 0),
            "last_skipped": _state.get("last_skipped", 0),
            "running": bool(_daemon_thread and _daemon_thread.is_alive())
        }


def set_auto_sync_enabled(enabled: bool) -> dict:
    with _lock:
        _state["enabled"] = bool(enabled)
        _save_persisted_state()
    return get_auto_sync_status()


def _is_lock_active(lock_path: str) -> bool:
    if not os.path.exists(lock_path):
        return False
    try:
        import psutil
        with open(lock_path, "r", encoding="utf-8") as lf:
            pid_str = lf.read().strip()
        if pid_str.isdigit():
            pid = int(pid_str)
            if psutil.pid_exists(pid):
                return True
            else:
                try:
                    os.remove(lock_path)
                except Exception:
                    pass
                return False
        if (time.time() - os.path.getmtime(lock_path)) < 900:
            return True
    except Exception:
        return False
    return False


def _acquire_daemon_lock(lock_path: str = None) -> bool:
    target_lock = lock_path or (LOCK_FILE if LOCK_FILE != _DEFAULT_LOCK_FILE else _LOCK_FILE)
    try:
        if _is_lock_active(target_lock):
            return False
        if os.path.exists(target_lock):
            try:
                os.remove(target_lock)
            except OSError:
                pass
        os.makedirs(os.path.dirname(target_lock), exist_ok=True)
        fd = os.open(target_lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, str(os.getpid()).encode("utf-8"))
        finally:
            os.close(fd)
        return True
    except Exception as e_lock:
        logger.warning(f"No se pudo crear lockfile de auto_sync: {e_lock}")
        return False


def _run_sync_cycle():
    lock_path = LOCK_FILE if LOCK_FILE != _DEFAULT_LOCK_FILE else _LOCK_FILE
    if not _acquire_daemon_lock(lock_path):
        logger.info("Omitiendo ciclo de auto_sync_daemon: lockfile activo en uploads/.auto_sync.lock")
        return

    try:
        import db_manager
        import api_manager
        from async_helper import run_async_safe
        from services.cache_service import analytics_cache, invalidate_analytics_cache
        from services.fifo_service import recalculate_fifo_costs_db

        res = run_async_safe(api_manager.fetch_all_v2()) or {}
        models = res.get("data", [])
        inserted, skipped = 0, 0
        if models:
            dict_list = [m.to_dict() if hasattr(m, "to_dict") else m for m in models]
            if dict_list:
                try:
                    inserted, skipped = db_manager.insert_transactions(dict_list, trigger_fifo_recalc=False, source="EXCHANGE_API")
                except TypeError:
                    inserted, skipped = db_manager.insert_transactions(dict_list)
                if inserted > 0:
                    db_manager.deduplicate_existing_database()
                    recalc_fn = getattr(db_manager, "recalculate_fifo_costs_db", recalculate_fifo_costs_db)
                    recalc_fn()
                invalidate_analytics_cache()
                analytics_cache.clear()
        with _lock:
            _state["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _state["last_inserted"] = inserted
            _state["last_skipped"] = skipped
            _save_persisted_state()
    except Exception as e:
        logger.warning(f"Error en ciclo automático de sincronización: {e}")
    finally:
        try:
            if os.path.exists(lock_path):
                with open(lock_path, "r", encoding="utf-8") as lf:
                    lock_pid = lf.read().strip()
                if lock_pid == str(os.getpid()):
                    os.remove(lock_path)
        except Exception:
            pass


def _daemon_worker(interval_seconds: int):
    time.sleep(8)
    while True:
        if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
            break
        with _lock:
            is_enabled = bool(_state.get("enabled", True))
        if is_enabled:
            _run_sync_cycle()
        time.sleep(max(60, int(interval_seconds)))


def start_auto_sync_daemon(interval_seconds: int = None):
    global _daemon_thread
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    with _lock:
        if interval_seconds is not None:
            _state["interval_seconds"] = int(interval_seconds)
            _save_persisted_state()
        eff_interval = int(_state.get("interval_seconds", 3600))
        if _daemon_thread is not None and _daemon_thread.is_alive():
            return True
        _daemon_thread = threading.Thread(
            target=_daemon_worker,
            args=(eff_interval,),
            name="CryptoTaxAutoSyncDaemon",
            daemon=True
        )
        _daemon_thread.start()
        return True
