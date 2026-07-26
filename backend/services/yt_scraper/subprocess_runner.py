"""Cancelable hard deadlines for synchronous yt-dlp operations."""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import time
from collections.abc import Callable
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Any

from services.yt_scraper.errors import YouTubeAccessBlocked, is_youtube_block_error

logger = logging.getLogger(__name__)


class ScrapeOperationTimeout(TimeoutError):
    """A blocking scrape exceeded its configured hard deadline."""


class ScrapeSubprocessError(RuntimeError):
    """The isolated scrape process failed without a global YouTube block."""


def _operation_worker(sender: Connection, operation: Callable[[], Any]) -> None:
    try:
        sender.send(("ok", operation()))
    except BaseException as exc:
        sender.send(
            (
                "error",
                {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "youtube_blocked": isinstance(exc, YouTubeAccessBlocked)
                    or is_youtube_block_error(exc),
                },
            )
        )
    finally:
        sender.close()


async def _stop_process(process: BaseProcess, grace_seconds: float) -> None:
    if not process.is_alive():
        await asyncio.to_thread(process.join)
        return

    process.terminate()
    await asyncio.to_thread(process.join, grace_seconds)
    if process.is_alive():
        logger.error(
            "Scrape subprocess %s ignored terminate; sending kill",
            process.pid,
        )
        process.kill()
        await asyncio.to_thread(process.join, grace_seconds)


async def run_scrape_in_subprocess(
    operation: Callable[[], Any],
    *,
    timeout_seconds: float,
    terminate_grace_seconds: float,
) -> Any:
    """Run a picklable blocking operation with terminate/kill cancellation."""

    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_operation_worker,
        args=(sender, operation),
        name="vks-yt-dlp",
        daemon=True,
    )
    process.start()
    sender.close()
    deadline = time.monotonic() + timeout_seconds

    try:
        while True:
            try:
                has_result = receiver.poll()
            except (BrokenPipeError, OSError) as exc:
                await asyncio.to_thread(process.join)
                raise ScrapeSubprocessError(
                    "Scrape subprocess closed its result pipe unexpectedly "
                    f"(exit={process.exitcode})"
                ) from exc

            if has_result:
                try:
                    status, payload = await asyncio.to_thread(receiver.recv)
                except EOFError as exc:
                    await asyncio.to_thread(process.join)
                    raise ScrapeSubprocessError(
                        "Scrape subprocess closed its result pipe unexpectedly "
                        f"(exit={process.exitcode})"
                    ) from exc
                await asyncio.to_thread(process.join, terminate_grace_seconds)
                if process.is_alive():
                    await _stop_process(process, terminate_grace_seconds)
                if status == "ok":
                    return payload
                message = payload.get("message") or payload.get("type")
                if payload.get("youtube_blocked"):
                    raise YouTubeAccessBlocked(message)
                raise ScrapeSubprocessError(message)

            if not process.is_alive():
                await asyncio.to_thread(process.join)
                raise ScrapeSubprocessError(
                    "Scrape subprocess exited without a result "
                    f"(exit={process.exitcode})"
                )

            if time.monotonic() >= deadline:
                await _stop_process(process, terminate_grace_seconds)
                raise ScrapeOperationTimeout(
                    f"yt-dlp operation exceeded {timeout_seconds:.1f}s"
                )
            await asyncio.sleep(0.05)
    except asyncio.CancelledError:
        await _stop_process(process, terminate_grace_seconds)
        raise
    finally:
        receiver.close()
        if process.is_alive():
            await _stop_process(process, terminate_grace_seconds)
        if process.is_alive():
            logger.critical(
                "Scrape subprocess %s remained alive after kill deadline",
                process.pid,
            )
        else:
            process.close()
