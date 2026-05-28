import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.config import settings

T = TypeVar("T")


class TTLCache:
    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[float, object]] = {}
        self._lock = asyncio.Lock()

    async def get_or_set(self, key: str, factory: Callable[[], Awaitable[T]]) -> T:
        now = time.monotonic()
        async with self._lock:
            cached = self._items.get(key)
            if cached and cached[0] > now:
                return cached[1]  # type: ignore[return-value]

        value = await factory()
        async with self._lock:
            self._items[key] = (time.monotonic() + self.ttl_seconds, value)
        return value

    async def clear_prefix(self, prefix: str) -> None:
        async with self._lock:
            for key in list(self._items):
                if key.startswith(prefix):
                    self._items.pop(key, None)


catalog_cache = TTLCache(settings.CATALOG_CACHE_TTL_SECONDS)
