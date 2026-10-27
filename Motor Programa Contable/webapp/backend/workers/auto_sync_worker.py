import os
import sys
import time
import asyncio
import psutil
from datetime import datetime

# Path adjustment for backend imports
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPAT_DIR = os.path.join(BACKEND_DIR, 'compat')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if COMPAT_DIR not in sys.path:
    sys.path.insert(0, COMPAT_DIR)

import db_manager
import api_manager

_DEFAULT_LOCK_FILE = os.path.join(BACKEND_DIR, 'uploads', '.auto_sync.lock')
_LOCK_FILE = _DEFAULT_LOCK_FILE
LOCK_FILE = _DEFAULT_LOCK_FILE


def _is_lock_active(lock_path: str) -> bool:
    if not os.path.exists(lock_path):
        return False
    try:
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


async def run_silent_background_sync():
    lock_path = LOCK_FILE if LOCK_FILE != _DEFAULT_LOCK_FILE else _LOCK_FILE
    try:
        if _is_lock_active(lock_path):
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Omitiendo sincronización: lockfile activo en uploads/.auto_sync.lock")
            return
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with open(lock_path, "w", encoding="utf-8") as lf:
            lf.write(str(os.getpid()))
    except Exception as e_lock:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Aviso lockfile: {e_lock}")
        return

    start_time = time.time()
    try:
        db_manager.init_db()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando Sincronización Automática Silenciosa...")

        # Run concurrent exchange fetching
        result = await api_manager.fetch_all_v2()

        models = result.get("data", [])
        dict_list = [m.to_dict() if hasattr(m, "to_dict") else m for m in models]

        inserted, skipped = 0, 0
        if dict_list:
            try:
                inserted, skipped = db_manager.insert_transactions(dict_list, source="EXCHANGE_API", trigger_fifo_recalc=False)
            except TypeError:
                inserted, skipped = db_manager.insert_transactions(dict_list)
            if inserted > 0:
                db_manager.deduplicate_existing_database()
                from services.fifo_service import recalculate_fifo_costs_db
                recalc_fn = getattr(db_manager, "recalculate_fifo_costs_db", recalculate_fifo_costs_db)
                recalc_fn()

        elapsed = time.time() - start_time
        process = psutil.Process(os.getpid())
        ram_usage_mb = process.memory_info().rss / (1024 * 1024)

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sincronización finalizada exitosamente.")
        print(f" -> Transacciones Nuevas Insertadas: {inserted}")
        print(f" -> Transacciones Omitidas (Duplicadas / En Períodos Certificados): {skipped}")
        print(f" -> Errores/Alertas de Llaves: {len(result.get('errors', []))}")
        print(f" -> Tiempo Total de Ejecución: {elapsed:.2f} segundos")
        print(f" -> Uso de Memoria RAM: {ram_usage_mb:.2f} MB")

        if result.get("errors"):
            print(" -> Detalle de Alertas:")
            for err in result.get("errors"):
                if err:
                    print(f"    ⚠️ {err}")

    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ERROR crítico en sincronización: {e}")
    finally:
        try:
            if os.path.exists(lock_path):
                with open(lock_path, "r", encoding="utf-8") as lf:
                    lock_pid = lf.read().strip()
                if lock_pid == str(os.getpid()):
                    os.remove(lock_path)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(run_silent_background_sync())
