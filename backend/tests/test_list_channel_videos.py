"""Channel video list route filters without PostgreSQL."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from models.search import Paginated
from models.video import YouTubeVideo
from routers.v1 import search


def _video(video_id: str, *, has_song_list: bool = False) -> YouTubeVideo:
    return YouTubeVideo(
        id=video_id,
        title=f"Title {video_id}",
        url=f"https://www.youtube.com/watch?v={video_id}",
        channel_id="UC-test",
        type="karaoke",
        has_song_list_comment=has_song_list,
    )


@pytest.mark.asyncio
async def test_list_channel_videos_forwards_has_song_list(monkeypatch):
    items = [_video("vid-a", has_song_list=True)]
    video_repo = SimpleNamespace(
        get_by_channel_id=AsyncMock(return_value=items),
        count_by_channel_id=AsyncMock(return_value=1),
    )
    channel_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(id="UC-test")),
    )
    monkeypatch.setattr(search, "ChannelRepository", lambda _session: channel_repo)
    monkeypatch.setattr(search, "VideoRepository", lambda _session: video_repo)

    result = await search.list_channel_videos(
        "UC-test",
        (20, 0),
        "karaoke",
        True,
        SimpleNamespace(),
    )

    assert isinstance(result, Paginated)
    assert result.total == 1
    assert result.items[0].id == "vid-a"
    video_repo.get_by_channel_id.assert_awaited_once_with(
        "UC-test",
        limit=20,
        offset=0,
        video_type="karaoke",
        has_song_list=True,
    )
    video_repo.count_by_channel_id.assert_awaited_once_with(
        "UC-test",
        video_type="karaoke",
        has_song_list=True,
    )


@pytest.mark.asyncio
async def test_list_channel_videos_omits_has_song_list_when_unset(monkeypatch):
    video_repo = SimpleNamespace(
        get_by_channel_id=AsyncMock(return_value=[]),
        count_by_channel_id=AsyncMock(return_value=0),
    )
    channel_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(id="UC-test")),
    )
    monkeypatch.setattr(search, "ChannelRepository", lambda _session: channel_repo)
    monkeypatch.setattr(search, "VideoRepository", lambda _session: video_repo)

    await search.list_channel_videos(
        "UC-test",
        (20, 0),
        None,
        None,
        SimpleNamespace(),
    )

    video_repo.get_by_channel_id.assert_awaited_once_with(
        "UC-test",
        limit=20,
        offset=0,
        video_type=None,
        has_song_list=None,
    )
    video_repo.count_by_channel_id.assert_awaited_once_with(
        "UC-test",
        video_type=None,
        has_song_list=None,
    )


@pytest.mark.asyncio
async def test_list_channel_videos_404_when_channel_missing(monkeypatch):
    channel_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    monkeypatch.setattr(search, "ChannelRepository", lambda _session: channel_repo)

    with pytest.raises(HTTPException) as exc_info:
        await search.list_channel_videos(
            "UC-missing",
            (20, 0),
            None,
            False,
            SimpleNamespace(),
        )

    assert exc_info.value.status_code == 404
