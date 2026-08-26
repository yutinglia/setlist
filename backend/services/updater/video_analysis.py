"""Per-video comment scraping, classification, and setlist persistence."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any

from config import LlmSettings
from models.song import Song
from models.video import (
    ANALYSIS_DONE,
    ANALYSIS_EXHAUSTED,
    ANALYSIS_NO_SETLIST,
    ANALYSIS_RETRY,
    ANALYSIS_SKIPPED,
    YouTubeVideo,
)
from repositories.song_repository import SongRepository
from repositories.video_repository import VideoRepository
from services.analyzer.comment_attribution import (
    apply_setlist_comment_attribution,
    clear_setlist_comment_attribution,
)
from services.analyzer.llm_cleaner import SongListCleaner
from services.analyzer.yt_comment_analyzer import CommentAnalyzer
from services.scrape_policy import ScrapePolicy
from services.scraping import ScraperFactory
from services.updater.models import (
    CycleProgress,
    RetryableVideoAnalysisError,
)
from services.updater_status import UpdaterPhase, UpdaterStatusTracker
from services.yt_scraper.errors import (
    YouTubeAccessBlocked,
    is_youtube_block_error,
)
from services.yt_scraper.video_comment_scraper import VideoCommentScrapeResult
from utils.video_type import (
    VIDEO_TYPE_KARAOKE,
    classify_video_type,
    should_scrape_comments,
)
from utils.youtube_upload_date import (
    UPLOAD_DATE_EXACT,
    upload_date_info_from_entry,
)
from utils.ytdlp_snapshot import (
    merged_video_metadata,
    snapshot_payload,
    snapshot_ytdlp_info,
)

logger = logging.getLogger(__name__)

ScrapeRunner = Callable[[Callable[[], Any]], Awaitable[Any]]
AsyncPause = Callable[[], Awaitable[None]]


class VideoAnalysisService:
    """Analyze a single video while keeping mutation rules in one place."""

    def __init__(
        self,
        video_repo: VideoRepository,
        song_repo: SongRepository,
        policy: ScrapePolicy,
        status: UpdaterStatusTracker,
        scraper_factory: ScraperFactory,
        run_scrape: ScrapeRunner,
        song_list_cleaner: SongListCleaner,
        llm_settings: LlmSettings,
        progress: CycleProgress,
    ) -> None:
        self.video_repo = video_repo
        self.song_repo = song_repo
        self.policy = policy
        self.status = status
        self.scraper_factory = scraper_factory
        self.run_scrape = run_scrape
        self.song_list_cleaner = song_list_cleaner
        self.llm_settings = llm_settings
        self.progress = progress

    async def analyze(
        self,
        video: YouTubeVideo,
        *,
        before_followup_scrape: AsyncPause,
    ) -> None:
        """Scrape, classify, analyze, and stage one video's complete result."""
        if await self._skip_ineligible_video(video):
            return
        if self.progress.comment_scrapes > 0:
            await before_followup_scrape()

        self.progress.comment_scrapes += 1
        self._report_comment_scrape(video)
        now = self._utc_now()
        attempts = (video.analyze_attempts or 0) + 1
        operation = self._comment_scrape_operation(video)
        try:
            scrape_result = await self.run_scrape(operation)
        except Exception as exc:
            await self._record_scrape_failure(
                video,
                exc,
                now=now,
                attempts=attempts,
            )
            raise AssertionError("scrape failure handler must raise") from exc

        await self._apply_scraped_metadata(video, scrape_result)
        comment_snapshot = self._comment_snapshot(scrape_result)
        video.analyze_attempts = attempts
        video.last_analyzed_at = now

        if video.type != VIDEO_TYPE_KARAOKE:
            await self._record_non_karaoke_result(video, comment_snapshot)
            return
        await self._analyze_comments(
            video,
            scrape_result.comments,
            comment_snapshot,
            now=now,
            attempts=attempts,
        )
        await self.video_repo.update_analysis(video)

    async def _skip_ineligible_video(self, video: YouTubeVideo) -> bool:
        raw = merged_video_metadata(video.raw_data, video.metadata_raw_data)
        eligible = should_scrape_comments(
            video.title or "",
            live_status=raw.get("live_status"),
            duration=raw.get("duration"),
            stored_type=video.type,
        )
        if eligible:
            return False
        logger.info(
            "Skipping comment analysis for %s video %s (%s)",
            video.type or "unknown",
            video.id,
            video.title,
        )
        video.analysis_status = ANALYSIS_SKIPPED
        video.next_analysis_at = None
        await self.video_repo.update_analysis(video)
        return True

    def _report_comment_scrape(self, video: YouTubeVideo) -> None:
        count = self.progress.comment_scrapes
        logger.info(
            "Comment scrape %s/%s for karaoke stream %s (%s)",
            count,
            self.policy.comment_scrapes_per_cycle,
            video.id,
            video.title,
        )
        self.status.set(
            UpdaterPhase.SCRAPING_COMMENTS,
            detail=(
                f"Scraping comments ({count}/{self.policy.comment_scrapes_per_cycle})"
            ),
            video_id=video.id,
            video_title=video.title,
            comment_scrapes_this_cycle=count,
        )

    def _comment_scrape_operation(
        self,
        video: YouTubeVideo,
    ) -> Callable[[], VideoCommentScrapeResult]:
        scraper = self.scraper_factory.video_comments(video.url)
        max_comments = (
            self.policy.max_comments_per_video
            if (video.analyze_attempts or 0) == 0
            else self.policy.max_recheck_comments_per_video
        )
        scrape = getattr(scraper, "scrape", None)
        if callable(scrape):
            return partial(scrape, max_comments)

        def scrape_compatibly() -> VideoCommentScrapeResult:
            comments = scraper.get_video_top_comments(max_comments)
            metadata = getattr(scraper, "video_metadata", {})
            return VideoCommentScrapeResult(
                comments=comments,
                comments_available=True,
                metadata_raw_data=snapshot_ytdlp_info(
                    metadata,
                    source="video_comments:test_compat",
                ),
                scraped_at=self._utc_now(),
            )

        return scrape_compatibly

    async def _record_scrape_failure(
        self,
        video: YouTubeVideo,
        exc: Exception,
        *,
        now: datetime,
        attempts: int,
    ) -> None:
        video.last_analyzed_at = now
        blocked = isinstance(exc, YouTubeAccessBlocked) or is_youtube_block_error(exc)
        if blocked:
            video.analysis_status = ANALYSIS_RETRY
            video.next_analysis_at = now + timedelta(
                seconds=self.policy.youtube_cooldown_seconds
            )
            await self.video_repo.update_analysis(video)
            raise YouTubeAccessBlocked(str(exc)) from exc

        video.analyze_attempts = attempts
        exhausted = attempts >= self.policy.max_analysis_attempts
        video.analysis_status = ANALYSIS_EXHAUSTED if exhausted else ANALYSIS_RETRY
        video.next_analysis_at = (
            None
            if exhausted
            else now
            + timedelta(
                seconds=self.policy.analysis_retry_base_seconds
                * (2 ** min(attempts - 1, 5))
            )
        )
        await self.video_repo.update_analysis(video)
        raise RetryableVideoAnalysisError(str(exc)) from exc

    async def _apply_scraped_metadata(
        self,
        video: YouTubeVideo,
        scrape_result: VideoCommentScrapeResult,
    ) -> None:
        scraped_metadata = snapshot_payload(scrape_result.metadata_raw_data)
        exact_date = upload_date_info_from_entry(scraped_metadata)
        if exact_date and (
            video.upload_date != exact_date.value
            or video.upload_date_precision != UPLOAD_DATE_EXACT
        ):
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

    async def _record_non_karaoke_result(
        self,
        video: YouTubeVideo,
        comment_snapshot: dict[str, Any],
    ) -> None:
        self.record_comments_observation(
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

    async def _analyze_comments(
        self,
        video: YouTubeVideo,
        comments: list[dict[str, Any]],
        comment_snapshot: dict[str, Any],
        *,
        now: datetime,
        attempts: int,
    ) -> None:
        self.status.set(
            UpdaterPhase.ANALYZING,
            detail="Analyzing comments for setlist",
            video_id=video.id,
            video_title=video.title,
            comment_scrapes_this_cycle=self.progress.comment_scrapes,
        )
        analyzer = CommentAnalyzer(comments, video_id=video.id)
        has_timestamp_comment = analyzer.has_song_list_comment()
        songs = analyzer.extract_song_list() if has_timestamp_comment else []
        if songs:
            await self._record_setlist(video, analyzer, songs, comment_snapshot)
            return
        await self._record_no_setlist(
            video,
            comment_snapshot,
            now=now,
            attempts=attempts,
            timestamp_comment=has_timestamp_comment,
        )

    async def _record_setlist(
        self,
        video: YouTubeVideo,
        analyzer: CommentAnalyzer,
        songs: list[Song],
        comment_snapshot: dict[str, Any],
    ) -> None:
        self.record_comments_observation(
            video,
            comment_snapshot,
            preserve_existing=False,
        )
        video.has_song_list_comment = True
        video.analysis_status = ANALYSIS_DONE
        video.next_analysis_at = None
        video.song_list_comment_raw_data = analyzer.song_list_comment
        apply_setlist_comment_attribution(video, analyzer.song_list_comment)
        video.cleaned_song_list_comment = None
        final_songs = await self.maybe_llm_clean(video, analyzer, songs)
        await self.song_repo.replace_for_video(video.id, final_songs)
        logger.info(
            "Video %s: found setlist with %s song(s)",
            video.id,
            len(final_songs),
        )

    async def _record_no_setlist(
        self,
        video: YouTubeVideo,
        comment_snapshot: dict[str, Any],
        *,
        now: datetime,
        attempts: int,
        timestamp_comment: bool,
    ) -> None:
        self.record_comments_observation(
            video,
            comment_snapshot,
            preserve_existing=video.has_song_list_comment,
        )
        cleared = self.record_no_setlist_result(video, now, attempts)
        if cleared:
            await self.song_repo.replace_for_video(video.id, [])
        detail = (
            "timestamp comment had no parseable songs"
            if timestamp_comment
            else "no setlist comment found"
        )
        logger.info("Video %s: %s", video.id, detail)

    @staticmethod
    def _comment_snapshot(
        scrape_result: VideoCommentScrapeResult,
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = {
            "schema_version": 1,
            "comments": scrape_result.comments,
            "comments_available": scrape_result.comments_available,
            "captured_at": scrape_result.scraped_at.isoformat() + "Z",
            "source": "yt-dlp:top",
        }
        requested = scrape_result.requested_max_comments
        if requested is not None:
            returned = len(scrape_result.comments)
            reported = scrape_result.reported_comment_count
            snapshot["schema_version"] = 2
            snapshot["retrieval"] = {
                "requested_max_comments": requested,
                "returned_comments": returned,
                "reported_comment_count": reported,
                "comment_sort": scrape_result.comment_sort,
                "max_replies": scrape_result.max_replies,
                "max_depth": scrape_result.max_depth,
                "possibly_truncated": bool(
                    scrape_result.comments_available
                    and (
                        returned >= requested
                        or (reported is not None and reported > returned)
                    )
                ),
                "yt_dlp_version": scrape_result.yt_dlp_version,
            }
        return snapshot

    @staticmethod
    def record_comments_observation(
        video: YouTubeVideo,
        snapshot: dict[str, Any],
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

    def record_no_setlist_result(
        self,
        video: YouTubeVideo,
        now: datetime,
        attempts: int,
    ) -> bool:
        """Record an absence without erasing a prior successful extraction."""
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
        clear_setlist_comment_attribution(video)
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
        video.analysis_status = ANALYSIS_NO_SETLIST
        video.next_analysis_at = now + timedelta(
            seconds=self.policy.analysis_recheck_seconds * attempts
        )

    async def maybe_llm_clean(
        self,
        video: YouTubeVideo,
        analyzer: CommentAnalyzer,
        songs: list[Song],
    ) -> list[Song]:
        """Optionally LLM-clean the setlist; keep regex songs on skip/failure."""
        if not self._llm_cleaning_available(video):
            return songs

        raw_text = ""
        if analyzer.song_list_comment:
            raw_text = analyzer.song_list_comment.get("text", "") or ""
        video.cleaning_attempts = (video.cleaning_attempts or 0) + 1
        video.last_cleaned_at = self._utc_now()
        self.status.set(
            UpdaterPhase.LLM_CLEANING,
            detail="LLM-cleaning setlist comment",
            video_id=video.id,
            video_title=video.title,
        )
        cleaned = await self.song_list_cleaner.clean(raw_text)
        if cleaned is None:
            return songs

        video.cleaned_song_list_comment = {
            "text": cleaned,
            "source": "llm",
            "model": self.llm_settings.model,
        }
        llm_songs = analyzer.extract_from_text(cleaned, analyzed_by_llm=True)
        return self._select_song_list(video, regex_songs=songs, llm_songs=llm_songs)

    def _llm_cleaning_available(self, video: YouTubeVideo) -> bool:
        if not self.llm_settings.enabled:
            return False
        if not self.llm_settings.api_key:
            logger.warning(
                "LLM_CLEANING_ENABLED set but LLM_API_KEY empty; skipping clean"
            )
            return False
        attempts = video.cleaning_attempts or 0
        if attempts < self.llm_settings.max_cleaning_attempts:
            return True
        logger.info(
            "Video %s: LLM cleaning skipped (attempts=%s >= max=%s)",
            video.id,
            attempts,
            self.llm_settings.max_cleaning_attempts,
        )
        return False

    @staticmethod
    def _select_song_list(
        video: YouTubeVideo,
        *,
        regex_songs: list[Song],
        llm_songs: list[Song],
    ) -> list[Song]:
        if not llm_songs:
            logger.warning(
                "Video %s: LLM clean returned no parseable songs; keeping regex list",
                video.id,
            )
            return regex_songs
        if len(llm_songs) >= len(regex_songs):
            logger.info(
                "Video %s: using LLM-cleaned setlist (%s songs, was %s)",
                video.id,
                len(llm_songs),
                len(regex_songs),
            )
            return llm_songs
        logger.info(
            "Video %s: LLM setlist shorter (%s < %s); keeping regex list",
            video.id,
            len(llm_songs),
            len(regex_songs),
        )
        return regex_songs

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)
