"""Backward compatibility facade for utils.status_cache."""
from utils.status_cache import (
    get_status_cache,
    refresh_status_cache,
    invalidate_status_cache,
)

__all__ = [
    "get_status_cache",
    "refresh_status_cache",
    "invalidate_status_cache",
]
