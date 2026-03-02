"""JSON file cache with TTL support."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

from config import settings
from utils.logger import get_logger
from utils.paths import DIR_CACHE, ensure_dirs, p

logger = get_logger(__name__)


class CacheManager:
    """Simple TTL cache persisted as JSON files."""

    def __init__(self, cache_dir: str = DIR_CACHE, ttl_hours: int = settings.CACHE_DURATION_HOURS) -> None:
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_hours * 3600
        ensure_dirs([cache_dir])

    def _cache_path(self, key: str) -> str:
        safe_key = "".join(char if char.isalnum() or char in "-_" else "_" for char in key)
        return p("cache", f"{safe_key}.json")

    def get(self, key: str, max_age_seconds: int | None = None) -> Any | None:
        """Read cache value if not expired."""
        if not settings.ENABLE_CONTENT_CACHE:
            return None

        file_path = self._cache_path(key)
        if not os.path.exists(file_path):
            return None

        age = time.time() - os.path.getmtime(file_path)
        limit = max_age_seconds if max_age_seconds is not None else self.ttl_seconds
        if age > limit:
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload.get("data")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Cache read failed for key=%s: %s", key, exc)
            return None

    def set(self, key: str, data: Any) -> None:
        """Persist cache value."""
        if not settings.ENABLE_CONTENT_CACHE:
            return
        file_path = self._cache_path(key)
        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump({"saved_at": int(time.time()), "data": data}, handle, ensure_ascii=False, indent=2)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Cache write failed for key=%s: %s", key, exc)


def get_cached_or_compute(key: str, producer: Callable[[], Any], max_age_seconds: int | None = None) -> Any:
    """Get value from cache or compute/store it."""
    cache = CacheManager()
    cached = cache.get(key=key, max_age_seconds=max_age_seconds)
    if cached is not None:
        return cached
    value = producer()
    cache.set(key=key, data=value)
    return value
