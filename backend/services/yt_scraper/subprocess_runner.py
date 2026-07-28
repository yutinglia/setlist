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


def _closed_pipe_error(process: BaseProcess) -> ScrapeSubprocessError:
    return ScrapeSubprocessError(
        "Scrape subprocess closed its result pipe unexpectedly "
        f"(exit={process.exitcode})"
    )


async def _poll_result(
    receiver: Connection,
    process: BaseProcess,
) -> bool:
    try:
        return receiver.poll()
    except (BrokenPipeError, OSError) as exc:
        await asyncio.to_thread(process.join)
        raise _closed_pipe_error(process) from exc


def _unwrap_result(status: str, payload: Any) -> Any:
    if status == "ok":
        return payload
    message = payload.get("message") or payload.get("type")
    if payload.get("youtube_blocked"):
        raise YouTubeAccessBlocked(message)
    raise ScrapeSubprocessError(message)


async def _receive_result(
    receiver: Connection,
    process: BaseProcess,
    *,
    terminate_grace_seconds: float,
) -> Any:
    try:
        status, payload = await asyncio.to_thread(receiver.recv)
    except EOFError as exc:
        await asyncio.to_thread(process.join)
        raise _closed_pipe_error(process) from exc

    await asyncio.to_thread(process.join, terminate_grace_seconds)
    if process.is_alive():
        await _stop_process(process, terminate_grace_seconds)
    return _unwrap_result(status, payload)


async def _raise_if_process_exited(process: BaseProcess) -> None:
    if process.is_alive():
        return
    await asyncio.to_thread(process.join)
    raise ScrapeSubprocessError(
        f"Scrape subprocess exited without a result (exit={process.exitcode})"
    )


async def _wait_for_result(
    receiver: Connection,
    process: BaseProcess,
    *,
    deadline: float,
    timeout_seconds: float,
    terminate_grace_seconds: float,
) -> Any:
    while True:
        if await _poll_result(receiver, process):
            return await _receive_result(
                receiver,
                process,
                terminate_grace_seconds=terminate_grace_seconds,
            )
        await _raise_if_process_exited(process)
        if time.monotonic() >= deadline:
            await _stop_process(process, terminate_grace_seconds)
            raise ScrapeOperationTimeout(
                f"yt-dlp operation exceeded {timeout_seconds:.1f}s"
            )
        await asyncio.sleep(0.05)


async def _finalize_process(
    receiver: Connection,
    process: BaseProcess,
    *,
    terminate_grace_seconds: float,
) -> None:
    receiver.close()
    if process.is_alive():
        await _stop_process(process, terminate_grace_seconds)
    if process.is_alive():
        logger.critical(
            "Scrape subprocess %s remained alive after kill deadline",
            process.pid,
        )
        return
    process.close()


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
        return await _wait_for_result(
            receiver,
            process,
            deadline=deadline,
            timeout_seconds=timeout_seconds,
            terminate_grace_seconds=terminate_grace_seconds,
        )
    except asyncio.CancelledError:
        await _stop_process(process, terminate_grace_seconds)
        raise
    finally:
        await _finalize_process(
            receiver,
            process,
            terminate_grace_seconds=terminate_grace_seconds,
        )
