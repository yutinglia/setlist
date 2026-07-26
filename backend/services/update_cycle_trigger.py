"""Wake the periodic updater when newly committed work should run now."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

_GENERAL_REQUEST = object()


@dataclass(frozen=True)
class UpdateCycleRequest:
    """One coalesced request for an update cycle."""

    priority_channel_id: str | None = None


class UpdateCycleTrigger:
    """Process-local, async wake queue with per-channel de-duplication.

    PostgreSQL remains the durable source of pending backfills. This queue only
    removes the normal worker sleep after a channel is added and carries a hint
    that lets the next bounded cycle process that channel first.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[object] = asyncio.Queue()
        self._queued_channel_ids: set[str] = set()
        self._general_requested = False

    def request(self, *, priority_channel_id: str | None = None) -> bool:
        """Queue a wake-up, returning ``False`` when it was already queued."""
        channel_id = (priority_channel_id or "").strip() or None
        if channel_id is not None:
            if channel_id in self._queued_channel_ids:
                return False
            self._queued_channel_ids.add(channel_id)
            self._queue.put_nowait(channel_id)
            return True

        if self._general_requested:
            return False
        self._general_requested = True
        self._queue.put_nowait(_GENERAL_REQUEST)
        return True

    async def wait(self, timeout_seconds: float) -> UpdateCycleRequest | None:
        """Wait for explicit work, or return ``None`` at the periodic deadline."""
        try:
            item = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            try:
                item = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=max(0.0, timeout_seconds),
                )
            except TimeoutError:
                return None

        if item is _GENERAL_REQUEST:
            self._general_requested = False
            return UpdateCycleRequest()

        channel_id = str(item)
        self._queued_channel_ids.discard(channel_id)
        return UpdateCycleRequest(priority_channel_id=channel_id)

    def clear(self) -> None:
        """Drop process-local wake hints, primarily during app shutdown/tests."""
        while True:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._queued_channel_ids.clear()
        self._general_requested = False


update_cycle_trigger = UpdateCycleTrigger()
