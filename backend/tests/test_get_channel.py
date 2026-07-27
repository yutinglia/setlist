"""Public single-channel route behavior without PostgreSQL."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from routers.v1 import search


@pytest.mark.asyncio
async def test_get_channel_returns_public_channel(monkeypatch):
    channel = SimpleNamespace(
        id="UC-test",
        name="Test Channel",
        url="https://www.youtube.com/channel/UC-test",
        thumbnail_url=None,
        created_at=None,
        updated_at=None,
    )
    repo = SimpleNamespace(get_by_id=AsyncMock(return_value=channel))
    monkeypatch.setattr(search, "ChannelRepository", lambda _session: repo)

    result = await search.get_channel("UC-test", SimpleNamespace())

    assert result.name == "Test Channel"
    repo.get_by_id.assert_awaited_once_with("UC-test")


@pytest.mark.asyncio
async def test_get_channel_404_when_missing(monkeypatch):
    repo = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    monkeypatch.setattr(search, "ChannelRepository", lambda _session: repo)

    with pytest.raises(HTTPException) as exc_info:
        await search.get_channel("UC-missing", SimpleNamespace())

    assert exc_info.value.status_code == 404
