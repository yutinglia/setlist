"""Public catalog and administrator refresh route contracts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from models.search import (
    ChannelRead,
    Paginated,
    RecentUpdates,
    SetlistContributor,
    SongSearchResult,
    VideoRead,
)
from models.song import Song
from models.video import YouTubeVideo
from routers.v1 import search
from services.youtube_operation_lock import YouTubeUpdaterBusyError
from services.yt_scraper.errors import YouTubeAccessBlocked


def _detail() -> SongSearchResult:
    return SongSearchResult(
        id=1,
        title="Test Song",
        timestamp="01:23",
        video_id="video-1",
        video_url="https://www.youtube.com/watch?v=video-1&t=83s",
        video_title="Karaoke Night",
        channel_id="UC-test",
        channel_name="Test Channel",
    )


def _video() -> YouTubeVideo:
    return YouTubeVideo(
        id="video-1",
        title="Karaoke Night",
        url="https://www.youtube.com/watch?v=video-1",
        channel_id="UC-test",
        type="karaoke",
    )


@pytest.mark.asyncio
async def test_public_catalog_routes_return_paginated_projections():
    detail = _detail()
    channel = ChannelRead(
        id="UC-test",
        name="Test Channel",
        url="https://www.youtube.com/@test",
    )
    video = VideoRead.model_validate(_video())
    song = Song(
        id=detail.id,
        title=detail.title,
        video_id=detail.video_id,
        timestamp=detail.timestamp,
    )
    contributor = SetlistContributor(
        author="@helper",
        author_id="UC-helper",
        song_count=1,
        video_count=1,
    )
    queries = SimpleNamespace(
        get_song=AsyncMock(return_value=detail),
        list_setlist_contributors=AsyncMock(
            return_value=Paginated(
                items=[contributor],
                total=1,
                limit=20,
                offset=0,
            )
        ),
        list_channels=AsyncMock(
            return_value=Paginated(
                items=[channel],
                total=1,
                limit=10,
                offset=20,
            )
        ),
        get_recent_updates=AsyncMock(
            return_value=RecentUpdates(channels=[channel], songs=[detail])
        ),
        get_video=AsyncMock(return_value=video),
        list_video_songs=AsyncMock(
            return_value=Paginated(
                items=[song],
                total=1,
                limit=20,
                offset=40,
            )
        ),
    )

    assert (await search.get_song(1, queries)).title == detail.title
    contributors = await search.list_setlist_contributors((20, 0), queries)
    assert contributors.items == [contributor]
    channels = await search.list_channels("Test", (10, 20), queries)
    recent = await search.get_recent_updates(queries)
    assert channels.items == [channel]
    assert (await search.get_video(video.id, queries)).id == video.id
    songs = await search.list_video_songs(video.id, (20, 40), queries)
    assert songs.items == [song]
    assert recent.channels == [channel]
    assert recent.songs == [detail]
    queries.list_channels.assert_awaited_once_with(
        limit=10,
        offset=20,
        query="Test",
    )
    queries.get_recent_updates.assert_awaited_once_with()
    queries.list_setlist_contributors.assert_awaited_once_with(limit=20, offset=0)
    queries.list_video_songs.assert_awaited_once_with(
        video.id,
        limit=20,
        offset=40,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call", "detail"),
    [
        (lambda queries: search.get_song(404, queries), "Song not found"),
        (
            lambda queries: search.get_video("missing", queries),
            "Video not found",
        ),
        (
            lambda queries: search.list_video_songs(
                "missing",
                (20, 0),
                queries,
            ),
            "Video not found",
        ),
    ],
)
async def test_public_catalog_routes_map_missing_records_to_404(call, detail):
    queries = SimpleNamespace(
        get_song=AsyncMock(return_value=None),
        get_video=AsyncMock(return_value=None),
        list_video_songs=AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await call(queries)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == detail


@pytest.mark.asyncio
async def test_manual_refresh_routes_return_stable_public_responses():
    channel = SimpleNamespace(id="UC-test")
    video = _video()
    updater = SimpleNamespace(
        channel_repo=SimpleNamespace(get_by_id=AsyncMock(return_value=channel)),
        video_repo=SimpleNamespace(get_by_id=AsyncMock(return_value=video)),
        refresh_channel_video_list=AsyncMock(
            return_value=SimpleNamespace(
                channel_id=channel.id,
                mode="refresh",
                scraped=3,
                deleted=0,
                reclassified=1,
                cleared=1,
                message="Refreshed",
            )
        ),
        reload_video_song_list=AsyncMock(
            return_value=SimpleNamespace(
                video_id=video.id,
                song_count=2,
                has_song_list_comment=True,
                analysis_status="done",
                message="Reloaded",
            )
        ),
    )

    refresh = await search.refresh_channel_videos(channel.id, None, updater)
    reload = await search.reload_video_song_list(video.id, None, updater)

    assert refresh.model_dump() == {
        "channel_id": channel.id,
        "mode": "refresh",
        "scraped": 3,
        "deleted": 0,
        "reclassified": 1,
        "cleared": 1,
        "message": "Refreshed",
    }
    assert reload.video_id == video.id
    assert reload.song_count == 2
    assert reload.analysis_status == "done"


@pytest.mark.asyncio
async def test_manual_refresh_routes_return_404_before_scraping():
    updater = SimpleNamespace(
        channel_repo=SimpleNamespace(get_by_id=AsyncMock(return_value=None)),
        video_repo=SimpleNamespace(get_by_id=AsyncMock(return_value=None)),
        refresh_channel_video_list=AsyncMock(),
        reload_video_song_list=AsyncMock(),
    )

    with pytest.raises(HTTPException, match="Channel not found") as channel_exc:
        await search.refresh_channel_videos("missing", None, updater)
    with pytest.raises(HTTPException, match="Video not found") as video_exc:
        await search.reload_video_song_list("missing", None, updater)

    assert channel_exc.value.status_code == 404
    assert video_exc.value.status_code == 404
    updater.refresh_channel_video_list.assert_not_awaited()
    updater.reload_video_song_list.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            YouTubeUpdaterBusyError("busy"),
            503,
            "Another updater operation is running; try again shortly",
        ),
        (
            YouTubeAccessBlocked("blocked"),
            503,
            "YouTube temporarily blocked this request; try again later",
        ),
        (
            RuntimeError("private upstream detail"),
            502,
            "Could not refresh videos from YouTube",
        ),
    ],
)
async def test_channel_refresh_redacts_operational_failures(
    error,
    expected_status,
    expected_detail,
):
    updater = SimpleNamespace(
        channel_repo=SimpleNamespace(
            get_by_id=AsyncMock(return_value=SimpleNamespace(id="UC-test"))
        ),
        refresh_channel_video_list=AsyncMock(side_effect=error),
    )

    with pytest.raises(HTTPException) as exc_info:
        await search.refresh_channel_videos("UC-test", None, updater)

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == expected_detail
    assert "private upstream detail" not in exc_info.value.detail


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            YouTubeUpdaterBusyError("busy"),
            503,
            "Another updater operation is running; try again shortly",
        ),
        (
            YouTubeAccessBlocked("blocked"),
            503,
            "YouTube temporarily blocked this request; try again later",
        ),
        (
            RuntimeError("private upstream detail"),
            502,
            "Could not reload this song list from YouTube",
        ),
    ],
)
async def test_song_reload_redacts_operational_failures(
    error,
    expected_status,
    expected_detail,
):
    updater = SimpleNamespace(
        video_repo=SimpleNamespace(get_by_id=AsyncMock(return_value=_video())),
        reload_video_song_list=AsyncMock(side_effect=error),
    )

    with pytest.raises(HTTPException) as exc_info:
        await search.reload_video_song_list("video-1", None, updater)

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == expected_detail
    assert "private upstream detail" not in exc_info.value.detail
