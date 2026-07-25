"""DataUpdater: scrape → analyze → persist with Tier B YouTube pacing."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    BACKGROUND_UPDATER_ENABLED,
    LLM_API_KEY,
    LLM_CLEANING_ENABLED,
    LLM_MAX_CLEANING_ATTEMPTS,
    LLM_MODEL,
    UPDATE_BACKFILL_CHANNELS_PER_CYCLE,
    UPDATE_BACKFILL_PAGE_SIZE,
    UPDATE_MAX_ANALYZE_ATTEMPTS,
    UPDATE_MAX_COMMENT_SCRAPES,
    UPDATE_MAX_COMMENTS_PER_VIDEO,
    UPDATE_MAX_METADATA_SCRAPES,
    UPDATE_MAX_VIDEOS,
    UPDATE_SCRAPE_SLEEP_MAX,
    UPDATE_SCRAPE_SLEEP_MIN,
    UPDATE_YOUTUBE_COOLDOWN_SECONDS,
    YTDLP_COMMENT_MAX_SLEEP_INTERVAL,
    YTDLP_COMMENT_SLEEP_INTERVAL,
)
from models.channel import (
    VIDEO_BACKFILL_ACTIVE,
    VIDEO_BACKFILL_DONE,
    VIDEO_BACKFILL_FAILED,
    VIDEO_BACKFILL_RUNNING,
    YouTubeChannel,
)
from models.song import Song
from models.video import YouTubeVideo
from repositories.channel_repository import ChannelRepository
from repositories.song_repository import SongRepository
from repositories.video_repository import VideoRepository
from services.analyzer.llm_cleaner import maybe_clean_song_list_comment
from services.analyzer.yt_comment_analyzer import CommentAnalyzer
from services.updater_status import UpdaterPhase, updater_status
from services.yt_scraper.channel_scraper import YouTubeChannelScraper
from services.yt_scraper.channel_video_scraper import YouTubeChannelVideoScraper
from services.yt_scraper.errors import (
    YouTubeAccessBlocked,
    is_youtube_block_error,
    raise_if_block_error,
)
from services.yt_scraper.video_comment_scraper import YouTubeVideoCommentScraper
from utils.video_type import PERSISTED_VIDEO_TYPES, should_scrape_comments
from utils.youtube_upload_date import upload_date_from_entry


@dataclass(frozen=True)
class ChannelVideoRefreshResult:
    """Outcome of a manual, non-destructive channel video-list refresh."""

    channel_id: str
    mode: str  # "refresh"
    scraped: int
    deleted: int  # Backward-compatible response field; always zero.
    reclassified: int
    cleared: int
    message: str


logger = logging.getLogger(__name__)

# One process must not run the periodic updater and manual scraper operations at
# the same time. Deployments should still use one Uvicorn worker because this
# lock and the cooldown are intentionally process-local.
youtube_operation_lock = asyncio.Lock()


class DataUpdater:
    """負責資料更新的業務邏輯.

    Owns commit/rollback for the given session (commit per channel).
    Pipeline: channel → videos → comments → CommentAnalyzer → songs.
    """

    # In-memory YouTube cooldown (process-local; Tier B v1).
    _youtube_cooldown_until: float | None = None

    def __init__(
        self,
        session: AsyncSession,
        channel_repo: ChannelRepository,
        video_repo: VideoRepository,
        song_repo: SongRepository,
    ):
        self.session = session
        self.channel_repo = channel_repo
        self.video_repo = video_repo
        self.song_repo = song_repo
        self._comment_scrapes_this_cycle = 0
        self._backfill_channels_this_cycle = 0

    @classmethod
    def youtube_cooldown_remaining(cls) -> float:
        """Seconds left on YouTube cooldown, or 0 if clear."""
        if cls._youtube_cooldown_until is None:
            return 0.0
        remaining = cls._youtube_cooldown_until - time.monotonic()
        if remaining <= 0:
            cls._youtube_cooldown_until = None
            return 0.0
        return remaining

    @classmethod
    def set_youtube_cooldown(cls, seconds: float | None = None) -> None:
        seconds = UPDATE_YOUTUBE_COOLDOWN_SECONDS if seconds is None else seconds
        cls._youtube_cooldown_until = time.monotonic() + max(0.0, seconds)
        logger.warning(
            "YouTube cooldown set for %ss (until monotonic+%.0f)",
            seconds,
            seconds,
        )

    async def update(self) -> None:
        async with youtube_operation_lock:
            await self._update_without_lock()

    async def _update_without_lock(self) -> None:
        remaining = self.youtube_cooldown_remaining()
        if remaining > 0:
            logger.warning(
                "Skipping update cycle: YouTube cooldown active (%.0fs remaining)",
                remaining,
            )
            updater_status.set(
                UpdaterPhase.COOLDOWN,
                detail=f"YouTube cooldown active ({remaining:.0f}s remaining)",
                clear_channel=True,
                clear_video=True,
            )
            return

        self._comment_scrapes_this_cycle = 0
        self._backfill_channels_this_cycle = 0
        updater_status.begin_cycle()
        logger.info(
            "Starting update cycle (max_videos=%s, max_comment_scrapes=%s, "
            "backfill_page=%s, backfill_channels=%s, jitter=%.1f–%.1fs, "
            "max_attempts=%s)",
            UPDATE_MAX_VIDEOS,
            UPDATE_MAX_COMMENT_SCRAPES,
            UPDATE_BACKFILL_PAGE_SIZE,
            UPDATE_BACKFILL_CHANNELS_PER_CYCLE,
            UPDATE_SCRAPE_SLEEP_MIN,
            UPDATE_SCRAPE_SLEEP_MAX,
            UPDATE_MAX_ANALYZE_ATTEMPTS,
        )

        try:
            updater_status.set(
                UpdaterPhase.FETCHING_CHANNELS,
                detail="Loading channels from database",
                clear_channel=True,
                clear_video=True,
            )
            channels = await self.channel_repo.get_all()
            channels = self._prioritize_backfill_channels(channels)
            logger.info("Fetched %s channels from the database.", len(channels))

            for channel in channels:
                if self.youtube_cooldown_remaining() > 0:
                    logger.warning(
                        "Cooldown active mid-cycle; stopping remaining channels"
                    )
                    remaining = self.youtube_cooldown_remaining()
                    updater_status.set(
                        UpdaterPhase.COOLDOWN,
                        detail=(
                            f"YouTube cooldown mid-cycle ({remaining:.0f}s remaining)"
                        ),
                        clear_channel=True,
                        clear_video=True,
                    )
                    break
                try:
                    await self._process_channel(channel)
                    updater_status.set(
                        UpdaterPhase.COMMITTING,
                        detail=f"Committing updates for {channel.name}",
                        channel_id=channel.id,
                        channel_name=channel.name,
                        clear_video=True,
                    )
                    await self.session.commit()
                    logger.info("Committed updates for channel %s", channel.id)
                except YouTubeAccessBlocked as exc:
                    logger.warning(
                        "YouTube block while processing channel %s: %s",
                        channel.id,
                        exc,
                    )
                    await self.session.commit()
                    self.set_youtube_cooldown()
                    updater_status.set(
                        UpdaterPhase.COOLDOWN,
                        detail="YouTube temporarily blocked scraper requests",
                        channel_id=channel.id,
                        channel_name=channel.name,
                        last_error="YouTube access was temporarily blocked",
                    )
                    break
                except Exception:
                    await self.session.rollback()
                    logger.exception(
                        "Non-block failure for channel %s; continuing", channel.id
                    )
                    updater_status.set(
                        UpdaterPhase.ERROR,
                        detail=(
                            "Channel processing failed; continuing with next channel"
                        ),
                        channel_id=channel.id,
                        channel_name=channel.name,
                        last_error="A channel update failed",
                    )
            remaining = self.youtube_cooldown_remaining()
            if remaining > 0:
                updater_status.end_cycle(
                    phase=UpdaterPhase.COOLDOWN,
                    detail=f"YouTube cooldown ({remaining:.0f}s remaining)",
                )
            else:
                updater_status.end_cycle()
        except Exception:
            await self.session.rollback()
            updater_status.end_cycle(error="The update cycle failed")
            raise

    @staticmethod
    def _prioritize_backfill_channels(
        channels: list[YouTubeChannel],
    ) -> list[YouTubeChannel]:
        """Round-robin active backfills by their oldest persisted attempt time."""
        active = [
            channel
            for channel in channels
            if channel.video_backfill_status in VIDEO_BACKFILL_ACTIVE
        ]

        def _oldest_attempt_key(
            channel: YouTubeChannel,
        ) -> tuple[bool, str, str, str]:
            scheduled_at = channel.video_backfill_updated_at or channel.created_at
            return (
                scheduled_at is not None,
                scheduled_at.isoformat() if scheduled_at is not None else "",
                channel.name.casefold(),
                channel.id,
            )

        active.sort(key=_oldest_attempt_key)
        active_ids = {channel.id for channel in active}
        return active + [
            channel for channel in channels if channel.id not in active_ids
        ]

    async def refresh_channel_video_list(
        self, channel: YouTubeChannel
    ) -> ChannelVideoRefreshResult:
        async with youtube_operation_lock:
            try:
                result = await self._refresh_channel_video_list_without_lock(channel)
                # Keep the process-local YouTube lock until the transaction is
                # visible; otherwise the periodic updater can race this session.
                await self.session.commit()
                return result
            except asyncio.CancelledError:
                await self.session.rollback()
                updater_status.set(
                    self._manual_operation_resting_phase(),
                    detail="Manual video refresh was cancelled",
                    clear_channel=True,
                    clear_video=True,
                )
                raise
            except YouTubeAccessBlocked:
                await self.session.rollback()
                raise
            except Exception:
                await self.session.rollback()
                updater_status.set(
                    UpdaterPhase.ERROR,
                    detail=f"Could not refresh video metadata for {channel.name}",
                    channel_id=channel.id,
                    channel_name=channel.name,
                    clear_video=True,
                    last_error="A manual video metadata refresh failed",
                )
                raise
            except BaseException:
                await self.session.rollback()
                raise

    @staticmethod
    def _manual_operation_resting_phase() -> UpdaterPhase:
        return UpdaterPhase.WAITING if BACKGROUND_UPDATER_ENABLED else UpdaterPhase.IDLE

    async def _refresh_channel_video_list_without_lock(
        self, channel: YouTubeChannel
    ) -> ChannelVideoRefreshResult:
        """Refresh metadata without deleting videos or extracted songs.

        Flat tab lists often omit ``upload_date``, so this performs a bounded
        full-metadata enrichment and upserts the result. Older videos not present
        in the bounded scrape are intentionally preserved.

        Does **not** scrape comments / setlists.
        """
        remaining = self.youtube_cooldown_remaining()
        if remaining > 0:
            updater_status.set(
                UpdaterPhase.COOLDOWN,
                detail=f"YouTube cooldown active ({remaining:.0f}s remaining)",
                channel_id=channel.id,
                channel_name=channel.name,
                clear_video=True,
            )
            raise YouTubeAccessBlocked(
                f"YouTube cooldown active ({remaining:.0f}s remaining)"
            )

        updater_status.set(
            UpdaterPhase.SCRAPING_VIDEOS,
            detail=f"Refreshing video metadata for {channel.name}",
            channel_id=channel.id,
            channel_name=channel.name,
            clear_video=True,
            clear_error=True,
        )

        try:
            scraped = await self._scrape_channel_videos(channel, full_metadata=True)
        except YouTubeAccessBlocked:
            self.set_youtube_cooldown()
            updater_status.set(
                UpdaterPhase.COOLDOWN,
                detail=f"YouTube blocked while refreshing {channel.name}",
                channel_id=channel.id,
                channel_name=channel.name,
            )
            raise
        except Exception:
            updater_status.set(
                UpdaterPhase.ERROR,
                detail=f"Could not refresh video metadata for {channel.name}",
                channel_id=channel.id,
                channel_name=channel.name,
                clear_video=True,
                last_error="A manual video metadata refresh failed",
            )
            raise

        videos = await self.video_repo.upsert_many(scraped)
        scraped_count = len(videos)

        logger.info(
            "Channel %s safe metadata refresh done scraped=%s",
            channel.id,
            scraped_count,
        )
        updater_status.set(
            self._manual_operation_resting_phase(),
            detail=f"Safe metadata refresh finished for {channel.name}",
            channel_id=channel.id,
            channel_name=channel.name,
            clear_video=True,
        )
        return ChannelVideoRefreshResult(
            channel_id=channel.id,
            mode="refresh",
            scraped=scraped_count,
            deleted=0,
            reclassified=0,
            cleared=0,
            message=(
                f"Refreshed {scraped_count} recent video(s) without deleting "
                "videos, comments, or existing setlists."
            ),
        )

    async def _process_channel(self, channel: YouTubeChannel) -> None:
        logger.info("Processing channel %s (%s)", channel.name, channel.id)
        updater_status.set(
            UpdaterPhase.REFRESHING_CHANNEL,
            detail=f"Processing channel {channel.name}",
            channel_id=channel.id,
            channel_name=channel.name,
            clear_video=True,
            comment_scrapes_this_cycle=self._comment_scrapes_this_cycle,
        )

        # Optional metadata refresh when seed row has no raw_data yet.
        if channel.raw_data is None:
            updater_status.set(
                UpdaterPhase.REFRESHING_CHANNEL,
                detail=f"Refreshing channel metadata for {channel.name}",
                channel_id=channel.id,
                channel_name=channel.name,
            )
            channel = await self._refresh_channel(channel)

        backfill_active = channel.video_backfill_status in VIDEO_BACKFILL_ACTIVE
        if backfill_active:
            if self._backfill_channels_this_cycle >= UPDATE_BACKFILL_CHANNELS_PER_CYCLE:
                logger.info(
                    "Backfill channel cap reached (%s); "
                    "deferring video backfill for %s",
                    UPDATE_BACKFILL_CHANNELS_PER_CYCLE,
                    channel.id,
                )
            else:
                if self._backfill_channels_this_cycle > 0:
                    await self._jitter_sleep()
                await self._backfill_channel_video_page(channel)
                self._backfill_channels_this_cycle += 1
                # Reload cursor/status after backfill write.
                refreshed = await self.channel_repo.get_by_id(channel.id)
                if refreshed is not None:
                    channel = refreshed
        else:
            updater_status.set(
                UpdaterPhase.SCRAPING_VIDEOS,
                detail=f"Scraping video list for {channel.name}",
                channel_id=channel.id,
                channel_name=channel.name,
                clear_video=True,
            )
            videos = await self._scrape_and_upsert_videos(channel)
            if not videos:
                logger.info("No videos to consider for channel %s", channel.id)

        # Keep types aligned; drop chatter/other; clear stray song analysis.
        updater_status.set(
            UpdaterPhase.RECLASSIFYING,
            detail=f"Reclassifying videos for {channel.name}",
            channel_id=channel.id,
            channel_name=channel.name,
        )
        await self.video_repo.reclassify_for_channel(channel.id)
        deleted = await self.video_repo.delete_non_persisted_for_channel(
            channel.id, reclassify=False
        )
        cleared_ids = await self.video_repo.clear_analysis_for_non_karaoke(
            channel.id,
            max_attempts=UPDATE_MAX_ANALYZE_ATTEMPTS,
        )
        for video_id in cleared_ids:
            await self.song_repo.replace_for_video(video_id, [])
        if deleted or cleared_ids:
            logger.info(
                "Channel %s: deleted %s other video(s), cleared analysis on %s",
                channel.id,
                deleted,
                len(cleared_ids),
            )

        remaining_scrapes = (
            UPDATE_MAX_COMMENT_SCRAPES - self._comment_scrapes_this_cycle
        )
        if remaining_scrapes <= 0:
            return

        needing = await self.video_repo.get_needing_analysis(
            channel.id,
            max_attempts=UPDATE_MAX_ANALYZE_ATTEMPTS,
            limit=min(remaining_scrapes, UPDATE_MAX_VIDEOS),
        )
        logger.info(
            "Channel %s: %s video(s) need analysis (cap this pass=%s)",
            channel.id,
            len(needing),
            remaining_scrapes,
        )

        for video in needing:
            if self._comment_scrapes_this_cycle >= UPDATE_MAX_COMMENT_SCRAPES:
                logger.info(
                    "Hit UPDATE_MAX_COMMENT_SCRAPES=%s; stopping comment scrapes",
                    UPDATE_MAX_COMMENT_SCRAPES,
                )
                break

            try:
                await self._analyze_video(video)
            except YouTubeAccessBlocked:
                raise
            except Exception:
                logger.exception(
                    "Non-block failure analyzing video %s; continuing", video.id
                )
                updater_status.set(
                    UpdaterPhase.ERROR,
                    detail="Video analysis failed; continuing with the next video",
                    channel_id=channel.id,
                    channel_name=channel.name,
                    video_id=video.id,
                    video_title=video.title,
                    last_error="A video analysis failed",
                )

    async def _backfill_channel_video_page(self, channel: YouTubeChannel) -> None:
        """Scrape the next playlist window and advance the persisted cursor."""
        page_size = max(1, UPDATE_BACKFILL_PAGE_SIZE)
        offset = max(1, channel.video_backfill_offset or 1)
        updater_status.set(
            UpdaterPhase.BACKFILLING_VIDEOS,
            detail=(
                f"Backfilling videos for {channel.name} "
                f"(offset={offset}, page={page_size})"
            ),
            channel_id=channel.id,
            channel_name=channel.name,
            clear_video=True,
        )

        def _scrape_page():
            return YouTubeChannelVideoScraper(channel.url).get_channel_videos_page(
                playlist_start=offset,
                page_size=page_size,
            )

        try:
            page = await asyncio.to_thread(_scrape_page)
        except Exception as exc:
            raise_if_block_error(exc)
            logger.exception(
                "Backfill page failed for channel %s; scheduling retry", channel.id
            )
            await self.channel_repo.update_video_backfill(
                channel.id,
                status=VIDEO_BACKFILL_FAILED,
                offset=offset,
            )
            updater_status.set(
                UpdaterPhase.ERROR,
                detail="Video history backfill failed and will be retried",
                channel_id=channel.id,
                channel_name=channel.name,
                last_error="A video history backfill page failed",
            )
            return

        # Prefer recent uploads across Streams + Videos; empty dates sort last.
        scraped_sorted = sorted(
            page.videos,
            key=lambda v: (
                v.upload_date
                or upload_date_from_entry(
                    v.raw_data if isinstance(v.raw_data, dict) else None
                )
                or ""
            ),
            reverse=True,
        )
        persisted = [
            v for v in scraped_sorted if (v.type or "") in PERSISTED_VIDEO_TYPES
        ]
        for video in persisted:
            video.channel_id = channel.id

        upserted = await self.video_repo.upsert_many(persisted) if persisted else []
        if not page.all_tabs_succeeded:
            # Saving the usable rows is safe, but advancing would permanently
            # skip the failed tab's current window.
            await self.channel_repo.update_video_backfill(
                channel.id,
                status=VIDEO_BACKFILL_FAILED,
                offset=offset,
            )
            logger.warning(
                "Channel %s video backfill partially failed at offset=%s; "
                "kept=%s raw=%s failed_tabs=%s; scheduling retry",
                channel.id,
                offset,
                len(upserted),
                page.raw_entry_count,
                len(page.failed_tabs),
            )
            updater_status.set(
                UpdaterPhase.ERROR,
                detail="Part of the video history page failed and will be retried",
                channel_id=channel.id,
                channel_name=channel.name,
                last_error="A channel tab failed during video history backfill",
            )
            return

        if page.exhausted:
            next_status = VIDEO_BACKFILL_DONE
            next_offset = offset
            logger.info(
                "Channel %s video backfill done at offset=%s (page kept=%s raw=%s)",
                channel.id,
                offset,
                len(upserted),
                page.raw_entry_count,
            )
        else:
            next_status = VIDEO_BACKFILL_RUNNING
            next_offset = offset + page_size
            logger.info(
                "Channel %s video backfill page offset=%s -> %s (kept=%s raw=%s)",
                channel.id,
                offset,
                next_offset,
                len(upserted),
                page.raw_entry_count,
            )

        await self.channel_repo.update_video_backfill(
            channel.id,
            status=next_status,
            offset=next_offset,
        )

    async def _refresh_channel(self, channel: YouTubeChannel) -> YouTubeChannel:
        logger.info("Refreshing channel metadata for %s", channel.url)

        def _scrape() -> YouTubeChannel:
            return YouTubeChannelScraper().get_channel_info(channel.url)

        try:
            scraped = await asyncio.to_thread(_scrape)
        except Exception as exc:
            raise_if_block_error(exc)
            raise

        # Keep the seeded primary key if scrape returns a different playlist id.
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

    async def _scrape_channel_videos(
        self,
        channel: YouTubeChannel,
        *,
        full_metadata: bool = False,
    ) -> list[YouTubeVideo]:
        """Scrape Streams+Videos tabs; return song/karaoke rows (newest first)."""

        def _scrape() -> list[YouTubeVideo]:
            return YouTubeChannelVideoScraper(
                channel.url,
                max_videos=UPDATE_MAX_VIDEOS,
                full_metadata=full_metadata,
                metadata_limit=UPDATE_MAX_METADATA_SCRAPES,
            ).get_channel_videos()

        try:
            scraped = await asyncio.to_thread(_scrape)
        except Exception as exc:
            raise_if_block_error(exc)
            raise

        # Prefer recent uploads across Streams + Videos; empty dates sort last.
        scraped_sorted = sorted(
            scraped,
            key=lambda v: (
                v.upload_date
                or upload_date_from_entry(
                    v.raw_data if isinstance(v.raw_data, dict) else None
                )
                or ""
            ),
            reverse=True,
        )
        # Only persist song + karaoke stream records (drop chatter / other).
        persisted = [
            v for v in scraped_sorted if (v.type or "") in PERSISTED_VIDEO_TYPES
        ]
        limited = persisted[:UPDATE_MAX_VIDEOS]
        logger.info(
            "Channel %s: scraped %s, kept %s song/karaoke (full_metadata=%s)",
            channel.id,
            len(scraped),
            len(limited),
            full_metadata,
        )

        for video in limited:
            # Flat extracts sometimes omit channel_id; bind to the DB channel.
            video.channel_id = channel.id

        return limited

    async def _scrape_and_upsert_videos(
        self,
        channel: YouTubeChannel,
        *,
        full_metadata: bool = False,
    ) -> list[YouTubeVideo]:
        limited = await self._scrape_channel_videos(
            channel, full_metadata=full_metadata
        )
        return await self.video_repo.upsert_many(limited)

    async def _analyze_video(self, video: YouTubeVideo) -> None:
        # Re-check from title + raw_data: song/MV/cover must never scrape comments.
        raw = video.raw_data if isinstance(video.raw_data, dict) else {}
        if not should_scrape_comments(
            video.title or "",
            live_status=raw.get("live_status"),
            duration=raw.get("duration"),
            stored_type=video.type,
        ):
            logger.info(
                "Skipping comment analysis for %s video %s (%s)",
                video.type or "unknown",
                video.id,
                video.title,
            )
            return

        if self._comment_scrapes_this_cycle > 0:
            await self._jitter_sleep()
        self._comment_scrapes_this_cycle += 1
        logger.info(
            "Comment scrape %s/%s for karaoke stream %s (%s)",
            self._comment_scrapes_this_cycle,
            UPDATE_MAX_COMMENT_SCRAPES,
            video.id,
            video.title,
        )
        updater_status.set(
            UpdaterPhase.SCRAPING_COMMENTS,
            detail=(
                f"Scraping comments "
                f"({self._comment_scrapes_this_cycle}/{UPDATE_MAX_COMMENT_SCRAPES})"
            ),
            video_id=video.id,
            video_title=video.title,
            comment_scrapes_this_cycle=self._comment_scrapes_this_cycle,
        )

        def _scrape_comments() -> list:
            scraper = YouTubeVideoCommentScraper(
                video.url,
                sleep_interval=YTDLP_COMMENT_SLEEP_INTERVAL,
                max_sleep_interval=YTDLP_COMMENT_MAX_SLEEP_INTERVAL,
            )
            return scraper.get_video_top_comments(UPDATE_MAX_COMMENTS_PER_VIDEO)

        now = datetime.now(UTC).replace(tzinfo=None)
        attempts = (video.analyze_attempts or 0) + 1

        try:
            comments = await asyncio.to_thread(_scrape_comments)
        except Exception as exc:
            video.analyze_attempts = attempts
            video.last_analyzed_at = now
            await self.video_repo.update_analysis(video)
            if isinstance(exc, YouTubeAccessBlocked) or is_youtube_block_error(exc):
                raise YouTubeAccessBlocked(str(exc)) from exc
            raise

        video.comments_raw_data = {"comments": comments}
        video.analyze_attempts = attempts
        video.last_analyzed_at = now

        updater_status.set(
            UpdaterPhase.ANALYZING,
            detail="Analyzing comments for setlist",
            video_id=video.id,
            video_title=video.title,
            comment_scrapes_this_cycle=self._comment_scrapes_this_cycle,
        )
        analyzer = CommentAnalyzer(comments, video_id=video.id)
        if analyzer.has_song_list_comment():
            songs = analyzer.extract_song_list()
            if songs:
                video.has_song_list_comment = True
                video.song_list_comment_raw_data = analyzer.song_list_comment
                # This analysis is authoritative; never retain an older LLM
                # payload if the current cleaning pass is skipped or fails.
                video.cleaned_song_list_comment = None
                songs = await self._maybe_llm_clean(video, analyzer, songs)
                await self.song_repo.replace_for_video(video.id, songs)
                logger.info(
                    "Video %s: found setlist with %s song(s)", video.id, len(songs)
                )
            else:
                video.has_song_list_comment = False
                video.song_list_comment_raw_data = None
                video.cleaned_song_list_comment = None
                video.cleaning_attempts = 0
                video.last_cleaned_at = None
                await self.song_repo.replace_for_video(video.id, [])
                logger.info(
                    "Video %s: timestamp comment had no parseable songs", video.id
                )
        else:
            video.has_song_list_comment = False
            video.song_list_comment_raw_data = None
            video.cleaned_song_list_comment = None
            video.cleaning_attempts = 0
            video.last_cleaned_at = None
            # Re-analysis is authoritative: a successful "no setlist" result
            # must not leave songs from an older analysis behind.
            await self.song_repo.replace_for_video(video.id, [])
            logger.info("Video %s: no setlist comment found", video.id)

        await self.video_repo.update_analysis(video)

    async def _maybe_llm_clean(
        self,
        video: YouTubeVideo,
        analyzer: CommentAnalyzer,
        songs: list[Song],
    ) -> list[Song]:
        """Optionally LLM-clean the setlist; keep regex songs on skip/failure."""
        if not LLM_CLEANING_ENABLED:
            return songs

        if not LLM_API_KEY:
            logger.warning(
                "LLM_CLEANING_ENABLED set but LLM_API_KEY empty; skipping clean"
            )
            return songs

        attempts = video.cleaning_attempts or 0
        if attempts >= LLM_MAX_CLEANING_ATTEMPTS:
            logger.info(
                "Video %s: LLM cleaning skipped (attempts=%s >= max=%s)",
                video.id,
                attempts,
                LLM_MAX_CLEANING_ATTEMPTS,
            )
            return songs

        raw_text = ""
        if analyzer.song_list_comment:
            raw_text = analyzer.song_list_comment.get("text", "") or ""

        now = datetime.now(UTC).replace(tzinfo=None)
        video.cleaning_attempts = attempts + 1
        video.last_cleaned_at = now

        updater_status.set(
            UpdaterPhase.LLM_CLEANING,
            detail="LLM-cleaning setlist comment",
            video_id=video.id,
            video_title=video.title,
        )
        cleaned = await maybe_clean_song_list_comment(raw_text)
        if cleaned is None:
            return songs

        video.cleaned_song_list_comment = {
            "text": cleaned,
            "source": "llm",
            "model": LLM_MODEL,
        }
        llm_songs = analyzer.extract_from_text(cleaned, analyzed_by_llm=True)
        if not llm_songs:
            logger.warning(
                "Video %s: LLM clean returned no parseable songs; keeping regex list",
                video.id,
            )
            return songs

        # Prefer LLM list when it parses at least as many songs as regex.
        if len(llm_songs) >= len(songs):
            logger.info(
                "Video %s: using LLM-cleaned setlist (%s songs, was %s)",
                video.id,
                len(llm_songs),
                len(songs),
            )
            return llm_songs

        logger.info(
            "Video %s: LLM setlist shorter (%s < %s); keeping regex list",
            video.id,
            len(llm_songs),
            len(songs),
        )
        return songs

    async def _jitter_sleep(self) -> None:
        low = min(UPDATE_SCRAPE_SLEEP_MIN, UPDATE_SCRAPE_SLEEP_MAX)
        high = max(UPDATE_SCRAPE_SLEEP_MIN, UPDATE_SCRAPE_SLEEP_MAX)
        delay = random.uniform(low, high)
        logger.info("Inter-scrape jitter: sleeping %.1fs", delay)
        updater_status.set(
            UpdaterPhase.JITTER,
            detail=f"Inter-scrape pause ({delay:.1f}s)",
            clear_video=True,
            comment_scrapes_this_cycle=self._comment_scrapes_this_cycle,
        )
        await asyncio.sleep(delay)
