"""Small Redis cache wrapper. Cache failures never break the shopping API."""
from __future__ import annotations

import json
from functools import lru_cache

from redis import Redis

from .config import settings


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=2)


def redis_ping() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        return False


def cache_get(key: str):
    try:
        value = get_redis().get(key)
        return json.loads(value) if value else None
    except Exception:
        return None


def cache_set(key: str, value, ttl: int = 60) -> None:
    try:
        get_redis().setex(key, ttl, json.dumps(value))
    except Exception:
        return


def cache_delete_prefix(prefix: str) -> None:
    try:
        keys = list(get_redis().scan_iter(match=f"{prefix}*", count=100))
        if keys:
            get_redis().delete(*keys)
    except Exception:
        return


def rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Best-effort fixed-window rate limiter. Returns True when allowed."""
    try:
        redis = get_redis()
        current = redis.incr(key)
        if current == 1:
            redis.expire(key, window_seconds)
        return current <= limit
    except Exception:
        # Redis outage should not make authentication permanently unavailable.
        return True
