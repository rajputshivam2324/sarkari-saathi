"""Upstash Redis — REST and/or rediss:// TCP, with in-memory fallback."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_memory: dict[str, tuple[str, float | None]] = {}


class RedisCache:
    def __init__(self) -> None:
        settings = get_settings()
        self.rest_url = (settings.upstash_redis_rest_url or "").rstrip("/")
        self.token = settings.upstash_redis_rest_token or ""
        self.tcp_url = (settings.upstash_redis_url or "").strip()
        self.rest_enabled = bool(self.rest_url and self.token)
        self._redis = None
        if self.tcp_url.startswith(("redis://", "rediss://")):
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(
                    self.tcp_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                )
            except Exception as exc:
                logger.warning("TCP Redis init failed: %s", exc)

    @property
    def enabled(self) -> bool:
        return self.rest_enabled or self._redis is not None

    async def _rest(self, *args: Any) -> Any:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(
                self.rest_url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json=list(args),
            )
        if res.status_code >= 400:
            logger.warning("Upstash REST %s: %s", res.status_code, res.text[:200])
            return None
        return res.json().get("result")

    async def get(self, key: str) -> str | None:
        try:
            if self.rest_enabled:
                val = await self._rest("GET", key)
                return val if isinstance(val, str) else None
            if self._redis is not None:
                return await self._redis.get(key)
        except Exception as exc:
            logger.warning("Redis GET failed: %s", exc)

        item = _memory.get(key)
        if not item:
            return None
        value, exp = item
        if exp is not None and time.time() > exp:
            _memory.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, ttl_sec: int | None = None) -> None:
        try:
            if self.rest_enabled:
                if ttl_sec:
                    await self._rest("SET", key, value, "EX", ttl_sec)
                else:
                    await self._rest("SET", key, value)
                return
            if self._redis is not None:
                if ttl_sec:
                    await self._redis.set(key, value, ex=ttl_sec)
                else:
                    await self._redis.set(key, value)
                return
        except Exception as exc:
            logger.warning("Redis SET failed, using memory: %s", exc)

        exp = time.time() + ttl_sec if ttl_sec else None
        _memory[key] = (value, exp)

    async def get_json(self, key: str) -> Any | None:
        raw = await self.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set_json(self, key: str, value: Any, ttl_sec: int | None = None) -> None:
        await self.set(key, json.dumps(value, ensure_ascii=False), ttl_sec)

    async def ping(self) -> bool:
        try:
            if self.rest_enabled:
                return (await self._rest("PING")) == "PONG"
            if self._redis is not None:
                return (await self._redis.ping()) is True
        except Exception:
            return False
        return False


_cache: RedisCache | None = None


def get_cache() -> RedisCache:
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache
