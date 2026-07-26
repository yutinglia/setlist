"""Immediate updater wake queue regressions."""

import pytest

from services.update_cycle_trigger import UpdateCycleTrigger


@pytest.mark.asyncio
async def test_channel_request_wakes_immediately_with_priority():
    trigger = UpdateCycleTrigger()

    assert trigger.request(priority_channel_id="channel-1") is True
    request = await trigger.wait(timeout_seconds=60)

    assert request is not None
    assert request.priority_channel_id == "channel-1"


@pytest.mark.asyncio
async def test_duplicate_channel_request_is_coalesced():
    trigger = UpdateCycleTrigger()

    assert trigger.request(priority_channel_id="channel-1") is True
    assert trigger.request(priority_channel_id="channel-1") is False
    request = await trigger.wait(60)
    assert request is not None
    assert request.priority_channel_id == "channel-1"
    assert await trigger.wait(0) is None


@pytest.mark.asyncio
async def test_multiple_channels_remain_separate_bounded_cycles():
    trigger = UpdateCycleTrigger()
    trigger.request(priority_channel_id="channel-1")
    trigger.request(priority_channel_id="channel-2")

    first = await trigger.wait(60)
    second = await trigger.wait(60)

    assert first is not None and first.priority_channel_id == "channel-1"
    assert second is not None and second.priority_channel_id == "channel-2"


@pytest.mark.asyncio
async def test_periodic_timeout_has_no_priority():
    trigger = UpdateCycleTrigger()

    assert await trigger.wait(0) is None
