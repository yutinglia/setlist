"""Song search route filter forwarding without PostgreSQL."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from models.search import Paginated, SongSearchResult, SongSuggestion
from routers.v1 import search


def _hit(*, song_id: int = 1, title: str = "Stellar") -> SongSearchResult:
    return SongSearchResult(
        id=song_id,
        title=title,
        timestamp="1:23",
        video_id="vid-a",
        video_url="https://www.youtube.com/watch?v=vid-a&t=83s",
        video_title="Karaoke",
        channel_id="UC-test",
        channel_name="Test Channel",
    )


@pytest.mark.asyncio
async def test_search_songs_forwards_filters():
    items = [_hit()]
    queries = SimpleNamespace(
        search_songs=AsyncMock(
            return_value=Paginated(items=items, total=1, limit=20, offset=0)
        ),
    )

    result = await search.search_songs(
        "Stellar",
        ["UC-test", "UC-second"],
        "karaoke",
        "20240101",
        "20241231",
        (20, 0),
        queries,
    )

    assert isinstance(result, Paginated)
    assert result.total == 1
    assert result.items[0].title == "Stellar"
    queries.search_songs.assert_awaited_once_with(
        "Stellar",
        limit=20,
        offset=0,
        channel_ids=["UC-test", "UC-second"],
        video_type="karaoke",
        upload_date_from="20240101",
        upload_date_to="20241231",
    )


@pytest.mark.asyncio
async def test_search_songs_omits_unset_filters():
    queries = SimpleNamespace(
        search_songs=AsyncMock(
            return_value=Paginated(items=[], total=0, limit=20, offset=0)
        ),
    )

    await search.search_songs(
        "Love",
        None,
        None,
        None,
        None,
        (20, 0),
        queries,
    )

    queries.search_songs.assert_awaited_once_with(
        "Love",
        limit=20,
        offset=0,
        channel_ids=None,
        video_type=None,
        upload_date_from=None,
        upload_date_to=None,
    )


@pytest.mark.asyncio
async def test_search_songs_rejects_inverted_date_range():
    queries = SimpleNamespace(search_songs=AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        await search.search_songs(
            "Love",
            None,
            None,
            "20241231",
            "20240101",
            (20, 0),
            queries,
        )

    assert exc_info.value.status_code == 422
    queries.search_songs.assert_not_awaited()


@pytest.mark.asyncio
async def test_suggest_songs_forwards_limit_and_filters():
    suggestions = [SongSuggestion(title="Stellar", occurrences=3)]
    queries = SimpleNamespace(
        suggest_songs=AsyncMock(return_value=suggestions),
    )

    result = await search.suggest_songs(
        q="Ste",
        channel_id=["UC-test", "UC-second"],
        type="karaoke",
        upload_date_from="20240101",
        upload_date_to="20241231",
        limit=8,
        queries=queries,
    )

    assert result == suggestions
    queries.suggest_songs.assert_awaited_once_with(
        "Ste",
        limit=8,
        channel_ids=["UC-test", "UC-second"],
        video_type="karaoke",
        upload_date_from="20240101",
        upload_date_to="20241231",
    )


@pytest.mark.asyncio
async def test_suggest_songs_rejects_inverted_date_range():
    queries = SimpleNamespace(suggest_songs=AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        await search.suggest_songs(
            q="Love",
            channel_id=None,
            type=None,
            upload_date_from="20241231",
            upload_date_to="20240101",
            limit=8,
            queries=queries,
        )

    assert exc_info.value.status_code == 422
    queries.suggest_songs.assert_not_awaited()
