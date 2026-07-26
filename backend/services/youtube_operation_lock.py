"""Process-local and PostgreSQL-backed exclusion for YouTube operations."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

logger = logging.getLogger(__name__)

# ASCII-ish "VTKARAOK", kept below PostgreSQL's signed BIGINT maximum.
YOUTUBE_OPERATION_ADVISORY_LOCK_ID = 0x56544B4152414F4B

# Fast same-process serialization. The database lock below protects separate
# Uvicorn workers, overlapping deployments, one-shot jobs, and future replicas.
youtube_operation_lock = asyncio.Lock()


class YouTubeUpdaterBusyError(RuntimeError):
    """Another database-connected process currently owns the scraper lock."""


def _session_engine(session: AsyncSession) -> AsyncEngine | None:
    bind = getattr(session, "bind", None)
    if isinstance(bind, AsyncEngine):
        return bind
    # Unit tests use small session doubles. Production always passes the real
    # SQLAlchemy AsyncSession and therefore must have an AsyncEngine binding.
    if not isinstance(session, AsyncSession):
        return None
    raise RuntimeError("Updater AsyncSession is not bound to an AsyncEngine")


@asynccontextmanager
async def postgres_youtube_operation_lock(
    session: AsyncSession,
) -> AsyncIterator[bool]:
    """Try a dedicated session-level advisory lock without waiting.

    The dedicated connection remains open for the complete YouTube operation.
    PostgreSQL releases the lock automatically if the process or connection
    dies. Test session doubles fall back to the process-local lock only.
    """

    engine = _session_engine(session)
    if engine is None:
        yield True
        return

    async with engine.connect() as connection:
        acquired = bool(
            (
                await connection.execute(
                    text("SELECT pg_try_advisory_lock(:lock_id)"),
                    {"lock_id": YOUTUBE_OPERATION_ADVISORY_LOCK_ID},
                )
            ).scalar_one()
        )
        # End the SELECT transaction while retaining the session-level lock.
        await connection.commit()
        if not acquired:
            yield False
            return

        try:
            yield True
        finally:
            try:
                unlocked = bool(
                    (
                        await connection.execute(
                            text("SELECT pg_advisory_unlock(:lock_id)"),
                            {"lock_id": YOUTUBE_OPERATION_ADVISORY_LOCK_ID},
                        )
                    ).scalar_one()
                )
                await connection.commit()
                if not unlocked:
                    logger.error(
                        "PostgreSQL reported the YouTube advisory lock was not owned"
                    )
            except Exception:
                # Closing the dedicated connection below also releases any
                # remaining session-level advisory locks.
                logger.exception("Could not explicitly release YouTube advisory lock")


@asynccontextmanager
async def youtube_operation_guard(
    session: AsyncSession,
) -> AsyncIterator[bool]:
    """Serialize locally, then try the cross-process PostgreSQL lock."""

    async with youtube_operation_lock:
        async with postgres_youtube_operation_lock(session) as acquired:
            yield acquired
