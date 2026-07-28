"""Per-channel cycle scheduling around focused channel-video operations."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta

from models.channel import (
    VIDEO_BACKFILL_ACTIVE,
    VIDEO_BACKFILL_RUNNING,
    YouTubeChannel,
)
from models.video import YouTubeVideo
from repositories.channel_repository import ChannelRepository
from services.scrape_policy import ScrapePolicy
from services.updater.channel_videos import ChannelVideoService
from services.updater.models import CycleProgress
from services.updater_status import UpdaterPhase, UpdaterStatusTracker
from services.yt_scraper.errors import YouTubeAccessBlocked

logger = logging.getLogger(__name__)

AsyncAction = Callable[[], Awaitable[None]]
BackfillPage = Callable[
    [YouTubeChannel],
    Awaitable[YouTubeChannel | None],
]


class ChannelCycleService:
    """Schedule one channel's bounded backfill or steady-state discovery work."""

    def __init__(
        self,
        channel_repo: ChannelRepository,
        channel_videos: ChannelVideoService,
        policy: ScrapePolicy,
        status: UpdaterStatusTracker,
        progress: CycleProgress,
        *,
        commit: AsyncAction,
        list_pause: AsyncAction,
        backfill_page: BackfillPage,
    ) -> None:
        self.channel_repo = channel_repo
        self.channel_videos = channel_videos
        self.policy = policy
        self.status = status
        self.progress = progress
        self.commit = commit
        self.list_pause = list_pause
        self.backfill_page = backfill_page

    async def process(self, channel: YouTubeChannel) -> bool:
        """Process one channel and report uncommitted public-data changes."""
        logger.info("Processing channel %s (%s)", channel.name, channel.id)
        self.status.set(
            UpdaterPhase.REFRESHING_CHANNEL,
            detail=f"Processing channel {channel.name}",
            channel_id=channel.id,
            channel_name=channel.name,
            clear_video=True,
            comment_scrapes_this_cycle=self.progress.comment_scrapes,
        )
        channel, public_data_changed = await self._refresh_if_needed(channel)
        if channel.video_backfill_status in VIDEO_BACKFILL_ACTIVE:
            committed = await self._process_backfill_pages(channel)
            return public_data_changed and not committed

        videos, scan_changed_public_data = await self._process_steady_scan(channel)
        if videos:
            await self.channel_videos.reclassify_and_clear(
                channel,
                [video.id for video in videos],
            )
        return public_data_changed or scan_changed_public_data

    async def _refresh_if_needed(
        self,
        channel: YouTubeChannel,
    ) -> tuple[YouTubeChannel, bool]:
        if channel.raw_data is not None:
            return channel, False
        self.status.set(
            UpdaterPhase.REFRESHING_CHANNEL,
            detail=f"Refreshing channel metadata for {channel.name}",
            channel_id=channel.id,
            channel_name=channel.name,
        )
        return await self.channel_videos.refresh_channel(channel), True

    async def _process_backfill_pages(
        self,
        channel: YouTubeChannel,
    ) -> bool:
        if self.progress.backfill_channels >= self.policy.backfill_channels_per_cycle:
            logger.info(
                "Backfill channel cap reached (%s); deferring video backfill for %s",
                self.policy.backfill_channels_per_cycle,
                channel.id,
            )
            return False

        self.progress.backfill_channels += 1
        committed = False
        for page_index in range(self.policy.backfill_pages_per_cycle):
            if page_index:
                await self.list_pause()
            refreshed = await self.backfill_page(channel)
            await self.commit()
            committed = True
            if refreshed is None:
                return committed
            channel = refreshed
            if channel.video_backfill_status != VIDEO_BACKFILL_RUNNING:
                return committed
        return committed

    async def _process_steady_scan(
        self,
        channel: YouTubeChannel,
    ) -> tuple[list[YouTubeVideo] | None, bool]:
        if not self.channel_videos.scan_is_due(channel):
            return None, False
        if self.progress.steady_channels >= self.policy.steady_channels_per_cycle:
            return None, False

        self.progress.steady_channels += 1
        self.status.set(
            UpdaterPhase.SCRAPING_VIDEOS,
            detail=f"Checking recent archives for {channel.name}",
            channel_id=channel.id,
            channel_name=channel.name,
            clear_video=True,
        )
        try:
            videos = await self.channel_videos.scrape_and_upsert_videos(channel)
        except YouTubeAccessBlocked:
            raise
        except Exception:
            await self._schedule_scan_retry(channel)
            return None, True

        await self.channel_repo.schedule_video_scan(
            channel.id,
            next_scan_at=self.channel_videos.utc_now()
            + timedelta(seconds=self.policy.steady_scan_interval_seconds),
            succeeded=True,
        )
        if not videos:
            logger.info("No normal archive records found for %s", channel.id)
        return videos, True

    async def _schedule_scan_retry(self, channel: YouTubeChannel) -> None:
        failures = max(0, channel.video_scan_failures) + 1
        retry_seconds = min(
            self.policy.steady_scan_interval_seconds,
            self.policy.steady_retry_base_seconds * (2 ** min(failures - 1, 5)),
        )
        await self.channel_repo.schedule_video_scan(
            channel.id,
            next_scan_at=self.channel_videos.utc_now()
            + timedelta(seconds=retry_seconds),
            succeeded=False,
        )
        logger.exception(
            "Recent archive scan failed for %s; retry in %ss",
            channel.id,
            retry_seconds,
        )
        self.status.set(
            UpdaterPhase.ERROR,
            detail="Recent archive scan failed and was rescheduled",
            channel_id=channel.id,
            channel_name=channel.name,
            last_error="A channel discovery scan failed",
        )
