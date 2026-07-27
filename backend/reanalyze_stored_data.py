"""Dry-run or apply classifier/analyzer upgrades to persisted source data.

Run from ``backend/`` with the normal database environment configured:

    python reanalyze_stored_data.py
    python reanalyze_stored_data.py --apply

This command never contacts YouTube. It serializes with the background updater,
reclassifies all videos from stored metadata, and replays saved top comments.
The default is a transactionally rolled-back dry run.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import asdict

from config import SCRAPE_POLICY
from db import async_session_factory, engine
from repositories import ChannelRepository, SongRepository, VideoRepository
from services.stored_data_reanalyzer import StoredDataReanalyzer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the reclassification and stored-comment replay.",
    )
    return parser.parse_args()


async def run(*, apply: bool) -> dict[str, int | bool]:
    async with async_session_factory() as session:
        service = StoredDataReanalyzer(
            session,
            ChannelRepository(session),
            VideoRepository(session),
            SongRepository(session),
            max_analysis_attempts=SCRAPE_POLICY.max_analysis_attempts,
        )
        return asdict(await service.run(apply=apply))


async def main() -> None:
    args = parse_args()
    try:
        result = await run(apply=args.apply)
        mode = "APPLIED" if args.apply else "DRY RUN (rolled back)"
        print(mode)
        for key, value in result.items():
            print(f"{key}: {value}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main())
