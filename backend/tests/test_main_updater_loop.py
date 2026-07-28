"""Periodic worker wake-up wiring without a database."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import main
from services.update_cycle_trigger import UpdateCycleRequest


@pytest.mark.asyncio
async def test_worker_passes_wake_channel_to_next_cycle():
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
    container = SimpleNamespace(
        settings=SimpleNamespace(
            data_update_interval=300,
            updater_heartbeat_interval_seconds=30,
        ),
        updater_status=SimpleNamespace(
            set=Mock(),
            stop=Mock(),
            end_cycle=Mock(),
        ),
        session_factory=_SessionContext,
        data_updater=lambda _session: _FakeUpdater(),
        youtube_cooldown=SimpleNamespace(remaining=Mock(return_value=0)),
        runtime_state_store=SimpleNamespace(heartbeat=AsyncMock(return_value=True)),
        update_cycle_trigger=trigger,
    )

    await main.run_periodic_data_updater(container)

    assert priorities == [None, "channel-new"]
    trigger.wait.assert_awaited_once_with(
        min(
            container.settings.data_update_interval,
            container.settings.updater_heartbeat_interval_seconds,
        )
    )


@pytest.mark.asyncio
async def test_waiting_worker_refreshes_durable_heartbeat():
    request = UpdateCycleRequest(priority_channel_id="channel-new")
    trigger = SimpleNamespace(
        wait=AsyncMock(side_effect=[None, request]),
    )
    runtime_store = SimpleNamespace(heartbeat=AsyncMock(return_value=True))
    result = await main.wait_for_next_update_cycle(
        runtime_store,
        trigger,
        timeout_seconds=60,
        heartbeat_interval_seconds=5,
    )

    assert result == request
    runtime_store.heartbeat.assert_awaited_once()
    assert trigger.wait.await_count == 2
