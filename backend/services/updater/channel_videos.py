"""Channel metadata, video discovery, and historical backfill operations."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from functools import partial
from typing import Any

from models.channel import (
    VIDEO_BACKFILL_ACTIVE,
    VIDEO_BACKFILL_DONE,
    VIDEO_BACKFILL_FAILED,
    VIDEO_BACKFILL_RUNNING,
    YouTubeChannel,
)
from models.video import YouTubeVideo
from repositories.channel_repository import ChannelRepository
from repositories.song_repository import SongRepository
from repositories.video_repository import VideoRepository
from services.scrape_policy import ScrapePolicy
from services.scraping import ScraperFactory
from services.updater_status import UpdaterPhase, UpdaterStatusTracker
from services.yt_scraper.errors import raise_if_block_error
from utils.youtube_upload_date import upload_date_from_entry
from utils.ytdlp_snapshot import merged_video_metadata

logger = logging.getLogger(__name__)

ScrapeRunner = Callable[[Callable[[], Any]], Awaitable[Any]]


def prioritize_backfill_channels(
    channels: list[YouTubeChannel],
    *,
    priority_channel_id: str | None = None,
) -> list[YouTubeChannel]:
    """Put an explicitly added channel first, then rotate oldest backfills."""
    active = [
        channel
        for channel in channels
        if channel.video_backfill_status in VIDEO_BACKFILL_ACTIVE
    ]
    priority = [
        channel
        for channel in active
        if priority_channel_id is not None and channel.id == priority_channel_id
    ]
    priority_ids = {channel.id for channel in priority}
    active = [channel for channel in active if channel.id not in priority_ids]

    def oldest_attempt_key(
        channel: YouTubeChannel,
    ) -> tuple[bool, str, str, str]:
        scheduled_at = channel.video_backfill_updated_at or channel.created_at
        return (
            scheduled_at is not None,
            scheduled_at.isoformat() if scheduled_at is not None else "",
            channel.name.casefold(),
            channel.id,
        )

    active.sort(key=oldest_attempt_key)
    active_ids = {channel.id for channel in priority + active}
    inactive = [channel for channel in channels if channel.id not in active_ids]
    return priority + active + inactive


class ChannelVideoService:
    """Own channel refresh, archive discovery, and backfill details."""

    def __init__(
        self,
        channel_repo: ChannelRepository,
        video_repo: VideoRepository,
        song_repo: SongRepository,
        policy: ScrapePolicy,
        status: UpdaterStatusTracker,
        scraper_factory: ScraperFactory,
        run_scrape: ScrapeRunner,
        utc_now: Callable[[], Any],
    ) -> None:
        self.channel_repo = channel_repo
        self.video_repo = video_repo
        self.song_repo = song_repo
        self.policy = policy
        self.status = status
        self.scraper_factory = scraper_factory
        self.run_scrape = run_scrape
        self.utc_now = utc_now

    def scan_is_due(self, channel: YouTubeChannel) -> bool:
        return (
            channel.next_video_scan_at is None
            or channel.next_video_scan_at <= self.utc_now()
        )

    async def reclassify_and_clear(
        self,
        channel: YouTubeChannel,
        video_ids: list[str],
    ) -> None:
        """Reclassify and clean one scraped page in the caller's transaction."""
        if not video_ids:
            return
        self.status.set(
            UpdaterPhase.RECLASSIFYING,
            detail=f"Reclassifying videos for {channel.name}",
            channel_id=channel.id,
            channel_name=channel.name,
        )
        await self.video_repo.reclassify_by_ids(video_ids)
        cleared_ids = await self.video_repo.clear_analysis_for_non_karaoke_by_ids(
            video_ids,
            max_attempts=self.policy.max_analysis_attempts,
        )
        for video_id in cleared_ids:
            await self.song_repo.replace_for_video(video_id, [])
        if cleared_ids:
            logger.info(
                "Channel %s: preserved all archives, cleared derived analysis on %s",
                channel.id,
                len(cleared_ids),
            )

    async def backfill_page(
        self,
        channel: YouTubeChannel,
    ) -> YouTubeChannel | None:
        """Scrape the next playlist window and advance the persisted cursor."""
        page_size = max(1, self.policy.backfill_page_size)
        offset = max(1, channel.video_backfill_offset or 1)
        self.status.set(
            UpdaterPhase.BACKFILLING_VIDEOS,
            detail=(
                f"Backfilling videos for {channel.name} "
                f"(offset={offset}, page={page_size})"
            ),
            channel_id=channel.id,
            channel_name=channel.name,
            clear_video=True,
        )
        scraper = self.scraper_factory.channel_videos(channel.url)
        scrape_page = partial(
            scraper.get_channel_videos_page,
            playlist_start=offset,
            page_size=page_size,
        )

        try:
            page = await self.run_scrape(scrape_page)
        except Exception as exc:
            raise_if_block_error(exc)
            return await self._record_backfill_failure(channel, offset)

        scraped = self._sort_and_bind_videos(channel, page.videos)
        upserted = await self.video_repo.upsert_many(scraped) if scraped else []
        await self.reclassify_and_clear(
            channel,
            [video.id for video in upserted],
        )
        if not page.all_tabs_succeeded:
            return await self._record_partial_backfill(
                channel,
                offset=offset,
                kept_count=len(upserted),
                raw_count=page.raw_entry_count,
                failed_tab_count=len(page.failed_tabs),
            )
        return await self._advance_backfill(
            channel,
            offset=offset,
            page_size=page_size,
            kept_count=len(upserted),
            raw_count=page.raw_entry_count,
            exhausted=page.exhausted,
        )

    async def _record_backfill_failure(
        self,
        channel: YouTubeChannel,
        offset: int,
    ) -> YouTubeChannel | None:
        logger.exception(
            "Backfill page failed for channel %s; scheduling retry",
            channel.id,
        )
        failed = await self.channel_repo.update_video_backfill(
            channel.id,
            status=VIDEO_BACKFILL_FAILED,
            offset=offset,
        )
        self.status.set(
            UpdaterPhase.ERROR,
            detail="Video history backfill failed and will be retried",
            channel_id=channel.id,
            channel_name=channel.name,
            last_error="A video history backfill page failed",
        )
        return failed

    async def _record_partial_backfill(
        self,
        channel: YouTubeChannel,
        *,
        offset: int,
        kept_count: int,
        raw_count: int,
        failed_tab_count: int,
    ) -> YouTubeChannel | None:
        failed = await self.channel_repo.update_video_backfill(
            channel.id,
            status=VIDEO_BACKFILL_FAILED,
            offset=offset,
        )
        logger.warning(
            "Channel %s video backfill partially failed at offset=%s; "
            "kept=%s raw=%s failed_tabs=%s; scheduling retry",
            channel.id,
            offset,
            kept_count,
            raw_count,
            failed_tab_count,
        )
        self.status.set(
            UpdaterPhase.ERROR,
            detail="Part of the video history page failed and will be retried",
            channel_id=channel.id,
            channel_name=channel.name,
            last_error="A channel tab failed during video history backfill",
        )
        return failed

    async def _advance_backfill(
        self,
        channel: YouTubeChannel,
        *,
        offset: int,
        page_size: int,
        kept_count: int,
        raw_count: int,
        exhausted: bool,
    ) -> YouTubeChannel | None:
        next_status = VIDEO_BACKFILL_DONE if exhausted else VIDEO_BACKFILL_RUNNING
        next_offset = offset if exhausted else offset + page_size
        logger.info(
            "Channel %s video backfill %s offset=%s -> %s (kept=%s raw=%s)",
            channel.id,
            "done at" if exhausted else "page",
            offset,
            next_offset,
            kept_count,
            raw_count,
        )
        updated = await self.channel_repo.update_video_backfill(
            channel.id,
            status=next_status,
            offset=next_offset,
        )
        if next_status != VIDEO_BACKFILL_DONE:
            return updated
        return await self.channel_repo.schedule_video_scan(
            channel.id,
            next_scan_at=self.utc_now()
            + timedelta(seconds=self.policy.steady_scan_interval_seconds),
            succeeded=True,
        )

    async def refresh_channel(self, channel: YouTubeChannel) -> YouTubeChannel:
        logger.info("Refreshing channel metadata for %s", channel.url)
        scraper = self.scraper_factory.channel()
        scrape = partial(scraper.get_channel_info, channel.url)

        try:
            scraped = await self.run_scrape(scrape)
        except Exception as exc:
            raise_if_block_error(exc)
            raise

        if scraped.id and scraped.id != channel.id:
            logger.warning(
                "Scraped channel id %s differs from DB id %s; keeping DB id",
                scraped.id,
                channel.id,
            )
            scraped = scraped.model_copy(update={"id": channel.id, "url": channel.url})
        else:
            scraped = scraped.model_copy(update={"id": channel.id})
        return await self.channel_repo.upsert(scraped)

    async def scrape_channel_videos(
        self,
        channel: YouTubeChannel,
        *,
        full_metadata: bool = False,
    ) -> list[YouTubeVideo]:
        """Scrape Streams+Videos tabs and retain every normal archive."""
        scraper = self.scraper_factory.channel_videos(
            channel.url,
            max_videos=self.policy.recent_videos_per_channel,
            full_metadata=full_metadata,
            metadata_limit=self.policy.metadata_scrapes_per_refresh,
        )
        try:
            scraped = await self.run_scrape(scraper.get_channel_videos)
        except Exception as exc:
            raise_if_block_error(exc)
            raise

        sorted_videos = self._sort_and_bind_videos(channel, scraped)
        logger.info(
            "Channel %s: retained %s normal archive record(s) (full_metadata=%s)",
            channel.id,
            len(sorted_videos),
            full_metadata,
        )
        return sorted_videos

    async def scrape_and_upsert_videos(
        self,
        channel: YouTubeChannel,
        *,
        full_metadata: bool = False,
    ) -> list[YouTubeVideo]:
        scraped = await self.scrape_channel_videos(
            channel,
            full_metadata=full_metadata,
        )
        return await self.video_repo.upsert_many(scraped)

    @staticmethod
    def _sort_and_bind_videos(
        channel: YouTubeChannel,
        videos: list[YouTubeVideo],
    ) -> list[YouTubeVideo]:
        sorted_videos = sorted(
            videos,
            key=lambda video: (
                video.upload_date
                or upload_date_from_entry(
                    merged_video_metadata(
                        video.raw_data,
                        video.metadata_raw_data,
                    )
                )
                or ""
            ),
            reverse=True,
        )
        for video in sorted_videos:
            video.channel_id = channel.id
        return sorted_videos
