"""Hard-deadline and cancellation tests for isolated scraper processes."""

from __future__ import annotations

import asyncio
import multiprocessing
import time
from functools import partial

import pytest

from services.yt_scraper.subprocess_runner import (
    ScrapeOperationTimeout,
    ScrapeSubprocessError,
    run_scrape_in_subprocess,
)


def _scrape_children() -> set[int | None]:
    return {
        child.pid
        for child in multiprocessing.active_children()
        if child.name == "vks-yt-dlp"
    }


@pytest.mark.asyncio
async def test_subprocess_returns_pickled_result():
    result = await run_scrape_in_subprocess(
        partial(pow, 2, 5),
        timeout_seconds=5,
        terminate_grace_seconds=0.5,
    )
    assert result == 32


@pytest.mark.asyncio
async def test_subprocess_propagates_redacted_failure_type():
    with pytest.raises(ScrapeSubprocessError, match="invalid literal"):
        await run_scrape_in_subprocess(
            partial(int, "not-an-integer"),
            timeout_seconds=5,
            terminate_grace_seconds=0.5,
        )


@pytest.mark.asyncio
async def test_timeout_terminates_stuck_subprocess():
    before = _scrape_children()
    started = time.monotonic()

    with pytest.raises(ScrapeOperationTimeout):
        await run_scrape_in_subprocess(
            partial(time.sleep, 60),
            timeout_seconds=0.2,
            terminate_grace_seconds=0.5,
        )

    assert time.monotonic() - started < 3
    assert _scrape_children() == before


@pytest.mark.asyncio
async def test_cancellation_terminates_stuck_subprocess():
    before = _scrape_children()
    task = asyncio.create_task(
        run_scrape_in_subprocess(
            partial(time.sleep, 60),
            timeout_seconds=60,
            terminate_grace_seconds=0.5,
        )
    )
    await asyncio.sleep(0.2)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert _scrape_children() == before
