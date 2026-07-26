"""Management channel creation scheduling regressions without PostgreSQL."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from models.channel import ChannelCreate, YouTubeChannel
from routers.v1 import search
from services.data_updater import DataUpdater


def _channel() -> YouTubeChannel:
    return YouTubeChannel(
        id="UC-new",
        name="New channel",
        url="https://www.youtube.com/@new-channel",
        raw_data={},
    )


@pytest.mark.asyncio
async def test_create_channel_commits_before_requesting_immediate_backfill(
    monkeypatch,
):
    order: list[str] = []
    scraped = _channel()
    persisted = scraped.model_copy(
        update={"video_backfill_status": "pending", "video_backfill_offset": 1}
    )
    repo = SimpleNamespace(
        get_youtube_cooldown_until=AsyncMock(return_value=None),
        get_by_id=AsyncMock(return_value=None),
        create=AsyncMock(return_value=persisted),
    )
    session = SimpleNamespace(
        commit=AsyncMock(side_effect=lambda: order.append("commit")),
        rollback=AsyncMock(),
    )
    trigger = SimpleNamespace(
        request=Mock(side_effect=lambda **_kwargs: order.append("request") or True)
    )
    monkeypatch.setattr(search, "ChannelRepository", lambda _session: repo)
    monkeypatch.setattr(search.asyncio, "to_thread", AsyncMock(return_value=scraped))
    monkeypatch.setattr(search, "BACKGROUND_UPDATER_ENABLED", True)
    monkeypatch.setattr(search, "update_cycle_trigger", trigger)
    DataUpdater._youtube_cooldown_until = None

    created = await search.create_channel(
        ChannelCreate(url=scraped.url),
        None,
        session,
    )

    assert created.video_backfill_status == "pending"
    assert order == ["commit", "request"]
    session.commit.assert_awaited_once()
    trigger.request.assert_called_once_with(priority_channel_id=scraped.id)


@pytest.mark.asyncio
async def test_atomic_create_conflict_does_not_wake_updater(monkeypatch):
    scraped = _channel()
    repo = SimpleNamespace(
        get_youtube_cooldown_until=AsyncMock(return_value=None),
        get_by_id=AsyncMock(side_effect=[None, scraped]),
        create=AsyncMock(return_value=None),
    )
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    trigger = SimpleNamespace(request=Mock(return_value=True))
    monkeypatch.setattr(search, "ChannelRepository", lambda _session: repo)
    monkeypatch.setattr(search.asyncio, "to_thread", AsyncMock(return_value=scraped))
    monkeypatch.setattr(search, "BACKGROUND_UPDATER_ENABLED", True)
    monkeypatch.setattr(search, "update_cycle_trigger", trigger)
    DataUpdater._youtube_cooldown_until = None

    with pytest.raises(search.HTTPException) as exc_info:
        await search.create_channel(
            ChannelCreate(url=scraped.url),
            None,
            session,
        )

    assert exc_info.value.status_code == 409
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    trigger.request.assert_not_called()
