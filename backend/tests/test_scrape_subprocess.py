"""Hard-deadline and cancellation tests for isolated scraper processes."""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import time
from functools import partial

import pytest

from services.yt_scraper.errors import YouTubeAccessBlocked
from services.yt_scraper.subprocess_runner import (
    ScrapeOperationTimeout,
    ScrapeSubprocessError,
    run_scrape_in_subprocess,
)


def _raise_runtime_error(message: str) -> None:
    raise RuntimeError(message)


def _raise_typed_block(message: str) -> None:
    raise YouTubeAccessBlocked(message)


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
@pytest.mark.parametrize(
    "message",
    (
        "Sign in to confirm you're not a bot",
        "HTTP Error 429: Too Many Requests",
        "The current session has been rate-limited by YouTube",
    ),
)
async def test_subprocess_preserves_high_confidence_block_signals(message):
    with pytest.raises(YouTubeAccessBlocked):
        await run_scrape_in_subprocess(
            partial(_raise_runtime_error, message),
            timeout_seconds=5,
            terminate_grace_seconds=0.5,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    (
        "Sign in to confirm your age",
        "HTTP Error 403: Forbidden",
        "Join this channel to get access to members-only content",
    ),
)
async def test_subprocess_keeps_per_video_access_failures_record_local(message):
    with pytest.raises(ScrapeSubprocessError):
        await run_scrape_in_subprocess(
            partial(_raise_runtime_error, message),
            timeout_seconds=5,
            terminate_grace_seconds=0.5,
        )


@pytest.mark.asyncio
async def test_subprocess_preserves_typed_block_with_opaque_message():
    with pytest.raises(YouTubeAccessBlocked):
        await run_scrape_in_subprocess(
            partial(_raise_typed_block, "upstream access guard"),
            timeout_seconds=5,
            terminate_grace_seconds=0.5,
        )


@pytest.mark.asyncio
async def test_abrupt_subprocess_exit_becomes_scrape_error():
    with pytest.raises(ScrapeSubprocessError, match="exit=17"):
        await run_scrape_in_subprocess(
            partial(os._exit, 17),
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
