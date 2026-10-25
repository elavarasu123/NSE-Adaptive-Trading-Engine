from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict


@dataclass
class CacheItem:
    value: Any
    expires_at: datetime


class TTLCache:
    def __init__(self):
        self._items: Dict[str, CacheItem] = {}
        self._lock = Lock()

    def get(self, key):
        now = datetime.now(timezone.utc)

        with self._lock:
            item = self._items.get(key)

            if not item:
                return None

            if item.expires_at <= now:
                self._items.pop(key, None)
                return None

            return item.value

    def set(self, key, value, ttl_seconds):
        expires = (
            datetime.now(timezone.utc)
            + timedelta(seconds=ttl_seconds)
        )

        with self._lock:
            self._items[key] = CacheItem(
                value=value,
                expires_at=expires,
            )

    def clear(self):
        with self._lock:
            self._items.clear()


market_cache = TTLCache()
