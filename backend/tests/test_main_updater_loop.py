"""Periodic worker wake-up wiring without a database."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import main
from services.update_cycle_trigger import UpdateCycleRequest


@pytest.mark.asyncio
async def test_worker_passes_wake_channel_to_next_cycle(monkeypatch):
    priorities: list[str | None] = []

    class _SessionContext:
        async def __aenter__(self):
            return SimpleNamespace()

        async def __aexit__(self, *_args):
            return False

    class _FakeUpdater:
        def __init__(self, *_args):
            pass

        async def update(self, *, priority_channel_id=None):
            priorities.append(priority_channel_id)
            if len(priorities) == 2:
                raise asyncio.CancelledError

        @staticmethod
        def youtube_cooldown_remaining():
            return 0

    trigger = SimpleNamespace(
        wait=AsyncMock(
            return_value=UpdateCycleRequest(priority_channel_id="channel-new")
        )
    )
    monkeypatch.setattr(main, "async_session_factory", _SessionContext)
    monkeypatch.setattr(main, "ChannelRepository", lambda _session: SimpleNamespace())
    monkeypatch.setattr(main, "VideoRepository", lambda _session: SimpleNamespace())
    monkeypatch.setattr(main, "SongRepository", lambda _session: SimpleNamespace())
    monkeypatch.setattr(main, "DataUpdater", _FakeUpdater)
    monkeypatch.setattr(main, "update_cycle_trigger", trigger)

    await main.run_periodic_data_updater()

    assert priorities == [None, "channel-new"]
    trigger.wait.assert_awaited_once_with(
        min(
            main.DATA_UPDATE_INTERVAL,
            main.UPDATER_HEARTBEAT_INTERVAL_SECONDS,
        )
    )


@pytest.mark.asyncio
async def test_waiting_worker_refreshes_durable_heartbeat(monkeypatch):
    request = UpdateCycleRequest(priority_channel_id="channel-new")
    trigger = SimpleNamespace(
        wait=AsyncMock(side_effect=[None, request]),
    )
    runtime_store = SimpleNamespace(heartbeat=AsyncMock(return_value=True))
    monkeypatch.setattr(main, "update_cycle_trigger", trigger)

    result = await main.wait_for_next_update_cycle(
        runtime_store,
        timeout_seconds=60,
        heartbeat_interval_seconds=5,
    )

    assert result == request
    runtime_store.heartbeat.assert_awaited_once()
    assert trigger.wait.await_count == 2
