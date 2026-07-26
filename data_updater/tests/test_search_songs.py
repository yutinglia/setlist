"""Song search route filter forwarding without PostgreSQL."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from models.search import Paginated, SongSearchResult
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
async def test_search_songs_forwards_filters(monkeypatch):
    items = [_hit()]
    song_repo = SimpleNamespace(
        search_by_title=AsyncMock(return_value=(items, 1)),
    )
    monkeypatch.setattr(search, "SongRepository", lambda _session: song_repo)

    result = await search.search_songs(
        "Stellar",
        "UC-test",
        "karaoke",
        "20240101",
        "20241231",
        (20, 0),
        SimpleNamespace(),
    )

    assert isinstance(result, Paginated)
    assert result.total == 1
    assert result.items[0].title == "Stellar"
    song_repo.search_by_title.assert_awaited_once_with(
        "Stellar",
        limit=20,
        offset=0,
        channel_id="UC-test",
        video_type="karaoke",
        upload_date_from="20240101",
        upload_date_to="20241231",
    )


@pytest.mark.asyncio
async def test_search_songs_omits_unset_filters(monkeypatch):
    song_repo = SimpleNamespace(
        search_by_title=AsyncMock(return_value=([], 0)),
    )
    monkeypatch.setattr(search, "SongRepository", lambda _session: song_repo)

    await search.search_songs(
        "Love",
        None,
        None,
        None,
        None,
        (20, 0),
        SimpleNamespace(),
    )

    song_repo.search_by_title.assert_awaited_once_with(
        "Love",
        limit=20,
        offset=0,
        channel_id=None,
        video_type=None,
        upload_date_from=None,
        upload_date_to=None,
    )


@pytest.mark.asyncio
async def test_search_songs_rejects_inverted_date_range(monkeypatch):
    song_repo = SimpleNamespace(
        search_by_title=AsyncMock(return_value=([], 0)),
    )
    monkeypatch.setattr(search, "SongRepository", lambda _session: song_repo)

    with pytest.raises(HTTPException) as exc_info:
        await search.search_songs(
            "Love",
            None,
            None,
            "20241231",
            "20240101",
            (20, 0),
            SimpleNamespace(),
        )

    assert exc_info.value.status_code == 422
    song_repo.search_by_title.assert_not_awaited()
