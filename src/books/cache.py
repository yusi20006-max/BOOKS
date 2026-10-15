from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    """Thread-safe bounded LRU cache with monotonic TTL expiry."""

    def __init__(self, *, max_entries: int = 128, ttl_seconds: float = 300.0, clock=time.monotonic):
        if isinstance(max_entries, bool) or not isinstance(max_entries, int) or max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.max_entries = max_entries
        self.ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._items: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: K) -> V | None:
        now = self._clock()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= now:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key: K, value: V) -> None:
        expires_at = self._clock() + self.ttl_seconds
        with self._lock:
            self._items[key] = (expires_at, value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        now = self._clock()
        with self._lock:
            expired = [key for key, (expires_at, _) in self._items.items() if expires_at <= now]
            for key in expired:
                del self._items[key]
            return len(self._items)
