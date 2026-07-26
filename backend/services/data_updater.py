"""DataUpdater: scrape → analyze → persist with Tier B YouTube pacing."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio.engine import AsyncEngine

from config import (
    BACKGROUND_UPDATER_ENABLED,
    LLM_API_KEY,
    LLM_CLEANING_ENABLED,
    LLM_MAX_CLEANING_ATTEMPTS,
    LLM_MODEL,
    SCRAPE_POLICY,
    UPDATER_HEARTBEAT_INTERVAL_SECONDS,
)
from models.channel import (
    VIDEO_BACKFILL_ACTIVE,
    VIDEO_BACKFILL_DONE,
    VIDEO_BACKFILL_FAILED,
    VIDEO_BACKFILL_RUNNING,
    YouTubeChannel,
)
from models.song import Song
from models.video import (
    ANALYSIS_DONE,
    ANALYSIS_EXHAUSTED,
    ANALYSIS_NO_SETLIST,
    ANALYSIS_RETRY,
    ANALYSIS_SKIPPED,
    YouTubeVideo,
)
from repositories.channel_repository import ChannelRepository
from repositories.song_repository import SongRepository
from repositories.video_repository import VideoRepository
from services.analyzer.llm_cleaner import maybe_clean_song_list_comment
from services.analyzer.yt_comment_analyzer import CommentAnalyzer
from services.scrape_policy import ScrapePolicy
from services.updater_runtime_state import (
    UPDATER_PROCESS_OWNER_ID,
    UpdaterOutcome,
    UpdaterRuntimeStateStore,
)
from services.updater_status import UpdaterPhase, updater_status
from services.youtube_operation_lock import (
    YouTubeUpdaterBusyError,
    youtube_operation_guard,
)
from services.yt_scraper.channel_scraper import YouTubeChannelScraper
from services.yt_scraper.channel_video_scraper import YouTubeChannelVideoScraper
from services.yt_scraper.errors import (
    YouTubeAccessBlocked,
    is_youtube_block_error,
    raise_if_block_error,
)
from services.yt_scraper.subprocess_runner import run_scrape_in_subprocess
from services.yt_scraper.video_comment_scraper import (
    VideoCommentScrapeResult,
    YouTubeVideoCommentScraper,
)
from utils.video_type import (
    VIDEO_TYPE_KARAOKE,
    classify_video_type,
    should_scrape_comments,
)
from utils.youtube_upload_date import (
    UPLOAD_DATE_EXACT,
    upload_date_from_entry,
    upload_date_info_from_entry,
)
from utils.ytdlp_snapshot import (
    merged_video_metadata,
    snapshot_payload,
    snapshot_ytdlp_info,
)


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


@dataclass(frozen=True)
class VideoSongReloadResult:
    """Outcome of an administrator-requested comment/setlist re-analysis."""

    video_id: str
    song_count: int
    has_song_list_comment: bool
    analysis_status: str
    message: str


logger = logging.getLogger(__name__)


class RetryableVideoAnalysisError(Exception):
    """A scraper failure whose retry state is safe to commit.

    This separates expected upstream failures from analyzer/programming errors.
    The analysis queue commits the retry schedule for this exception only;
    unexpected failures roll the entire per-video transaction back.
    """


class DataUpdater:
    """負責資料更新的業務邏輯.

    Owns commit/rollback for the given session (commit per channel).
    Pipeline: channel → videos → comments → CommentAnalyzer → songs.
    """

    # Fast monotonic cache of the PostgreSQL-backed global cooldown.
    _youtube_cooldown_until: float | None = None

    def __init__(
        self,
        session: AsyncSession,
        channel_repo: ChannelRepository,
        video_repo: VideoRepository,
        song_repo: SongRepository,
        policy: ScrapePolicy | None = None,
        runtime_state_store: UpdaterRuntimeStateStore | None = None,
    ):
        self.session = session
        self.channel_repo = channel_repo
        self.video_repo = video_repo
        self.song_repo = song_repo
        self.policy = policy or SCRAPE_POLICY
        bind = getattr(session, "bind", None)
        self.runtime_state_store = runtime_state_store
        if self.runtime_state_store is None and isinstance(bind, AsyncEngine):
            self.runtime_state_store = UpdaterRuntimeStateStore(bind)
        self._comment_scrapes_this_cycle = 0
        self._backfill_channels_this_cycle = 0
        self._steady_channels_this_cycle = 0

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
        seconds = SCRAPE_POLICY.youtube_cooldown_seconds if seconds is None else seconds
        cls._youtube_cooldown_until = time.monotonic() + max(0.0, seconds)
        logger.warning(
            "YouTube cooldown set for %ss (until monotonic+%.0f)",
            seconds,
            seconds,
        )

    async def update(self, *, priority_channel_id: str | None = None) -> None:
        async with youtube_operation_guard(self.session) as acquired:
            if not acquired:
                logger.info(
                    "Skipping update cycle: another process owns the YouTube lock"
                )
                updater_status.set(
                    UpdaterPhase.WAITING,
                    detail="Another updater process is currently running",
                    clear_channel=True,
                    clear_video=True,
                )
                return
            outcome = UpdaterOutcome.ERROR
            runtime_started = False
            heartbeat_stop = asyncio.Event()
            heartbeat_task: asyncio.Task[None] | None = None
            try:
                if self.runtime_state_store is not None:
                    await self.runtime_state_store.mark_started(
                        UPDATER_PROCESS_OWNER_ID
                    )
                    runtime_started = True
                    heartbeat_task = asyncio.create_task(
                        self._heartbeat_runtime_state(heartbeat_stop)
                    )
                outcome = await self._update_without_lock(
                    priority_channel_id=priority_channel_id,
                )
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
                if runtime_started and self.runtime_state_store is not None:
                    try:
                        await self.runtime_state_store.mark_finished(
                            UPDATER_PROCESS_OWNER_ID,
                            outcome,
                        )
                    except Exception:
                        logger.exception(
                            "Could not persist the updater cycle terminal state"
                        )

    async def _heartbeat_runtime_state(self, stop: asyncio.Event) -> None:
        if self.runtime_state_store is None:
            return
        while True:
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=UPDATER_HEARTBEAT_INTERVAL_SECONDS,
                )
                return
            except TimeoutError:
                try:
                    owned = await self.runtime_state_store.heartbeat(
                        UPDATER_PROCESS_OWNER_ID
                    )
                    if not owned:
                        logger.error(
                            "Updater heartbeat lost ownership; stopping heartbeat"
                        )
                        return
                except Exception:
                    logger.exception("Could not persist updater heartbeat")

    async def _run_blocking_scrape(self, operation: Callable[[], Any]) -> Any:
        """Use a killable subprocess in production and threads for test doubles."""
        if isinstance(self.session, AsyncSession):
            return await run_scrape_in_subprocess(
                operation,
                timeout_seconds=self.policy.ytdlp_operation_timeout_seconds,
                terminate_grace_seconds=self.policy.ytdlp_terminate_grace_seconds,
            )
        return await asyncio.to_thread(operation)

    async def _update_without_lock(
        self,
        *,
        priority_channel_id: str | None = None,
    ) -> UpdaterOutcome:
        await self._sync_persisted_cooldown()
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
            return UpdaterOutcome.COOLDOWN

        self._comment_scrapes_this_cycle = 0
        self._backfill_channels_this_cycle = 0
        self._steady_channels_this_cycle = 0
        updater_status.begin_cycle()
        logger.info(
            "Starting update cycle (max_videos=%s, max_comment_scrapes=%s, "
            "backfill_page=%s, backfill_channels=%s, jitter=%.1f–%.1fs, "
            "max_attempts=%s)",
            self.policy.recent_videos_per_channel,
            self.policy.comment_scrapes_per_cycle,
            self.policy.backfill_page_size,
            self.policy.backfill_channels_per_cycle,
            self.policy.inter_comment_sleep_min,
            self.policy.inter_comment_sleep_max,
            self.policy.max_analysis_attempts,
        )

        try:
            updater_status.set(
                UpdaterPhase.FETCHING_CHANNELS,
                detail="Loading channels from database",
                clear_channel=True,
                clear_video=True,
            )
            channels = await self.channel_repo.get_all()
            channels = self._prioritize_backfill_channels(
                channels,
                priority_channel_id=priority_channel_id,
            )
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
                    await self._activate_youtube_cooldown()
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
            if self.youtube_cooldown_remaining() <= 0:
                try:
                    await self._process_analysis_queue()
                except YouTubeAccessBlocked as exc:
                    await self._activate_youtube_cooldown()
                    logger.warning("YouTube block in analysis queue: %s", exc)
                    updater_status.set(
                        UpdaterPhase.COOLDOWN,
                        detail="YouTube temporarily blocked comment requests",
                        clear_channel=True,
                        last_error="YouTube access was temporarily blocked",
                    )
            remaining = self.youtube_cooldown_remaining()
            if remaining > 0:
                updater_status.end_cycle(
                    phase=UpdaterPhase.COOLDOWN,
                    detail=f"YouTube cooldown ({remaining:.0f}s remaining)",
                )
                return UpdaterOutcome.COOLDOWN
            else:
                updater_status.end_cycle()
                return UpdaterOutcome.SUCCESS
        except asyncio.CancelledError:
            await self.session.rollback()
            raise
        except Exception:
            await self.session.rollback()
            updater_status.end_cycle(error="The update cycle failed")
            raise
        except BaseException:
            await self.session.rollback()
            raise

    @staticmethod
    def _prioritize_backfill_channels(
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
        active_ids = {channel.id for channel in priority + active}
        return (
            priority
            + active
            + [channel for channel in channels if channel.id not in active_ids]
        )

    async def refresh_channel_video_list(
        self, channel: YouTubeChannel
    ) -> ChannelVideoRefreshResult:
        async with youtube_operation_guard(self.session) as acquired:
            if not acquired:
                raise YouTubeUpdaterBusyError(
                    "Another updater process is currently using YouTube"
                )
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
                await self._activate_youtube_cooldown()
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

    async def reload_video_song_list(
        self,
        video: YouTubeVideo,
    ) -> VideoSongReloadResult:
        """Run the normal comment analyzer once for an administrator request."""
        async with youtube_operation_guard(self.session) as acquired:
            if not acquired:
                raise YouTubeUpdaterBusyError(
                    "Another updater process is currently using YouTube"
                )
            try:
                await self._sync_persisted_cooldown()
                remaining = self.youtube_cooldown_remaining()
                if remaining > 0:
                    updater_status.set(
                        UpdaterPhase.COOLDOWN,
                        detail=f"YouTube cooldown active ({remaining:.0f}s remaining)",
                        video_id=video.id,
                        video_title=video.title,
                    )
                    raise YouTubeAccessBlocked(
                        f"YouTube cooldown active ({remaining:.0f}s remaining)"
                    )

                self._comment_scrapes_this_cycle = 0
                await self._analyze_video(video)
                song_count = await self.song_repo.count_by_video_id(video.id)
                await self.session.commit()
                updater_status.set(
                    self._manual_operation_resting_phase(),
                    detail=f"Song-list reload finished for {video.title}",
                    clear_channel=True,
                    video_id=video.id,
                    video_title=video.title,
                )
                return VideoSongReloadResult(
                    video_id=video.id,
                    song_count=song_count,
                    has_song_list_comment=video.has_song_list_comment,
                    analysis_status=video.analysis_status,
                    message=(
                        f"Reloaded comments and found {song_count} song(s)."
                        if video.has_song_list_comment
                        else "Reloaded comments; no new setlist was found."
                    ),
                )
            except asyncio.CancelledError:
                await self.session.rollback()
                updater_status.set(
                    self._manual_operation_resting_phase(),
                    detail="Manual song-list reload was cancelled",
                    clear_channel=True,
                    clear_video=True,
                )
                raise
            except YouTubeAccessBlocked:
                await self._activate_youtube_cooldown()
                raise
            except Exception:
                await self.session.rollback()
                updater_status.set(
                    UpdaterPhase.ERROR,
                    detail=f"Could not reload song list for {video.title}",
                    clear_channel=True,
                    video_id=video.id,
                    video_title=video.title,
                    last_error="A manual song-list reload failed",
                )
                raise
            except BaseException:
                await self.session.rollback()
                raise

    @staticmethod
    def _manual_operation_resting_phase() -> UpdaterPhase:
        return UpdaterPhase.WAITING if BACKGROUND_UPDATER_ENABLED else UpdaterPhase.IDLE

    async def _sync_persisted_cooldown(self) -> None:
        getter = getattr(self.channel_repo, "get_youtube_cooldown_until", None)
        if getter is None:
            return
        until = await getter()
        if until is None:
            return
        remaining = (until - self._utc_now()).total_seconds()
        if remaining > self.youtube_cooldown_remaining():
            self.set_youtube_cooldown(remaining)

    async def _activate_youtube_cooldown(self) -> None:
        """Persist current work and cooldown atomically, then update local cache."""
        seconds = self.policy.youtube_cooldown_seconds
        setter = getattr(self.channel_repo, "set_youtube_cooldown_until", None)
        try:
            if setter is not None:
                await setter(self._utc_now() + timedelta(seconds=seconds))
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            raise
        self.set_youtube_cooldown(seconds)

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
        # Re-evaluate using the newly stored full-video snapshot. This only
        # updates classification state; the manual refresh never deletes
        # videos, comments, songs, or prior setlist inputs.
        reclassified = await self.video_repo.reclassify_for_channel(channel.id)

        logger.info(
            "Channel %s safe metadata refresh done scraped=%s reclassified=%s",
            channel.id,
            scraped_count,
            reclassified,
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
            reclassified=reclassified,
            cleared=0,
            message=(
                f"Refreshed {scraped_count} recent video(s), reclassified "
                f"{reclassified}, without deleting videos, comments, or "
                "existing setlists."
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
            if (
                self._backfill_channels_this_cycle
                >= self.policy.backfill_channels_per_cycle
            ):
                logger.info(
                    "Backfill channel cap reached (%s); "
                    "deferring video backfill for %s",
                    self.policy.backfill_channels_per_cycle,
                    channel.id,
                )
            else:
                self._backfill_channels_this_cycle += 1
                for page_index in range(self.policy.backfill_pages_per_cycle):
                    if page_index:
                        await self._list_jitter_sleep()
                    refreshed = await self._backfill_channel_video_page(channel)
                    # Each page, bounded cleanup, and cursor are durable as one
                    # unit, so interruption resumes at the next safe window.
                    await self.session.commit()
                    if refreshed is None:
                        break
                    channel = refreshed
                    if channel.video_backfill_status != VIDEO_BACKFILL_RUNNING:
                        break
            # Each backfill page already includes bounded reclassification,
            # derived-song cleanup, and cursor movement in its durable commit.
            return
        else:
            if not self._channel_scan_is_due(channel):
                return
            if (
                self._steady_channels_this_cycle
                >= self.policy.steady_channels_per_cycle
            ):
                return
            self._steady_channels_this_cycle += 1
            try:
                updater_status.set(
                    UpdaterPhase.SCRAPING_VIDEOS,
                    detail=f"Checking recent archives for {channel.name}",
                    channel_id=channel.id,
                    channel_name=channel.name,
                    clear_video=True,
                )
                videos = await self._scrape_and_upsert_videos(channel)
                next_scan = self._utc_now() + timedelta(
                    seconds=self.policy.steady_scan_interval_seconds
                )
                await self.channel_repo.schedule_video_scan(
                    channel.id,
                    next_scan_at=next_scan,
                    succeeded=True,
                )
                if not videos:
                    logger.info("No normal archive records found for %s", channel.id)
            except YouTubeAccessBlocked:
                raise
            except Exception:
                failures = max(0, channel.video_scan_failures) + 1
                retry_seconds = min(
                    self.policy.steady_scan_interval_seconds,
                    self.policy.steady_retry_base_seconds * (2 ** min(failures - 1, 5)),
                )
                await self.channel_repo.schedule_video_scan(
                    channel.id,
                    next_scan_at=self._utc_now() + timedelta(seconds=retry_seconds),
                    succeeded=False,
                )
                logger.exception(
                    "Recent archive scan failed for %s; retry in %ss",
                    channel.id,
                    retry_seconds,
                )
                updater_status.set(
                    UpdaterPhase.ERROR,
                    detail="Recent archive scan failed and was rescheduled",
                    channel_id=channel.id,
                    channel_name=channel.name,
                    last_error="A channel discovery scan failed",
                )
                return

        video_ids = [video.id for video in videos]
        if not video_ids:
            return
        await self._reclassify_and_clear_video_ids(channel, video_ids)

    async def _reclassify_and_clear_video_ids(
        self,
        channel: YouTubeChannel,
        video_ids: list[str],
    ) -> None:
        """Reclassify and clean one scraped page in the caller's transaction."""
        if not video_ids:
            return
        updater_status.set(
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

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    def _channel_scan_is_due(self, channel: YouTubeChannel) -> bool:
        return (
            channel.next_video_scan_at is None
            or channel.next_video_scan_at <= self._utc_now()
        )

    async def _process_analysis_queue(self) -> None:
        """Analyze a global, due queue independently from channel discovery."""
        remaining = (
            self.policy.comment_scrapes_per_cycle - self._comment_scrapes_this_cycle
        )
        if remaining <= 0:
            return

        needing = await self.video_repo.get_analysis_queue(
            max_attempts=self.policy.max_analysis_attempts,
            limit=remaining,
        )
        logger.info(
            "Global analysis queue returned %s video(s) (cycle cap=%s)",
            len(needing),
            self.policy.comment_scrapes_per_cycle,
        )
        for video in needing:
            if (
                self._comment_scrapes_this_cycle
                >= self.policy.comment_scrapes_per_cycle
            ):
                break
            try:
                await self._analyze_video(video)
                await self.session.commit()
            except asyncio.CancelledError:
                await self.session.rollback()
                raise
            except YouTubeAccessBlocked:
                # The caller adds the global cooldown and commits both states
                # atomically before stopping the remaining YouTube work.
                raise
            except RetryableVideoAnalysisError:
                # The scraper failure path deliberately wrote only retry/backoff
                # state. Keep it durable, then continue with the next video.
                await self.session.commit()
                logger.warning(
                    "Retryable scraper failure analyzing video %s; continuing",
                    video.id,
                )
                updater_status.set(
                    UpdaterPhase.ERROR,
                    detail="Video comments could not be fetched and were rescheduled",
                    clear_channel=True,
                    video_id=video.id,
                    video_title=video.title,
                    last_error="A video comment request failed",
                )
            except Exception:
                # Analyzer/programming/database failures must not make partial
                # metadata, song replacement, or scheduling changes durable.
                await self.session.rollback()
                logger.exception(
                    "Non-block failure analyzing video %s; continuing", video.id
                )
                updater_status.set(
                    UpdaterPhase.ERROR,
                    detail="Video analysis failed; continuing with the next video",
                    clear_channel=True,
                    video_id=video.id,
                    video_title=video.title,
                    last_error="A video analysis failed",
                )
            except BaseException:
                await self.session.rollback()
                raise

    async def _backfill_channel_video_page(
        self, channel: YouTubeChannel
    ) -> YouTubeChannel | None:
        """Scrape the next playlist window and advance the persisted cursor."""
        page_size = max(1, self.policy.backfill_page_size)
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

        scraper = YouTubeChannelVideoScraper(
            channel.url,
            sleep_interval=self.policy.ytdlp_list_sleep_interval,
            max_sleep_interval=self.policy.ytdlp_list_max_sleep_interval,
            socket_timeout=self.policy.ytdlp_socket_timeout_seconds,
            retries=self.policy.ytdlp_retries,
            extractor_retries=self.policy.ytdlp_extractor_retries,
        )
        scrape_page = partial(
            scraper.get_channel_videos_page,
            playlist_start=offset,
            page_size=page_size,
        )

        try:
            page = await self._run_blocking_scrape(scrape_page)
        except Exception as exc:
            raise_if_block_error(exc)
            logger.exception(
                "Backfill page failed for channel %s; scheduling retry", channel.id
            )
            failed = await self.channel_repo.update_video_backfill(
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
            return failed

        # Prefer recent uploads across Streams + Videos; empty dates sort last.
        scraped_sorted = sorted(
            page.videos,
            key=lambda v: (
                v.upload_date
                or upload_date_from_entry(
                    merged_video_metadata(v.raw_data, v.metadata_raw_data)
                )
                or ""
            ),
            reverse=True,
        )
        for video in scraped_sorted:
            video.channel_id = channel.id

        upserted = (
            await self.video_repo.upsert_many(scraped_sorted) if scraped_sorted else []
        )
        await self._reclassify_and_clear_video_ids(
            channel,
            [video.id for video in upserted],
        )
        if not page.all_tabs_succeeded:
            # Saving the usable rows is safe, but advancing would permanently
            # skip the failed tab's current window.
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
            return failed

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

        updated = await self.channel_repo.update_video_backfill(
            channel.id,
            status=next_status,
            offset=next_offset,
        )
        if next_status == VIDEO_BACKFILL_DONE:
            next_scan = self._utc_now() + timedelta(
                seconds=self.policy.steady_scan_interval_seconds
            )
            updated = await self.channel_repo.schedule_video_scan(
                channel.id,
                next_scan_at=next_scan,
                succeeded=True,
            )
        return updated

    async def _refresh_channel(self, channel: YouTubeChannel) -> YouTubeChannel:
        logger.info("Refreshing channel metadata for %s", channel.url)

        scraper = YouTubeChannelScraper(
            sleep_interval=self.policy.ytdlp_list_sleep_interval,
            max_sleep_interval=self.policy.ytdlp_list_max_sleep_interval,
            socket_timeout=self.policy.ytdlp_socket_timeout_seconds,
            retries=self.policy.ytdlp_retries,
            extractor_retries=self.policy.ytdlp_extractor_retries,
        )
        scrape = partial(scraper.get_channel_info, channel.url)

        try:
            scraped = await self._run_blocking_scrape(scrape)
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
        """Scrape Streams+Videos tabs; retain all normal archived records."""

        scraper = YouTubeChannelVideoScraper(
            channel.url,
            max_videos=self.policy.recent_videos_per_channel,
            full_metadata=full_metadata,
            metadata_limit=self.policy.metadata_scrapes_per_refresh,
            sleep_interval=self.policy.ytdlp_list_sleep_interval,
            max_sleep_interval=self.policy.ytdlp_list_max_sleep_interval,
            socket_timeout=self.policy.ytdlp_socket_timeout_seconds,
            retries=self.policy.ytdlp_retries,
            extractor_retries=self.policy.ytdlp_extractor_retries,
        )

        try:
            scraped = await self._run_blocking_scrape(scraper.get_channel_videos)
        except Exception as exc:
            raise_if_block_error(exc)
            raise

        # Prefer recent uploads across Streams + Videos; empty dates sort last.
        scraped_sorted = sorted(
            scraped,
            key=lambda v: (
                v.upload_date
                or upload_date_from_entry(
                    merged_video_metadata(v.raw_data, v.metadata_raw_data)
                )
                or ""
            ),
            reverse=True,
        )
        logger.info(
            "Channel %s: retained %s normal archive record(s) (full_metadata=%s)",
            channel.id,
            len(scraped_sorted),
            full_metadata,
        )

        for video in scraped_sorted:
            # Flat extracts sometimes omit channel_id; bind to the DB channel.
            video.channel_id = channel.id

        return scraped_sorted

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
        raw = merged_video_metadata(video.raw_data, video.metadata_raw_data)
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
            video.analysis_status = ANALYSIS_SKIPPED
            video.next_analysis_at = None
            await self.video_repo.update_analysis(video)
            return

        if self._comment_scrapes_this_cycle > 0:
            await self._jitter_sleep()
        self._comment_scrapes_this_cycle += 1
        logger.info(
            "Comment scrape %s/%s for karaoke stream %s (%s)",
            self._comment_scrapes_this_cycle,
            self.policy.comment_scrapes_per_cycle,
            video.id,
            video.title,
        )
        updater_status.set(
            UpdaterPhase.SCRAPING_COMMENTS,
            detail=(
                f"Scraping comments "
                f"({self._comment_scrapes_this_cycle}/"
                f"{self.policy.comment_scrapes_per_cycle})"
            ),
            video_id=video.id,
            video_title=video.title,
            comment_scrapes_this_cycle=self._comment_scrapes_this_cycle,
        )

        scraper = YouTubeVideoCommentScraper(
            video.url,
            sleep_interval=self.policy.ytdlp_comment_sleep_interval,
            max_sleep_interval=self.policy.ytdlp_comment_max_sleep_interval,
            socket_timeout=self.policy.ytdlp_socket_timeout_seconds,
            retries=self.policy.ytdlp_retries,
            extractor_retries=self.policy.ytdlp_extractor_retries,
        )
        scrape = getattr(scraper, "scrape", None)
        if callable(scrape):
            scrape_comments = partial(scrape, self.policy.max_comments_per_video)
        else:
            # Compatibility for small test/manual fakes that only implement
            # the original comments-only method.
            def scrape_comments() -> VideoCommentScrapeResult:
                comments = scraper.get_video_top_comments(
                    self.policy.max_comments_per_video
                )
                metadata = getattr(scraper, "video_metadata", {})
                return VideoCommentScrapeResult(
                    comments=comments,
                    comments_available=True,
                    metadata_raw_data=snapshot_ytdlp_info(
                        metadata,
                        source="video_comments:test_compat",
                    ),
                    scraped_at=datetime.now(UTC).replace(tzinfo=None),
                )

        now = datetime.now(UTC).replace(tzinfo=None)
        attempts = (video.analyze_attempts or 0) + 1

        try:
            scrape_result = await self._run_blocking_scrape(scrape_comments)
        except Exception as exc:
            video.last_analyzed_at = now
            blocked = isinstance(exc, YouTubeAccessBlocked) or is_youtube_block_error(
                exc
            )
            if blocked:
                # A process/IP block says nothing about this video's content and
                # must not permanently exhaust the record's analysis attempts.
                video.analysis_status = ANALYSIS_RETRY
                video.next_analysis_at = now + timedelta(
                    seconds=self.policy.youtube_cooldown_seconds
                )
                await self.video_repo.update_analysis(video)
                raise YouTubeAccessBlocked(str(exc)) from exc

            video.analyze_attempts = attempts
            if attempts >= self.policy.max_analysis_attempts:
                video.analysis_status = ANALYSIS_EXHAUSTED
                video.next_analysis_at = None
            else:
                retry_seconds = self.policy.analysis_retry_base_seconds * (
                    2 ** min(attempts - 1, 5)
                )
                video.analysis_status = ANALYSIS_RETRY
                video.next_analysis_at = now + timedelta(seconds=retry_seconds)
            await self.video_repo.update_analysis(video)
            raise RetryableVideoAnalysisError(str(exc)) from exc

        comments = scrape_result.comments
        scraped_metadata = snapshot_payload(scrape_result.metadata_raw_data)
        exact_date = upload_date_info_from_entry(scraped_metadata)
        if exact_date and (
            video.upload_date != exact_date.value
            or video.upload_date_precision != UPLOAD_DATE_EXACT
        ):
            # The comment request already extracted this full video metadata.
            # Upgrade the approximate channel-list date without another call.
            video.upload_date = exact_date.value
            video.upload_date_precision = exact_date.precision
        scraped_title = scraped_metadata.get("title")
        if isinstance(scraped_title, str) and scraped_title.strip():
            video.title = scraped_title
        if scraped_metadata:
            video.metadata_raw_data = scrape_result.metadata_raw_data
            video.metadata_scraped_at = scrape_result.scraped_at
        effective_metadata = merged_video_metadata(
            video.raw_data,
            video.metadata_raw_data,
        )
        video.type = classify_video_type(
            video.title,
            live_status=effective_metadata.get("live_status"),
            duration=effective_metadata.get("duration"),
        )
        if scraped_metadata:
            await self.video_repo.upsert(video)

        comment_snapshot = {
            "schema_version": 1,
            "comments": comments,
            "comments_available": scrape_result.comments_available,
            "captured_at": scrape_result.scraped_at.isoformat() + "Z",
            "source": "yt-dlp:top",
        }
        video.analyze_attempts = attempts
        video.last_analyzed_at = now

        # Flat metadata can produce a false-positive karaoke classification.
        # The already-fetched full snapshot is authoritative; retain the raw
        # comments but do not create/retain derived songs for non-karaoke rows.
        if video.type != VIDEO_TYPE_KARAOKE:
            self._record_comments_observation(
                video,
                comment_snapshot,
                preserve_existing=video.has_song_list_comment,
            )
            video.has_song_list_comment = False
            video.analysis_status = ANALYSIS_SKIPPED
            video.next_analysis_at = None
            await self.song_repo.replace_for_video(video.id, [])
            await self.video_repo.update_analysis(video)
            logger.info(
                "Video %s reclassified as %s after full metadata; analysis skipped",
                video.id,
                video.type,
            )
            return

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
                self._record_comments_observation(
                    video,
                    comment_snapshot,
                    preserve_existing=False,
                )
                video.has_song_list_comment = True
                video.analysis_status = ANALYSIS_DONE
                video.next_analysis_at = None
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
                self._record_comments_observation(
                    video,
                    comment_snapshot,
                    preserve_existing=video.has_song_list_comment,
                )
                cleared = self._record_no_setlist_result(video, now, attempts)
                if cleared:
                    await self.song_repo.replace_for_video(video.id, [])
                logger.info(
                    "Video %s: timestamp comment had no parseable songs", video.id
                )
        else:
            self._record_comments_observation(
                video,
                comment_snapshot,
                preserve_existing=video.has_song_list_comment,
            )
            cleared = self._record_no_setlist_result(video, now, attempts)
            if cleared:
                await self.song_repo.replace_for_video(video.id, [])
            logger.info("Video %s: no setlist comment found", video.id)

        await self.video_repo.update_analysis(video)

    @staticmethod
    def _record_comments_observation(
        video: YouTubeVideo,
        snapshot: dict,
        *,
        preserve_existing: bool,
    ) -> None:
        """Keep source comments behind a successful result on negative refreshes."""
        if preserve_existing and video.comments_raw_data:
            preserved = dict(video.comments_raw_data)
            preserved["last_negative_observation"] = snapshot
            video.comments_raw_data = preserved
            return
        video.comments_raw_data = snapshot

    def _record_no_setlist_result(
        self,
        video: YouTubeVideo,
        now: datetime,
        attempts: int,
    ) -> bool:
        """Record an absence without erasing a prior successful extraction.

        Top-comment membership and comment availability can change. A negative
        observation is useful for a never-successful record, but is not strong
        enough evidence to destroy an existing setlist and songs.

        Returns ``True`` when derived songs should be cleared.
        """
        if video.has_song_list_comment:
            video.analysis_status = ANALYSIS_DONE
            video.next_analysis_at = None
            logger.warning(
                "Video %s: current comments had no setlist; preserving prior result",
                video.id,
            )
            return False

        video.has_song_list_comment = False
        video.song_list_comment_raw_data = None
        video.cleaned_song_list_comment = None
        video.cleaning_attempts = 0
        video.last_cleaned_at = None
        self._schedule_no_setlist_recheck(video, now, attempts)
        return True

    def _schedule_no_setlist_recheck(
        self,
        video: YouTubeVideo,
        now: datetime,
        attempts: int,
    ) -> None:
        if attempts >= self.policy.max_analysis_attempts:
            video.analysis_status = ANALYSIS_EXHAUSTED
            video.next_analysis_at = None
            return
        # Comments often gain a setlist after archive publication. Recheck later,
        # never immediately on the next five-minute worker tick.
        video.analysis_status = ANALYSIS_NO_SETLIST
        video.next_analysis_at = now + timedelta(
            seconds=self.policy.analysis_recheck_seconds * attempts
        )

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
        low = min(
            self.policy.inter_comment_sleep_min,
            self.policy.inter_comment_sleep_max,
        )
        high = max(
            self.policy.inter_comment_sleep_min,
            self.policy.inter_comment_sleep_max,
        )
        delay = random.uniform(low, high)
        logger.info("Inter-scrape jitter: sleeping %.1fs", delay)
        updater_status.set(
            UpdaterPhase.JITTER,
            detail=f"Inter-scrape pause ({delay:.1f}s)",
            clear_video=True,
            comment_scrapes_this_cycle=self._comment_scrapes_this_cycle,
        )
        await asyncio.sleep(delay)

    async def _list_jitter_sleep(self) -> None:
        low = min(self.policy.inter_list_sleep_min, self.policy.inter_list_sleep_max)
        high = max(self.policy.inter_list_sleep_min, self.policy.inter_list_sleep_max)
        delay = random.uniform(low, high)
        logger.info("Backfill page pause: sleeping %.1fs", delay)
        updater_status.set(
            UpdaterPhase.JITTER,
            detail=f"Backfill page pause ({delay:.1f}s)",
            clear_video=True,
            comment_scrapes_this_cycle=self._comment_scrapes_this_cycle,
        )
        await asyncio.sleep(delay)
