"""Durable lifecycle and heartbeat handling for one owned updater cycle."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from services.updater_runtime_state import (
    UPDATER_PROCESS_OWNER_ID,
    UpdaterOutcome,
    UpdaterRuntimeStateStore,
)

logger = logging.getLogger(__name__)

CycleOperation = Callable[[], Awaitable[UpdaterOutcome]]


class UpdaterRuntimeLifecycle:
    """Wrap a cycle with owner-guarded durable start/heartbeat/finish state."""

    def __init__(
        self,
        store: UpdaterRuntimeStateStore | None,
        *,
        heartbeat_interval_seconds: float,
    ) -> None:
        self.store = store
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

    async def run(self, operation: CycleOperation) -> None:
        outcome = UpdaterOutcome.ERROR
        started = False
        heartbeat_stop = asyncio.Event()
        heartbeat_task: asyncio.Task[None] | None = None
        try:
            if self.store is not None:
                await self.store.mark_started(UPDATER_PROCESS_OWNER_ID)
                started = True
                heartbeat_task = asyncio.create_task(
                    self._heartbeat_until_stopped(heartbeat_stop)
                )
            outcome = await operation()
        except asyncio.CancelledError:
            outcome = UpdaterOutcome.CANCELLED
            raise
        except BaseException:
            outcome = UpdaterOutcome.ERROR
            raise
        finally:
            heartbeat_stop.set()
            if heartbeat_task is not None:
                await heartbeat_task
            if started:
                await self._finish(outcome)

    async def _heartbeat_until_stopped(self, stop: asyncio.Event) -> None:
        if self.store is None:
            return
        while True:
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=self.heartbeat_interval_seconds,
                )
                return
            except TimeoutError:
                if not await self._write_heartbeat():
                    return

    async def _write_heartbeat(self) -> bool:
        if self.store is None:
            return False
        try:
            owned = await self.store.heartbeat(UPDATER_PROCESS_OWNER_ID)
            if owned:
                return True
            logger.error("Updater heartbeat lost ownership; stopping heartbeat")
        except Exception:
            logger.exception("Could not persist updater heartbeat")
            return True
        return False

    async def _finish(self, outcome: UpdaterOutcome) -> None:
        if self.store is None:
            return
        try:
            await self.store.mark_finished(
                UPDATER_PROCESS_OWNER_ID,
                outcome,
            )
        except Exception:
            logger.exception("Could not persist the updater cycle terminal state")
