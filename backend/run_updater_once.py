"""Run exactly one production-equivalent updater cycle.

Use from ``backend/`` after configuring the same environment variables as
the API. This is intentionally the same DataUpdater path used by the background
worker, making local validation deterministic without shortening production
cadence or leaving a loop running.
"""

from __future__ import annotations

import asyncio
import logging

from container import ApplicationContainer


async def run_once(container: ApplicationContainer) -> None:
    async with container.session_factory() as session:
        await container.data_updater(session).update()


async def main() -> None:
    container = ApplicationContainer.build()
    try:
        await run_once(container)
    finally:
        await container.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main())
