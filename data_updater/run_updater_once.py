"""Run exactly one production-equivalent updater cycle.

Use from ``data_updater/`` after configuring the same environment variables as
the API. This is intentionally the same DataUpdater path used by the background
worker, making local validation deterministic without shortening production
cadence or leaving a loop running.
"""

from __future__ import annotations

import asyncio
import logging

from db import async_session_factory, engine
from repositories import ChannelRepository, SongRepository, VideoRepository
from services.data_updater import DataUpdater


async def run_once() -> None:
    async with async_session_factory() as session:
        updater = DataUpdater(
            session,
            ChannelRepository(session),
            VideoRepository(session),
            SongRepository(session),
        )
        await updater.update()


async def main() -> None:
    try:
        await run_once()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main())
