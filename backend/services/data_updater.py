"""Data updater orchestration with bounded, dependency-injected collaborators."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio.engine import AsyncEngine

import config
from config import (
    SCRAPE_POLICY,
    UPDATER_HEARTBEAT_INTERVAL_SECONDS,
    LlmSettings,
)
from models.channel import (
    MAX_CHANNELS_PER_BULK_ADD,
    ChannelIngestItem,
    YouTubeChannel,
)
from models.video import YouTubeVideo
from repositories.channel_ingest_repository import ChannelIngestRepository
from repositories.channel_repository import ChannelRepository
from repositories.song_repository import SongRepository
from repositories.video_repository import VideoRepository
from services.analyzer.llm_cleaner import LlmSongListCleaner, SongListCleaner
from services.cache import PUBLIC_CACHE_NAMESPACES, ResponseCache
from services.channel_creator import ChannelCreator, ChannelResolutionFailed
from services.scrape_policy import ScrapePolicy
from services.scraping import (
    DefaultScraperFactory,
    ScrapeExecutor,
    ScraperFactory,
)
from services.updater.channel_cycle import ChannelCycleService
from services.updater.channel_videos import (
    ChannelVideoService,
    prioritize_backfill_channels,
)
from services.updater.models import (
    ChannelVideoRefreshResult,
    CycleProgress,
    RetryableVideoAnalysisError,
    VideoSongReloadResult,
)
from services.updater.runtime import UpdaterRuntimeLifecycle
from services.updater.video_analysis import VideoAnalysisService
from services.updater_runtime_state import (
    UpdaterOutcome,
    UpdaterRuntimeStateStore,
)
from services.updater_status import (
    UpdaterPhase,
    UpdaterStatusTracker,
    updater_status,
)
from services.youtube_cooldown import YouTubeCooldown
from services.youtube_operation_lock import (
    YouTubeOperationCoordinator,
    YouTubeUpdaterBusyError,
    default_youtube_operation_coordinator,
)
from services.yt_scraper.errors import (
    YouTubeAccessBlocked,
)

logger = logging.getLogger(__name__)


class DataUpdater:
    """Coordinate transactions and locks around focused updater services.

    The updater owns commit/rollback for its session. Channel/video discovery
    and per-video analysis live in dedicated collaborators; this class keeps
    cross-cutting cycle ordering, transaction boundaries, and public manual
    operations visible in one place.
    """

    def __init__(
        self,
        session: AsyncSession,
        channel_repo: ChannelRepository,
        video_repo: VideoRepository,
        song_repo: SongRepository,
        policy: ScrapePolicy | None = None,
        runtime_state_store: UpdaterRuntimeStateStore | None = None,
        *,
        status_tracker: UpdaterStatusTracker | None = None,
        cooldown: YouTubeCooldown | None = None,
        operations: YouTubeOperationCoordinator | None = None,
        channel_ingest_repo: ChannelIngestRepository | None = None,
        channel_creator: ChannelCreator | None = None,
        scraper_factory: ScraperFactory | None = None,
        scrape_executor: ScrapeExecutor | None = None,
        song_list_cleaner: SongListCleaner | None = None,
        cache: ResponseCache | None = None,
        heartbeat_interval_seconds: float = UPDATER_HEARTBEAT_INTERVAL_SECONDS,
        background_updater_enabled: bool | None = None,
        llm_settings: LlmSettings | None = None,
    ) -> None:
        self.session = session
        self.channel_repo = channel_repo
        self.video_repo = video_repo
        self.song_repo = song_repo
        self.policy = policy or SCRAPE_POLICY
        self.status = status_tracker or updater_status
        self.cooldown = cooldown or YouTubeCooldown(
            self.policy.youtube_cooldown_seconds
        )
        self.operations = operations or default_youtube_operation_coordinator
        self.channel_ingest_repo = channel_ingest_repo
        self.channel_creator = channel_creator
        self.scraper_factory = scraper_factory or DefaultScraperFactory(self.policy)
        self.scrape_executor = scrape_executor or ScrapeExecutor(self.policy)
        self.llm_settings = llm_settings or config.get_settings().llm
        self.song_list_cleaner = song_list_cleaner or LlmSongListCleaner(
            self.llm_settings
        )
        self.cache = cache
        self.background_updater_enabled = (
            config.BACKGROUND_UPDATER_ENABLED
            if background_updater_enabled is None
            else background_updater_enabled
        )
        bind = getattr(session, "bind", None)
        self.runtime_state_store = runtime_state_store
        if self.runtime_state_store is None and isinstance(bind, AsyncEngine):
            self.runtime_state_store = UpdaterRuntimeStateStore(bind)

        self._progress = CycleProgress()
        self._runtime = UpdaterRuntimeLifecycle(
            self.runtime_state_store,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        )
        self._channel_videos = ChannelVideoService(
            channel_repo,
            video_repo,
            song_repo,
            self.policy,
            self.status,
            self.scraper_factory,
            self._run_blocking_scrape,
            self._utc_now,
        )
        self._channel_cycle = ChannelCycleService(
            channel_repo,
            self._channel_videos,
            self.policy,
            self.status,
            self._progress,
            commit=lambda: self._commit(invalidate_cache=True),
            list_pause=lambda: self._list_jitter_sleep(),
            backfill_page=lambda channel: self._backfill_channel_video_page(channel),
        )
        self._video_analysis = VideoAnalysisService(
            video_repo,
            song_repo,
            self.policy,
            self.status,
            self.scraper_factory,
            self._run_blocking_scrape,
            self.song_list_cleaner,
            self.llm_settings,
            self._progress,
        )

    @property
    def _comment_scrapes_this_cycle(self) -> int:
        return self._progress.comment_scrapes

    @_comment_scrapes_this_cycle.setter
    def _comment_scrapes_this_cycle(self, value: int) -> None:
        self._progress.comment_scrapes = value

    def _cooldown_remaining(self) -> float:
        return self.cooldown.remaining()

    def _set_cooldown(self, seconds: float | None = None) -> None:
        self.cooldown.activate(seconds)

    async def update(self, *, priority_channel_id: str | None = None) -> None:
        async with self.operations.guard(self.session) as acquired:
            if not acquired:
                logger.info(
                    "Skipping update cycle: another process owns the YouTube lock"
                )
                self.status.set(
                    UpdaterPhase.WAITING,
                    detail="Another updater process is currently running",
                    clear_channel=True,
                    clear_video=True,
                )
                return
            await self._runtime.run(
                lambda: self._update_without_lock(
                    priority_channel_id=priority_channel_id,
                )
            )

    async def _run_blocking_scrape(self, operation: Callable[[], Any]) -> Any:
        """Use a killable subprocess in production and threads for test doubles."""
        return await self.scrape_executor.run(
            operation,
            production=isinstance(self.session, AsyncSession),
        )

    async def _commit(self, *, invalidate_cache: bool = True) -> None:
        """Commit owned work, then invalidate shared read models."""
        await self.session.commit()
        if invalidate_cache and self.cache is not None:
            await self.cache.invalidate(*PUBLIC_CACHE_NAMESPACES)

    async def _update_without_lock(
        self,
        *,
        priority_channel_id: str | None = None,
    ) -> UpdaterOutcome:
        await self._sync_persisted_cooldown()
        if self._cooldown_remaining() > 0:
            return self._skip_cycle_for_cooldown()

        self._begin_cycle()
        try:
            await self._process_channel_ingest_queue()
            if self._cooldown_remaining() <= 0:
                channels = await self._load_prioritized_channels(priority_channel_id)
                await self._process_channels(channels)
            if self._cooldown_remaining() <= 0:
                await self._process_analysis_queue_with_cooldown()
            return self._finish_cycle()
        except asyncio.CancelledError:
            await self.session.rollback()
            raise
        except Exception:
            await self.session.rollback()
            self.status.end_cycle(error="The update cycle failed")
            raise
        except BaseException:
            await self.session.rollback()
            raise

    def _skip_cycle_for_cooldown(self) -> UpdaterOutcome:
        remaining = self._cooldown_remaining()
        logger.warning(
            "Skipping update cycle: YouTube cooldown active (%.0fs remaining)",
            remaining,
        )
        self.status.set(
            UpdaterPhase.COOLDOWN,
            detail=f"YouTube cooldown active ({remaining:.0f}s remaining)",
            clear_channel=True,
            clear_video=True,
        )
        return UpdaterOutcome.COOLDOWN

    def _begin_cycle(self) -> None:
        self._progress.reset()
        self.status.begin_cycle()
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

    async def _process_channel_ingest_queue(self) -> None:
        if self.channel_ingest_repo is None or self.channel_creator is None:
            return

        self.status.set(
            UpdaterPhase.FETCHING_CHANNELS,
            detail="Loading queued channel URLs",
            clear_channel=True,
            clear_video=True,
        )
        items = await self.channel_ingest_repo.list_pending(
            limit=MAX_CHANNELS_PER_BULK_ADD
        )
        if not items:
            return

        logger.info("Resolving %s queued channel URL(s)", len(items))
        for item in items:
            if self._cooldown_remaining() > 0:
                return
            if not await self._process_channel_ingest_item(item):
                return

    async def _process_channel_ingest_item(
        self,
        item: ChannelIngestItem,
    ) -> bool:
        if self.channel_ingest_repo is None or self.channel_creator is None:
            return True
        self.status.set(
            UpdaterPhase.FETCHING_CHANNELS,
            detail="Resolving a queued channel URL",
            clear_channel=True,
            clear_video=True,
        )
        try:
            outcome = await self.channel_creator.resolve_locked(
                item.channel_url,
                wait_for_add_cooldown=True,
            )
            channel = outcome.channel
            if channel is None:
                raise RuntimeError("Resolved queue outcome did not include a channel")
            completed = await self.channel_ingest_repo.mark_completed(
                item.id,
                channel_id=channel.id,
            )
            if completed is None:
                raise RuntimeError("Queued channel item is no longer pending")
            await self._commit(
                invalidate_cache=outcome.public_data_changed,
            )
            logger.info(
                "Completed queued channel URL %s as %s (%s)",
                item.channel_url,
                channel.id,
                outcome.status,
            )
            return True
        except ChannelResolutionFailed:
            await self.channel_ingest_repo.mark_failed(
                item.id,
                error_message="Could not resolve this YouTube channel",
            )
            await self._commit(invalidate_cache=False)
            logger.warning(
                "Queued channel URL could not be resolved: %s",
                item.channel_url,
            )
            return True
        except YouTubeAccessBlocked as exc:
            await self.channel_ingest_repo.mark_attempted(item.id)
            await self._activate_youtube_cooldown()
            logger.warning(
                "YouTube block while resolving queued channel %s: %s",
                item.channel_url,
                exc,
            )
            self.status.set(
                UpdaterPhase.COOLDOWN,
                detail="YouTube temporarily blocked channel resolution",
                clear_channel=True,
                clear_video=True,
                last_error="YouTube access was temporarily blocked",
            )
            return False
        except asyncio.CancelledError:
            await self.session.rollback()
            raise
        except BaseException:
            await self.session.rollback()
            raise

    async def _load_prioritized_channels(
        self,
        priority_channel_id: str | None,
    ) -> list[YouTubeChannel]:
        self.status.set(
            UpdaterPhase.FETCHING_CHANNELS,
            detail="Loading channels from database",
            clear_channel=True,
            clear_video=True,
        )
        channels = await self.channel_repo.get_all()
        prioritized = self._prioritize_backfill_channels(
            channels,
            priority_channel_id=priority_channel_id,
        )
        logger.info("Fetched %s channels from the database.", len(prioritized))
        return prioritized

    async def _process_channels(self, channels: list[YouTubeChannel]) -> None:
        for channel in channels:
            if self._stop_for_mid_cycle_cooldown():
                return
            should_continue = await self._process_channel_transaction(channel)
            if not should_continue:
                return

    def _stop_for_mid_cycle_cooldown(self) -> bool:
        remaining = self._cooldown_remaining()
        if remaining <= 0:
            return False
        logger.warning("Cooldown active mid-cycle; stopping remaining channels")
        self.status.set(
            UpdaterPhase.COOLDOWN,
            detail=f"YouTube cooldown mid-cycle ({remaining:.0f}s remaining)",
            clear_channel=True,
            clear_video=True,
        )
        return True

    async def _process_channel_transaction(
        self,
        channel: YouTubeChannel,
    ) -> bool:
        try:
            public_data_changed = await self._process_channel(channel)
            self.status.set(
                UpdaterPhase.COMMITTING,
                detail=f"Committing updates for {channel.name}",
                channel_id=channel.id,
                channel_name=channel.name,
                clear_video=True,
            )
            await self._commit(invalidate_cache=bool(public_data_changed))
            logger.info("Committed updates for channel %s", channel.id)
            return True
        except YouTubeAccessBlocked as exc:
            logger.warning(
                "YouTube block while processing channel %s: %s",
                channel.id,
                exc,
            )
            await self._activate_youtube_cooldown()
            self.status.set(
                UpdaterPhase.COOLDOWN,
                detail="YouTube temporarily blocked scraper requests",
                channel_id=channel.id,
                channel_name=channel.name,
                last_error="YouTube access was temporarily blocked",
            )
            return False
        except Exception:
            await self.session.rollback()
            logger.exception(
                "Non-block failure for channel %s; continuing",
                channel.id,
            )
            self.status.set(
                UpdaterPhase.ERROR,
                detail="Channel processing failed; continuing with next channel",
                channel_id=channel.id,
                channel_name=channel.name,
                last_error="A channel update failed",
            )
            return True

    async def _process_analysis_queue_with_cooldown(self) -> None:
        try:
            await self._process_analysis_queue()
        except YouTubeAccessBlocked as exc:
            await self._activate_youtube_cooldown()
            logger.warning("YouTube block in analysis queue: %s", exc)
            self.status.set(
                UpdaterPhase.COOLDOWN,
                detail="YouTube temporarily blocked comment requests",
                clear_channel=True,
                last_error="YouTube access was temporarily blocked",
            )

    def _finish_cycle(self) -> UpdaterOutcome:
        remaining = self._cooldown_remaining()
        if remaining > 0:
            self.status.end_cycle(
                phase=UpdaterPhase.COOLDOWN,
                detail=f"YouTube cooldown ({remaining:.0f}s remaining)",
            )
            return UpdaterOutcome.COOLDOWN
        self.status.end_cycle()
        return UpdaterOutcome.SUCCESS

    @staticmethod
    def _prioritize_backfill_channels(
        channels: list[YouTubeChannel],
        *,
        priority_channel_id: str | None = None,
    ) -> list[YouTubeChannel]:
        return prioritize_backfill_channels(
            channels,
            priority_channel_id=priority_channel_id,
        )

    async def refresh_channel_video_list(
        self,
        channel: YouTubeChannel,
    ) -> ChannelVideoRefreshResult:
        async with self.operations.guard(self.session) as acquired:
            if not acquired:
                raise YouTubeUpdaterBusyError(
                    "Another updater process is currently using YouTube"
                )
            try:
                result = await self._refresh_channel_video_list_without_lock(channel)
                await self._commit()
                return result
            except asyncio.CancelledError:
                await self.session.rollback()
                self._set_manual_cancelled_status("Manual video refresh was cancelled")
                raise
            except YouTubeAccessBlocked:
                await self._activate_youtube_cooldown()
                raise
            except Exception:
                await self.session.rollback()
                self._set_manual_channel_error(channel)
                raise
            except BaseException:
                await self.session.rollback()
                raise

    async def reload_video_song_list(
        self,
        video: YouTubeVideo,
    ) -> VideoSongReloadResult:
        """Run the normal comment analyzer once for an administrator request."""
        async with self.operations.guard(self.session) as acquired:
            if not acquired:
                raise YouTubeUpdaterBusyError(
                    "Another updater process is currently using YouTube"
                )
            try:
                return await self._reload_video_song_list_without_lock(video)
            except asyncio.CancelledError:
                await self.session.rollback()
                self._set_manual_cancelled_status(
                    "Manual song-list reload was cancelled"
                )
                raise
            except YouTubeAccessBlocked:
                await self._activate_youtube_cooldown()
                raise
            except Exception:
                await self.session.rollback()
                self._set_manual_video_error(video)
                raise
            except BaseException:
                await self.session.rollback()
                raise

    async def _reload_video_song_list_without_lock(
        self,
        video: YouTubeVideo,
    ) -> VideoSongReloadResult:
        await self._sync_persisted_cooldown()
        remaining = self._cooldown_remaining()
        if remaining > 0:
            self.status.set(
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
        await self._commit()
        self.status.set(
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

    def _set_manual_cancelled_status(self, detail: str) -> None:
        self.status.set(
            self._manual_operation_resting_phase(),
            detail=detail,
            clear_channel=True,
            clear_video=True,
        )

    def _set_manual_channel_error(self, channel: YouTubeChannel) -> None:
        self.status.set(
            UpdaterPhase.ERROR,
            detail=f"Could not refresh video metadata for {channel.name}",
            channel_id=channel.id,
            channel_name=channel.name,
            clear_video=True,
            last_error="A manual video metadata refresh failed",
        )

    def _set_manual_video_error(self, video: YouTubeVideo) -> None:
        self.status.set(
            UpdaterPhase.ERROR,
            detail=f"Could not reload song list for {video.title}",
            clear_channel=True,
            video_id=video.id,
            video_title=video.title,
            last_error="A manual song-list reload failed",
        )

    def _manual_operation_resting_phase(self) -> UpdaterPhase:
        return (
            UpdaterPhase.WAITING
            if self.background_updater_enabled
            else UpdaterPhase.IDLE
        )

    async def _sync_persisted_cooldown(self) -> None:
        getter = getattr(self.channel_repo, "get_youtube_cooldown_until", None)
        if getter is None:
            return
        until = await getter()
        if until is None:
            return
        remaining = (until - self._utc_now()).total_seconds()
        if remaining > self._cooldown_remaining():
            self._set_cooldown(remaining)

    async def _activate_youtube_cooldown(self) -> None:
        """Persist current work and cooldown atomically, then update local cache."""
        seconds = self.policy.youtube_cooldown_seconds
        setter = getattr(self.channel_repo, "set_youtube_cooldown_until", None)
        try:
            if setter is not None:
                await setter(self._utc_now() + timedelta(seconds=seconds))
            await self._commit(invalidate_cache=False)
        except BaseException:
            await self.session.rollback()
            raise
        self._set_cooldown(seconds)

    async def _refresh_channel_video_list_without_lock(
        self,
        channel: YouTubeChannel,
    ) -> ChannelVideoRefreshResult:
        """Refresh recent metadata without deleting videos or extracted songs."""
        remaining = self._cooldown_remaining()
        if remaining > 0:
            self.status.set(
                UpdaterPhase.COOLDOWN,
                detail=f"YouTube cooldown active ({remaining:.0f}s remaining)",
                channel_id=channel.id,
                channel_name=channel.name,
                clear_video=True,
            )
            raise YouTubeAccessBlocked(
                f"YouTube cooldown active ({remaining:.0f}s remaining)"
            )

        self.status.set(
            UpdaterPhase.SCRAPING_VIDEOS,
            detail=f"Refreshing video metadata for {channel.name}",
            channel_id=channel.id,
            channel_name=channel.name,
            clear_video=True,
            clear_error=True,
        )
        try:
            scraped = await self._scrape_channel_videos(
                channel,
                full_metadata=True,
            )
        except YouTubeAccessBlocked:
            self.status.set(
                UpdaterPhase.COOLDOWN,
                detail=f"YouTube blocked while refreshing {channel.name}",
                channel_id=channel.id,
                channel_name=channel.name,
            )
            raise
        except Exception:
            self._set_manual_channel_error(channel)
            raise

        videos = await self.video_repo.upsert_many(scraped)
        reclassified = await self.video_repo.reclassify_for_channel(channel.id)
        logger.info(
            "Channel %s safe metadata refresh done scraped=%s reclassified=%s",
            channel.id,
            len(videos),
            reclassified,
        )
        self.status.set(
            self._manual_operation_resting_phase(),
            detail=f"Safe metadata refresh finished for {channel.name}",
            channel_id=channel.id,
            channel_name=channel.name,
            clear_video=True,
        )
        return ChannelVideoRefreshResult(
            channel_id=channel.id,
            mode="refresh",
            scraped=len(videos),
            deleted=0,
            reclassified=reclassified,
            cleared=0,
            message=(
                f"Refreshed {len(videos)} recent video(s), reclassified "
                f"{reclassified}, without deleting videos, comments, or "
                "existing setlists."
            ),
        )

    async def _process_channel(self, channel: YouTubeChannel) -> bool:
        return await self._channel_cycle.process(channel)

    async def _process_analysis_queue(self) -> None:
        """Analyze a global, due queue independently from channel discovery."""
        remaining = (
            self.policy.comment_scrapes_per_cycle - self._comment_scrapes_this_cycle
        )
        if remaining <= 0:
            return
        videos = await self.video_repo.get_analysis_queue(
            max_attempts=self.policy.max_analysis_attempts,
            limit=remaining,
        )
        logger.info(
            "Global analysis queue returned %s video(s) (cycle cap=%s)",
            len(videos),
            self.policy.comment_scrapes_per_cycle,
        )
        for video in videos:
            if (
                self._comment_scrapes_this_cycle
                >= self.policy.comment_scrapes_per_cycle
            ):
                return
            await self._process_analysis_queue_video(video)

    async def _process_analysis_queue_video(self, video: YouTubeVideo) -> None:
        try:
            await self._analyze_video(video)
            await self._commit()
        except asyncio.CancelledError:
            await self.session.rollback()
            raise
        except YouTubeAccessBlocked:
            raise
        except RetryableVideoAnalysisError:
            await self._commit()
            logger.warning(
                "Retryable scraper failure analyzing video %s; continuing",
                video.id,
            )
            self.status.set(
                UpdaterPhase.ERROR,
                detail="Video comments could not be fetched and were rescheduled",
                clear_channel=True,
                video_id=video.id,
                video_title=video.title,
                last_error="A video comment request failed",
            )
        except Exception:
            await self.session.rollback()
            logger.exception(
                "Non-block failure analyzing video %s; continuing",
                video.id,
            )
            self.status.set(
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
        self,
        channel: YouTubeChannel,
    ) -> YouTubeChannel | None:
        return await self._channel_videos.backfill_page(channel)

    async def _scrape_channel_videos(
        self,
        channel: YouTubeChannel,
        *,
        full_metadata: bool = False,
    ) -> list[YouTubeVideo]:
        return await self._channel_videos.scrape_channel_videos(
            channel,
            full_metadata=full_metadata,
        )

    async def _analyze_video(self, video: YouTubeVideo) -> None:
        await self._video_analysis.analyze(
            video,
            before_followup_scrape=self._jitter_sleep,
        )

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
        self.status.set(
            UpdaterPhase.JITTER,
            detail=f"Inter-scrape pause ({delay:.1f}s)",
            clear_video=True,
            comment_scrapes_this_cycle=self._comment_scrapes_this_cycle,
        )
        await asyncio.sleep(delay)

    async def _list_jitter_sleep(self) -> None:
        low = min(
            self.policy.inter_list_sleep_min,
            self.policy.inter_list_sleep_max,
        )
        high = max(
            self.policy.inter_list_sleep_min,
            self.policy.inter_list_sleep_max,
        )
        delay = random.uniform(low, high)
        logger.info("Backfill page pause: sleeping %.1fs", delay)
        self.status.set(
            UpdaterPhase.JITTER,
            detail=f"Backfill page pause ({delay:.1f}s)",
            clear_video=True,
            comment_scrapes_this_cycle=self._comment_scrapes_this_cycle,
        )
        await asyncio.sleep(delay)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)
