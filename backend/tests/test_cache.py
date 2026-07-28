"""Optional cache adapter, cache-aside, and DI regressions."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import TypeAdapter

from config import CacheSettings
from models.search import SongSearchResult
from services.cache import (
    PUBLIC_CACHE_NAMESPACES,
    MemoryCacheBackend,
    RedisCacheBackend,
    ResponseCache,
    create_cache,
)
from services.data_updater import DataUpdater
from services.queries import CatalogQueryService


def _hit() -> SongSearchResult:
    return SongSearchResult(
        id=1,
        title="Stellar",
        timestamp="1:23",
        video_id="vid-a",
        video_url="https://www.youtube.com/watch?v=vid-a&t=83s",
        video_title="Karaoke",
        channel_id="UC-test",
        channel_name="Test Channel",
    )


@pytest.mark.asyncio
async def test_response_cache_hits_and_namespace_invalidation():
    cache = ResponseCache(
        MemoryCacheBackend(),
        key_prefix="test",
        default_ttl_seconds=60,
    )
    loader = AsyncMock(return_value=_hit())

    first = await cache.remember(
        "catalog",
        {"operation": "song", "id": 1},
        SongSearchResult,
        loader,
    )
    second = await cache.remember(
        "catalog",
        {"id": 1, "operation": "song"},
        SongSearchResult,
        loader,
    )

    assert first == second
    loader.assert_awaited_once()

    await cache.invalidate("catalog")
    await cache.remember(
        "catalog",
        {"operation": "song", "id": 1},
        SongSearchResult,
        loader,
    )
    assert loader.await_count == 2


@pytest.mark.asyncio
async def test_cache_failure_is_fail_open():
    backend = SimpleNamespace(
        enabled=True,
        name="failing",
        get=AsyncMock(side_effect=ConnectionError("down")),
        set=AsyncMock(side_effect=ConnectionError("down")),
        delete_prefix=AsyncMock(side_effect=ConnectionError("down")),
        ping=AsyncMock(side_effect=ConnectionError("down")),
        aclose=AsyncMock(),
    )
    cache = ResponseCache(
        backend,
        key_prefix="test",
        default_ttl_seconds=60,
    )
    loader = AsyncMock(return_value=_hit())

    result = await cache.remember(
        "catalog",
        {"id": 1},
        SongSearchResult,
        loader,
    )

    assert result.title == "Stellar"
    loader.assert_awaited_once()
    assert await cache.status() == "unavailable"
    backend.get.assert_awaited_once()
    backend.ping.assert_not_awaited()

    await cache.remember(
        "catalog",
        {"id": 2},
        SongSearchResult,
        loader,
    )
    backend.get.assert_awaited_once()
    assert loader.await_count == 2
    await cache.invalidate("catalog")


@pytest.mark.asyncio
async def test_catalog_query_service_uses_injected_cache():
    song_repo = SimpleNamespace(
        search_by_title=AsyncMock(return_value=([_hit()], 1)),
    )
    service = CatalogQueryService(
        SimpleNamespace(),
        SimpleNamespace(),
        song_repo,
        ResponseCache(
            MemoryCacheBackend(),
            key_prefix="test",
            default_ttl_seconds=60,
        ),
    )

    first = await service.search_songs(
        "Stellar",
        limit=20,
        offset=0,
        channel_ids=["UC-b", "UC-a"],
        video_type="karaoke",
        upload_date_from=None,
        upload_date_to=None,
    )
    second = await service.search_songs(
        "Stellar",
        limit=20,
        offset=0,
        channel_ids=["UC-a", "UC-b"],
        video_type="karaoke",
        upload_date_from=None,
        upload_date_to=None,
    )

    assert first == second
    song_repo.search_by_title.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_cache_url_injects_noop_backend():
    cache = create_cache(
        CacheSettings(
            url="",
            key_prefix="test",
            default_ttl_seconds=60,
            search_ttl_seconds=900,
            catalog_ttl_seconds=3600,
            report_ttl_seconds=300,
            failure_backoff_seconds=5,
            connect_timeout_seconds=1,
            socket_timeout_seconds=1,
        )
    )
    loader = AsyncMock(return_value=_hit())

    await cache.remember("catalog", {"id": 1}, SongSearchResult, loader)
    await cache.remember("catalog", {"id": 1}, SongSearchResult, loader)

    assert cache.enabled is False
    assert await cache.status() == "disabled"
    assert loader.await_count == 2


@pytest.mark.asyncio
async def test_mutation_invalidates_injected_cache_only_after_commit():
    order: list[str] = []
    session = SimpleNamespace(
        commit=AsyncMock(side_effect=lambda: order.append("commit")),
    )
    cache = SimpleNamespace(
        invalidate=AsyncMock(
            side_effect=lambda *_namespaces: order.append("invalidate")
        )
    )
    updater = DataUpdater(
        session,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        cache=cache,
    )

    await updater._commit()

    assert order == ["commit", "invalidate"]
    cache.invalidate.assert_awaited_once_with(*PUBLIC_CACHE_NAMESPACES)

    cache.invalidate.reset_mock()
    await updater._commit(invalidate_cache=False)
    cache.invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_redis_cache_adapter_handles_values_batches_and_lifecycle():
    async def scan_iter(**kwargs):
        assert kwargs == {"match": "prefix*", "count": 100}
        for index in range(105):
            yield f"key-{index}"

    client = SimpleNamespace(
        get=AsyncMock(side_effect=[None, b"bytes", "text"]),
        set=AsyncMock(),
        scan_iter=scan_iter,
        delete=AsyncMock(),
        ping=AsyncMock(return_value=1),
        aclose=AsyncMock(),
    )
    backend = RedisCacheBackend(client)

    assert await backend.get("missing") is None
    assert await backend.get("bytes") == b"bytes"
    assert await backend.get("text") == b"text"
    await backend.set("key", b"value", ttl_seconds=30)
    await backend.delete_prefix("prefix")
    assert await backend.ping() is True
    await backend.aclose()

    client.set.assert_awaited_once_with("key", b"value", ex=30)
    assert client.delete.await_count == 2
    assert len(client.delete.await_args_list[0].args) == 100
    assert len(client.delete.await_args_list[1].args) == 5
    client.aclose.assert_awaited_once()


def test_enabled_cache_settings_build_redis_adapter(monkeypatch):
    client = SimpleNamespace()
    from_url = Mock(return_value=client)
    monkeypatch.setattr("services.cache.Redis.from_url", from_url)
    settings = CacheSettings(
        url="redis://cache:6379/0",
        key_prefix="test",
        default_ttl_seconds=60,
        search_ttl_seconds=900,
        catalog_ttl_seconds=3600,
        report_ttl_seconds=300,
        failure_backoff_seconds=5,
        connect_timeout_seconds=1.5,
        socket_timeout_seconds=2.5,
    )

    cache = create_cache(settings)

    assert cache.enabled is True
    assert cache.backend._client is client
    from_url.assert_called_once_with(
        settings.url,
        decode_responses=False,
        socket_connect_timeout=1.5,
        socket_timeout=2.5,
        health_check_interval=30,
    )
    assert cache.namespace_ttl_seconds == {
        "search": 900,
        "catalog": 3600,
        "report": 300,
    }
    assert cache.failure_backoff_seconds == 5


@pytest.mark.asyncio
async def test_namespace_ttl_policy_is_used_for_cache_writes():
    backend = SimpleNamespace(
        enabled=True,
        name="recording",
        get=AsyncMock(return_value=None),
        set=AsyncMock(),
        delete_prefix=AsyncMock(),
        ping=AsyncMock(return_value=True),
        aclose=AsyncMock(),
    )
    cache = ResponseCache(
        backend,
        key_prefix="test",
        default_ttl_seconds=60,
        namespace_ttl_seconds={"search": 900, "catalog": 3600},
    )
    loader = AsyncMock(return_value=_hit())

    await cache.remember("search", {"id": 1}, SongSearchResult, loader)
    await cache.remember("catalog", {"id": 1}, SongSearchResult, loader)

    assert [call.kwargs["ttl_seconds"] for call in backend.set.await_args_list] == [
        900,
        3600,
    ]


@pytest.mark.asyncio
async def test_failed_invalidation_bypasses_stale_data_until_cleanup(monkeypatch):
    class FlakyInvalidationBackend(MemoryCacheBackend):
        def __init__(self):
            super().__init__()
            self.delete_calls = 0

        async def delete_prefix(self, prefix: str) -> None:
            self.delete_calls += 1
            if self.delete_calls == 1:
                raise ConnectionError("temporarily unavailable")
            await super().delete_prefix(prefix)

    clock = Mock(return_value=100.0)
    monkeypatch.setattr("services.cache.time.monotonic", clock)
    backend = FlakyInvalidationBackend()
    cache = ResponseCache(
        backend,
        key_prefix="test",
        default_ttl_seconds=60,
        failure_backoff_seconds=5,
    )
    key = cache._key("catalog", {"id": 1})
    await backend.set(
        key, TypeAdapter(SongSearchResult).dump_json(_hit()), ttl_seconds=60
    )
    fresh = _hit().model_copy(update={"title": "Fresh"})
    loader = AsyncMock(return_value=fresh)

    await cache.invalidate("catalog")
    assert (
        await cache.remember(
            "catalog",
            {"id": 1},
            SongSearchResult,
            loader,
        )
    ) == fresh
    assert backend.delete_calls == 1

    clock.return_value = 106.0
    assert (
        await cache.remember(
            "catalog",
            {"id": 1},
            SongSearchResult,
            loader,
        )
    ) == fresh
    assert backend.delete_calls == 2
    assert loader.await_count == 2
    assert cache._dirty_namespaces == set()


@pytest.mark.asyncio
async def test_cache_invalid_payload_expiry_and_close_failure(monkeypatch):
    backend = MemoryCacheBackend()
    cache = ResponseCache(
        backend,
        key_prefix="test",
        default_ttl_seconds=60,
    )
    key = cache._key("catalog", {"id": 1})
    await backend.set(key, b"not-json", ttl_seconds=60)
    loader = AsyncMock(return_value=_hit())

    assert (
        await cache.remember(
            "catalog",
            {"id": 1},
            SongSearchResult,
            loader,
            ttl_seconds=5,
        )
    ) == _hit()
    loader.assert_awaited_once()

    monkeypatch.setattr(
        "services.cache.time.monotonic",
        Mock(return_value=10_000_000_000),
    )
    assert await backend.get(key) is None
    assert await backend.ping() is True
    await backend.aclose()

    failing = ResponseCache(
        SimpleNamespace(
            enabled=True,
            name="failing",
            aclose=AsyncMock(side_effect=ConnectionError("down")),
        ),
        key_prefix="test",
        default_ttl_seconds=60,
    )
    await failing.aclose()
