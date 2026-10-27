import inspect
import sys
import threading
import time
from .async_helper import run_async_safe

time_module = time

STATUS_CACHE_TTL = 300
_STATUS_TTL = STATUS_CACHE_TTL

_status_cache = {
    'data': {},
    'timestamp': 0.0,
    'refreshing': False,
    'generation': 0,
    'last_attempt_ts': 0.0,
}
_status_cache_lock = threading.Lock()


def _refresh_worker():
    with _status_cache_lock:
        gen = _status_cache['generation']

    new_data = None
    succeeded = False
    try:
        mod_self = sys.modules.get(__name__)
        check_fn = getattr(mod_self, 'check_all_api_statuses_v2', None)
        if not check_fn:
            try:
                from api_clients import check_all_api_statuses_v2
                check_fn = check_all_api_statuses_v2
            except ImportError:
                import api_manager
                check_fn = api_manager.check_all_api_statuses_v2
        res_or_coro = check_fn()
        new_data = run_async_safe(res_or_coro) if inspect.iscoroutine(res_or_coro) else res_or_coro
        succeeded = True
    except Exception as e:
        print("Error refreshing status cache:", e)
    finally:
        now = time.time()
        with _status_cache_lock:
            if succeeded and _status_cache['generation'] == gen:
                _status_cache['data'] = new_data or {}
                _status_cache['timestamp'] = now
            _status_cache['last_attempt_ts'] = now
            _status_cache['refreshing'] = False


refresh_status_cache = _refresh_worker


def get_cached_api_statuses(force=False):
    if force:
        with _status_cache_lock:
            _status_cache['refreshing'] = True
        _refresh_worker()
        with _status_cache_lock:
            return dict(_status_cache['data']), False

    should_start_thread = False
    with _status_cache_lock:
        now = time.time()
        ts = _status_cache['timestamp']
        last_attempt = _status_cache['last_attempt_ts']
        cached = dict(_status_cache['data'])
        is_refreshing = _status_cache['refreshing']

        if cached:
            need_refresh = (now - ts) > STATUS_CACHE_TTL
        else:
            need_refresh = last_attempt == 0.0 or (now - last_attempt) > STATUS_CACHE_TTL

        if need_refresh and not is_refreshing:
            _status_cache['refreshing'] = True
            is_refreshing = True
            should_start_thread = True

    if should_start_thread:
        t = threading.Thread(target=_refresh_worker, daemon=True)
        t.start()

    return cached, is_refreshing


get_status_cache = get_cached_api_statuses


def invalidate_status_cache():
    with _status_cache_lock:
        _status_cache['generation'] += 1
        _status_cache['timestamp'] = 0.0
        _status_cache['last_attempt_ts'] = 0.0
        _status_cache['data'] = {}
        _status_cache['refreshing'] = False
