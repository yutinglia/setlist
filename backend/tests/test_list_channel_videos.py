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
async def test_list_channel_videos_forwards_has_song_list():
    items = [_video("vid-a", has_song_list=True)]
    expected = Paginated(items=items, total=1, limit=20, offset=0)
    queries = SimpleNamespace(
        list_channel_videos=AsyncMock(return_value=expected),
    )

    result = await search.list_channel_videos(
        "UC-test",
        (20, 0),
        "karaoke",
        True,
        queries,
    )

    assert isinstance(result, Paginated)
    assert result.total == 1
    assert result.items[0].id == "vid-a"
    queries.list_channel_videos.assert_awaited_once_with(
        "UC-test",
        limit=20,
        offset=0,
        video_type="karaoke",
        has_song_list=True,
    )


@pytest.mark.asyncio
async def test_list_channel_videos_omits_has_song_list_when_unset():
    queries = SimpleNamespace(
        list_channel_videos=AsyncMock(
            return_value=Paginated(items=[], total=0, limit=20, offset=0)
        ),
    )

    await search.list_channel_videos(
        "UC-test",
        (20, 0),
        None,
        None,
        queries,
    )

    queries.list_channel_videos.assert_awaited_once_with(
        "UC-test",
        limit=20,
        offset=0,
        video_type=None,
        has_song_list=None,
    )


@pytest.mark.asyncio
async def test_list_channel_videos_404_when_channel_missing():
    queries = SimpleNamespace(list_channel_videos=AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc_info:
        await search.list_channel_videos(
            "UC-missing",
            (20, 0),
            None,
            False,
            queries,
        )

    assert exc_info.value.status_code == 404
