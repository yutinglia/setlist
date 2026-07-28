"""Dependency-injected cache ports and Redis/Valkey adapters."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import TypeAdapter
from redis.asyncio import Redis

from config import CacheSettings

logger = logging.getLogger(__name__)
T = TypeVar("T")


class CacheBackend(Protocol):
    """Small async key/value port implemented by cache infrastructure."""

    enabled: bool
    name: str

    async def get(self, key: str) -> bytes | None: ...

    async def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None: ...

    async def delete_prefix(self, prefix: str) -> None: ...

    async def ping(self) -> bool: ...

    async def aclose(self) -> None: ...


class NullCacheBackend:
    """No-op object used when shared caching is not configured."""

    enabled = False
    name = "disabled"

    async def get(self, key: str) -> bytes | None:
        del key
        return None

    async def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None:
        del key, value, ttl_seconds

    async def delete_prefix(self, prefix: str) -> None:
        del prefix

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None


class RedisCacheBackend:
    """redis-py asyncio adapter compatible with Redis and Valkey."""

    enabled = True
    name = "redis-compatible"

    def __init__(self, client: Redis) -> None:
        self._client = client

    @classmethod
    def from_settings(cls, settings: CacheSettings) -> RedisCacheBackend:
        client = Redis.from_url(
            settings.url,
            decode_responses=False,
            socket_connect_timeout=settings.connect_timeout_seconds,
            socket_timeout=settings.socket_timeout_seconds,
            health_check_interval=30,
        )
        return cls(client)

    async def get(self, key: str) -> bytes | None:
        value = await self._client.get(key)
        if value is None:
            return None
        return value if isinstance(value, bytes) else str(value).encode()

    async def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None:
        await self._client.set(key, value, ex=ttl_seconds)

    async def delete_prefix(self, prefix: str) -> None:
        batch: list[str | bytes] = []
        async for key in self._client.scan_iter(match=f"{prefix}*", count=100):
            batch.append(key)
            if len(batch) >= 100:
                await self._client.delete(*batch)
                batch.clear()
        if batch:
            await self._client.delete(*batch)

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def aclose(self) -> None:
        await self._client.aclose()


@dataclass
class _MemoryValue:
    value: bytes
    expires_at: float


class MemoryCacheBackend:
    """Deterministic cache fake for unit tests and local component tests."""

    enabled = True
    name = "memory"

    def __init__(self) -> None:
        self._values: dict[str, _MemoryValue] = {}

    async def get(self, key: str) -> bytes | None:
        item = self._values.get(key)
        if item is None:
            return None
        if item.expires_at <= time.monotonic():
            self._values.pop(key, None)
            return None
        return item.value

    async def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None:
        self._values[key] = _MemoryValue(
            value=value,
            expires_at=time.monotonic() + ttl_seconds,
        )

    async def delete_prefix(self, prefix: str) -> None:
        for key in [key for key in self._values if key.startswith(prefix)]:
            self._values.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        self._values.clear()


class ResponseCache:
    """Cache-aside service with bounded local stampede protection.

    Cache errors are deliberately fail-open: PostgreSQL remains authoritative
    and an unavailable optional cache must not take down public reads.
    """

    _SCHEMA_VERSION = "v1"

    def __init__(
        self,
        backend: CacheBackend,
        *,
        key_prefix: str,
        default_ttl_seconds: int,
    ) -> None:
        self.backend = backend
        self.key_prefix = key_prefix
        self.default_ttl_seconds = default_ttl_seconds
        self._locks = tuple(asyncio.Lock() for _ in range(64))
        self._last_failure_log_at = 0.0

    @property
    def enabled(self) -> bool:
        return self.backend.enabled

    async def remember(
        self,
        namespace: str,
        parameters: dict[str, Any],
        response_type: Any,
        loader: Callable[[], Awaitable[T]],
        *,
        ttl_seconds: int | None = None,
    ) -> T:
        if not self.enabled:
            return await loader()

        key = self._key(namespace, parameters)
        adapter: TypeAdapter[T] = TypeAdapter(response_type)
        cached = await self._safe_get(key)
        if cached is not None:
            try:
                return adapter.validate_json(cached)
            except Exception:
                logger.warning("Ignoring invalid cached response for %s", namespace)

        lock = self._locks[int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 64]
        async with lock:
            cached = await self._safe_get(key)
            if cached is not None:
                try:
                    return adapter.validate_json(cached)
                except Exception:
                    pass
            result = await loader()
            payload = adapter.dump_json(result)
            await self._safe_set(
                key,
                payload,
                ttl_seconds=ttl_seconds or self.default_ttl_seconds,
            )
            return result

    async def invalidate(self, *namespaces: str) -> None:
        for namespace in namespaces:
            prefix = f"{self.key_prefix}:{self._SCHEMA_VERSION}:{namespace}:"
            try:
                await self.backend.delete_prefix(prefix)
            except Exception as exc:
                self._log_failure("invalidate", exc)

    async def status(self) -> str:
        if not self.enabled:
            return "disabled"
        try:
            return "ok" if await self.backend.ping() else "unavailable"
        except Exception as exc:
            self._log_failure("ping", exc)
            return "unavailable"

    async def aclose(self) -> None:
        try:
            await self.backend.aclose()
        except Exception:
            logger.exception("Could not close optional cache client")

    def _key(self, namespace: str, parameters: dict[str, Any]) -> str:
        canonical = json.dumps(
            parameters,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        return f"{self.key_prefix}:{self._SCHEMA_VERSION}:{namespace}:{digest}"

    async def _safe_get(self, key: str) -> bytes | None:
        try:
            return await self.backend.get(key)
        except Exception as exc:
            self._log_failure("read", exc)
            return None

    async def _safe_set(self, key: str, value: bytes, *, ttl_seconds: int) -> None:
        try:
            await self.backend.set(key, value, ttl_seconds=ttl_seconds)
        except Exception as exc:
            self._log_failure("write", exc)

    def _log_failure(self, operation: str, exc: Exception) -> None:
        now = time.monotonic()
        if now - self._last_failure_log_at < 60:
            return
        self._last_failure_log_at = now
        logger.warning(
            "Optional cache %s failed; continuing without cache: %s",
            operation,
            type(exc).__name__,
        )


def create_cache(settings: CacheSettings) -> ResponseCache:
    backend: CacheBackend
    if settings.enabled:
        backend = RedisCacheBackend.from_settings(settings)
    else:
        backend = NullCacheBackend()
    return ResponseCache(
        backend,
        key_prefix=settings.key_prefix,
        default_ttl_seconds=settings.default_ttl_seconds,
    )
