"""PostgreSQL-backed updater lifecycle and heartbeat state."""

from __future__ import annotations

import logging
import os
import socket
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)
UPDATER_PROCESS_OWNER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class UpdaterOutcome(StrEnum):
    NEVER = "never"
    RUNNING = "running"
    SUCCESS = "success"
    COOLDOWN = "cooldown"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class UpdaterRuntimeSnapshot:
    cycle_started_at: datetime | None
    cycle_finished_at: datetime | None
    last_success_at: datetime | None
    heartbeat_at: datetime | None
    outcome: str
    owner_id: str | None

    def is_stalled(
        self,
        *,
        stale_after_seconds: float,
        now: datetime | None = None,
    ) -> bool:
        """Return true only for an unfinished cycle with an expired heartbeat."""
        if self.outcome != UpdaterOutcome.RUNNING.value:
            return False
        if self.heartbeat_at is None:
            return True
        current = now or _utc_now()
        return (current - self.heartbeat_at).total_seconds() > stale_after_seconds


class UpdaterRuntimeStateStore:
    """Write runtime state independently from updater work transactions."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def read(self) -> UpdaterRuntimeSnapshot:
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT
                            updater_cycle_started_at,
                            updater_cycle_finished_at,
                            updater_last_success_at,
                            updater_heartbeat_at,
                            updater_outcome,
                            updater_owner_id
                        FROM scraper_state
                        WHERE id = 1
                        """
                    )
                )
            ).one()
        return UpdaterRuntimeSnapshot(
            cycle_started_at=row.updater_cycle_started_at,
            cycle_finished_at=row.updater_cycle_finished_at,
            last_success_at=row.updater_last_success_at,
            heartbeat_at=row.updater_heartbeat_at,
            outcome=row.updater_outcome,
            owner_id=row.updater_owner_id,
        )

    async def mark_started(self, owner_id: str) -> None:
        now = _utc_now()
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE scraper_state
                    SET
                        updater_cycle_started_at = :now,
                        updater_cycle_finished_at = NULL,
                        updater_heartbeat_at = :now,
                        updater_outcome = 'running',
                        updater_owner_id = :owner_id,
                        updated_at = :now
                    WHERE id = 1
                    """
                ),
                {"now": now, "owner_id": owner_id},
            )

    async def heartbeat(self, owner_id: str) -> bool:
        """Refresh only the cycle still owned by this process."""
        now = _utc_now()
        async with self.engine.begin() as connection:
            result = await connection.execute(
                text(
                    """
                    UPDATE scraper_state
                    SET updater_heartbeat_at = :now, updated_at = :now
                    WHERE
                        id = 1
                        AND updater_outcome = 'running'
                        AND updater_owner_id = :owner_id
                    """
                ),
                {"now": now, "owner_id": owner_id},
            )
        return result.rowcount == 1

    async def mark_finished(
        self,
        owner_id: str,
        outcome: UpdaterOutcome,
    ) -> bool:
        if outcome in {UpdaterOutcome.NEVER, UpdaterOutcome.RUNNING}:
            raise ValueError("A finished updater cycle needs a terminal outcome")

        now = _utc_now()
        success_at = now if outcome is UpdaterOutcome.SUCCESS else None
        async with self.engine.begin() as connection:
            result = await connection.execute(
                text(
                    """
                    UPDATE scraper_state
                    SET
                        updater_cycle_finished_at = :now,
                        updater_last_success_at = COALESCE(
                            :success_at,
                            updater_last_success_at
                        ),
                        updater_heartbeat_at = :now,
                        updater_outcome = :outcome,
                        updated_at = :now
                    WHERE
                        id = 1
                        AND updater_outcome = 'running'
                        AND updater_owner_id = :owner_id
                    """
                ),
                {
                    "now": now,
                    "success_at": success_at,
                    "outcome": outcome.value,
                    "owner_id": owner_id,
                },
            )
        if result.rowcount != 1:
            logger.warning(
                "Updater runtime state was no longer owned by %s at finish",
                owner_id,
            )
            return False
        return True
