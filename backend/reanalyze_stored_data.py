"""Dry-run or apply classifier/analyzer upgrades to persisted source data.

Run from ``backend/`` with the normal database environment configured:

    python reanalyze_stored_data.py
    python reanalyze_stored_data.py --apply --requeue-unresolved
    python reanalyze_stored_data.py --include-successful

This command never contacts YouTube. It serializes with the background updater,
reclassifies all videos from stored metadata, and replays saved top comments.
By default, replay only recovers unresolved videos; replacing an existing
successful setlist requires ``--include-successful``. Every mode is a
transactionally rolled-back dry run unless ``--apply`` is also supplied.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import asdict

from container import ApplicationContainer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the reclassification and stored-comment replay.",
    )
    parser.add_argument(
        "--include-successful",
        action="store_true",
        help=(
            "Also rewrite changed successful setlists. By default, replay only "
            "recovers unresolved videos."
        ),
    )
    parser.add_argument(
        "--requeue-unresolved",
        action="store_true",
        help=(
            "Reset still-unresolved karaoke videos for the normal bounded "
            "yt-dlp analysis queue."
        ),
    )
    return parser.parse_args()


async def run(
    container: ApplicationContainer,
    *,
    apply: bool,
    include_successful: bool,
    requeue_unresolved: bool,
) -> dict[str, int | bool]:
    async with container.session_factory() as session:
        service = container.stored_data_reanalyzer(session)
        return asdict(
            await service.run(
                apply=apply,
                include_successful=include_successful,
                requeue_unresolved=requeue_unresolved,
            )
        )


async def main() -> None:
    args = parse_args()
    container = ApplicationContainer.build()
    try:
        result = await run(
            container,
            apply=args.apply,
            include_successful=args.include_successful,
            requeue_unresolved=args.requeue_unresolved,
        )
        mode = "APPLIED" if args.apply else "DRY RUN (rolled back)"
        print(mode)
        for key, value in result.items():
            print(f"{key}: {value}")
    finally:
        await container.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main())
