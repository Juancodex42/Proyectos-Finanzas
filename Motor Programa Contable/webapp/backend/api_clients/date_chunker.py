"""
Módulo de particionamiento temporal para APIs de exchanges.
Divide rangos de fechas en sub-ventanas respetando los límites de cada exchange.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Optional


def generate_time_windows(
    start_dt: datetime,
    end_dt: Optional[datetime] = None,
    chunk_days: int = 60
) -> List[Tuple[int, int]]:
    """
    Genera una lista de tuplas (start_ms, end_ms) desde start_dt hasta end_dt
    en pasos de hasta chunk_days días.
    Garantiza timestamps en milisegundos y zonas horarias UTC consistentes.
    """
    if end_dt is None:
        end_dt = datetime.now(timezone.utc)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    if start_dt >= end_dt:
        return []

    windows = []
    current_start = start_dt
    delta = timedelta(days=chunk_days)

    while current_start < end_dt:
        current_end = min(current_start + delta, end_dt)
        windows.append((
            int(current_start.timestamp() * 1000),
            int(current_end.timestamp() * 1000)
        ))
        current_start = current_end

    return windows
