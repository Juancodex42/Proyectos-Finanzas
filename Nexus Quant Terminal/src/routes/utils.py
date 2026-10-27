"""Fachada de compatibilidad para utilidades de rutas HTTP/SSE.
Re-exporta el contexto de ejecución desde engine.services.runtime_context sin ciclos de dependencia.
Referencia de diseño: docs/ARQUITECTURA.md"""

from engine.services.runtime_context import (
    INTERVAL_ORDER,
    MAX_DATA_CACHE_SIZE,
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
    resolve_csv_filepath,
    simulator,
    sort_intervals,
    sse_response,
    stats_engine,
)

__all__ = [
    "simulator",
    "stats_engine",
    "optimizer",
    "INTERVAL_ORDER",
    "MAX_DATA_CACHE_SIZE",
    "_data_cache",
    "_cache_lock",
    "get_data_dir",
    "extract_markov_params",
    "is_safe_symbol",
    "is_safe_interval",
    "clean_json_data",
    "preserve_peaks_subsample",
    "get_genetic_optimizer_path",
    "extract_json_from_output",
    "sse_response",
    "sort_intervals",
    "fetch_and_save_binance_klines",
    "load_csv_data",
]
