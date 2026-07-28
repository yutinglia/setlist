"""Application query services, cache keys, and missing-record behavior."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Response, status

from models.channel import YouTubeChannel
from models.report import SummaryReport
from models.search import SetlistContributor, SongSearchResult, SongSuggestion
from models.song import Song
from models.video import YouTubeVideo
from routers.v1.health import health_check
from services.cache import (
    CATALOG_CACHE_NAMESPACE,
    PUBLIC_CACHE_NAMESPACES,
    REPORT_CACHE_NAMESPACE,
    SEARCH_CACHE_NAMESPACE,
    NullCacheBackend,
    ResponseCache,
)
from services.queries import CatalogQueryService, ReportQueryService


class _RecordingCache:
    def __init__(self):
        self.remembered: list[tuple[str, str]] = []
        self.invalidated: tuple[str, ...] = ()

    async def remember(self, namespace, parameters, response_type, loader):
        del response_type
        self.remembered.append((namespace, parameters["operation"]))
        return await loader()

    async def invalidate(self, *namespaces):
        self.invalidated = namespaces


def _cache():
    return ResponseCache(
        NullCacheBackend(),
        key_prefix="test",
        default_ttl_seconds=60,
    )


def _summary():
    return SummaryReport(
        generated_at=datetime(2026, 7, 29, tzinfo=UTC),
        channels=1,
        backfill={"pending": 0, "running": 0, "done": 1, "failed": 0},
        videos={
            "total": 1,
            "karaoke": 1,
            "song": 0,
            "other": 0,
            "with_list_snapshot": 1,
            "with_metadata_snapshot": 1,
            "date_unknown": 0,
            "date_approximate": 0,
            "date_exact": 1,
            "latest_discovered_at": None,
        },
        analysis={
            "attempted": 1,
            "with_setlist": 1,
            "videos_with_comments": 1,
            "comments": 1,
            "latest_analyzed_at": None,
            "status": {
                "pending": 0,
                "retry": 0,
                "no_setlist": 0,
                "done": 1,
                "exhausted": 0,
                "skipped": 0,
            },
        },
        songs={"total": 1, "analyzed_by_llm": 0},
    )


@pytest.mark.asyncio
async def test_catalog_query_service_loads_every_public_projection():
    channel = YouTubeChannel(
        id="UC-test",
        name="Test",
        url="https://www.youtube.com/@test",
    )
    video = YouTubeVideo(
        id="video",
        title="Karaoke",
        url="https://www.youtube.com/watch?v=video",
        channel_id=channel.id,
    )
    song = Song(id=1, title="Song", video_id=video.id, timestamp="01:00")
    detail = SongSearchResult(
        id=1,
        title=song.title,
        timestamp=song.timestamp,
        video_id=video.id,
        video_url=f"{video.url}&t=60s",
        video_title=video.title,
        channel_id=channel.id,
        channel_name=channel.name,
    )
    suggestion = SongSuggestion(title=song.title, occurrences=1)
    contributor = SetlistContributor(
        author="@helper",
        author_id="UC-helper",
        song_count=12,
        video_count=2,
    )
    channel_repo = SimpleNamespace(
        get_all=AsyncMock(return_value=[channel]),
        count_all=AsyncMock(return_value=1),
        get_by_id=AsyncMock(return_value=channel),
    )
    video_repo = SimpleNamespace(
        get_by_channel_id=AsyncMock(return_value=[video]),
        count_by_channel_id=AsyncMock(return_value=1),
        get_by_id=AsyncMock(return_value=video),
    )
    song_repo = SimpleNamespace(
        search_by_title=AsyncMock(return_value=([detail], 1)),
        suggest_titles=AsyncMock(return_value=[suggestion]),
        get_detail=AsyncMock(return_value=detail),
        list_setlist_contributors=AsyncMock(return_value=([contributor], 1)),
        get_by_video_id=AsyncMock(return_value=[song]),
        count_by_video_id=AsyncMock(return_value=1),
    )
    cache = _RecordingCache()
    service = CatalogQueryService(channel_repo, video_repo, song_repo, cache)

    search = await service.search_songs(
        "Song",
        limit=20,
        offset=0,
        channel_ids=["UC-z", "UC-test", "UC-test"],
        video_type="karaoke",
        upload_date_from="20260101",
        upload_date_to="20261231",
    )
    suggestions = await service.suggest_songs(
        "So",
        limit=8,
        channel_ids=None,
        video_type=None,
        upload_date_from=None,
        upload_date_to=None,
    )
    assert (await service.get_song(1)) == detail
    contributors = await service.list_setlist_contributors(limit=20, offset=0)
    channels = await service.list_channels(limit=20, offset=0)
    assert (await service.get_channel(channel.id)).id == channel.id
    videos = await service.list_channel_videos(
        channel.id,
        limit=10,
        offset=0,
        video_type="karaoke",
        has_song_list=True,
    )
    assert (await service.get_video(video.id)).id == video.id
    songs = await service.list_video_songs(video.id, limit=20, offset=0)
    await service.invalidate()

    assert search.items == [detail]
    assert suggestions == [suggestion]
    assert contributors.items == [contributor]
    assert contributors.total == 1
    assert channels.items[0].id == channel.id
    assert videos.items[0].id == video.id
    assert songs.items == [song]
    song_repo.search_by_title.assert_awaited_once()
    song_repo.suggest_titles.assert_awaited_once()
    assert cache.remembered == [
        (SEARCH_CACHE_NAMESPACE, "search_songs"),
        (SEARCH_CACHE_NAMESPACE, "suggest_songs"),
        (CATALOG_CACHE_NAMESPACE, "get_song"),
        (CATALOG_CACHE_NAMESPACE, "list_setlist_contributors"),
        (CATALOG_CACHE_NAMESPACE, "list_channels"),
        (CATALOG_CACHE_NAMESPACE, "get_channel"),
        (CATALOG_CACHE_NAMESPACE, "list_channel_videos"),
        (CATALOG_CACHE_NAMESPACE, "get_video"),
        (CATALOG_CACHE_NAMESPACE, "list_video_songs"),
    ]
    assert cache.invalidated == PUBLIC_CACHE_NAMESPACES


@pytest.mark.asyncio
async def test_catalog_query_service_returns_none_for_missing_relations():
    channel_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    video_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    song_repo = SimpleNamespace()
    service = CatalogQueryService(channel_repo, video_repo, song_repo, _cache())

    assert await service.get_channel("missing") is None
    assert (
        await service.list_channel_videos(
            "missing",
            limit=10,
            offset=0,
            video_type=None,
            has_song_list=None,
        )
        is None
    )
    assert await service.get_video("missing") is None
    assert await service.list_video_songs("missing", limit=20, offset=0) is None


@pytest.mark.asyncio
async def test_report_query_service_and_health_paths():
    expected = _summary()
    repo = SimpleNamespace(get_summary=AsyncMock(return_value=expected))
    cache = _RecordingCache()
    assert await ReportQueryService(repo, cache).get_summary() == expected
    assert cache.remembered == [(REPORT_CACHE_NAMESPACE, "summary")]

    healthy_response = Response()
    healthy_session = SimpleNamespace(execute=AsyncMock(return_value=None))
    healthy_container = SimpleNamespace(
        cache=SimpleNamespace(status=AsyncMock(return_value="disabled"))
    )
    assert await health_check(
        healthy_response,
        healthy_session,
        healthy_container,
    ) == {
        "status": "healthy",
        "version": "v1",
        "database": "ok",
        "cache": "disabled",
    }
    assert healthy_response.status_code == status.HTTP_200_OK

    failed_response = Response()
    failed_session = SimpleNamespace(
        execute=AsyncMock(side_effect=RuntimeError("database unavailable"))
    )
    result = await health_check(
        failed_response,
        failed_session,
        healthy_container,
    )
    assert result["status"] == "unhealthy"
    assert result["database"] == "unavailable"
    assert failed_response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
