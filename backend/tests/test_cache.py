"""Optional cache adapter, cache-aside, and DI regressions."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config import CacheSettings
from models.search import SongSearchResult
from services.cache import MemoryCacheBackend, ResponseCache, create_cache
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
    cache.invalidate.assert_awaited_once_with("catalog", "report")
