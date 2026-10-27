"""
cache_service.py - In-Memory Analytics & Calculation Cache Layer.
Provides high-performance, thread-safe caching for computationally intensive
analytical aggregations (full audit, gap analysis, dashboard metrics).
Automatically invalidated when transactions, certifications, or tax settings mutate.
"""

import threading
from typing import Any, Callable, Optional


class AnalyticsCache:
    """Thread-safe in-memory cache for analytical and reconciliation calculations."""

    def __init__(self, default_ttl: Optional[float] = None):
        self._lock = threading.Lock()
        self._cache = {}
        self._generation = 0
        self.default_ttl = default_ttl

    def get_generation(self) -> int:
        with self._lock:
            return self._generation

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: Any, ttl: Optional[float] = None, expected_gen: Optional[int] = None) -> None:
        with self._lock:
            if expected_gen is not None and expected_gen != self._generation:
                return
            self._cache[key] = value

    def invalidate(self) -> None:
        with self._lock:
            self._generation += 1
            self._cache.clear()

    def clear(self) -> None:
        self.invalidate()

    def get_or_compute(self, key: str, compute_fn: Callable[..., Any], *args, **kwargs) -> Any:
        with self._lock:
            if key in self._cache:
                return self._cache[key]
            gen = self._generation

        # Compute outside lock to avoid blocking readers of other keys
        result = compute_fn(*args, **kwargs)

        with self._lock:
            if self._generation == gen:
                self._cache[key] = result
        return result


TTLCache = AnalyticsCache

# Global singleton cache instance
analytics_cache = AnalyticsCache()


def invalidate_analytics_cache():
    """Invalidates the entire analytics cache when database mutations occur."""
    analytics_cache.invalidate()


invalidate_Dashboard_Cache = invalidate_analytics_cache
