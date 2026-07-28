"""Public single-channel route behavior without PostgreSQL."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from routers.v1 import search


@pytest.mark.asyncio
async def test_get_channel_returns_public_channel():
    channel = SimpleNamespace(
        id="UC-test",
        name="Test Channel",
        url="https://www.youtube.com/channel/UC-test",
        thumbnail_url=None,
        created_at=None,
        updated_at=None,
    )
    queries = SimpleNamespace(get_channel=AsyncMock(return_value=channel))

    result = await search.get_channel("UC-test", queries)

    assert result.name == "Test Channel"
    queries.get_channel.assert_awaited_once_with("UC-test")


@pytest.mark.asyncio
async def test_get_channel_404_when_missing():
    queries = SimpleNamespace(get_channel=AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc_info:
        await search.get_channel("UC-missing", queries)

    assert exc_info.value.status_code == 404
