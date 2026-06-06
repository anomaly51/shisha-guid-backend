import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings

_buckets: dict[str, deque[float]] = defaultdict(deque)
_last_prune_at = 0.0


def _client_key(request: Request, scope: str) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    ip = (
        forwarded_for.split(",", 1)[0].strip()
        if forwarded_for
        else request.headers.get("x-real-ip")
        or (request.client.host if request.client else "unknown")
    )
    return f"{scope}:{ip}"


async def enforce_rate_limit(request: Request, scope: str, limit: int) -> None:
    global _last_prune_at
    now = time.monotonic()
    window = settings.RATE_LIMIT_WINDOW_SECONDS
    bucket = _buckets[_client_key(request, scope)]

    while bucket and bucket[0] <= now - window:
        bucket.popleft()

    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": str(window)},
        )

    bucket.append(now)

    should_prune = now - _last_prune_at >= window or len(_buckets) > 10000
    if should_prune:
        _last_prune_at = now
        for key, values in list(_buckets.items()):
            while values and values[0] <= now - window:
                values.popleft()
            if not values:
                _buckets.pop(key, None)


def rate_limiter(scope: str, limit: int) -> Callable[[Request], object]:
    async def dependency(request: Request) -> None:
        await enforce_rate_limit(request, scope, limit)

    return dependency
