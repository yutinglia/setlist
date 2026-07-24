"""DataUpdater: scrape → analyze → persist with Tier B YouTube pacing."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    LLM_API_KEY,
    LLM_CLEANING_ENABLED,
    LLM_MAX_CLEANING_ATTEMPTS,
    LLM_MODEL,
    UPDATE_MAX_ANALYZE_ATTEMPTS,
    UPDATE_MAX_COMMENT_SCRAPES,
    UPDATE_MAX_COMMENTS_PER_VIDEO,
    UPDATE_MAX_VIDEOS,
    UPDATE_SCRAPE_SLEEP_MAX,
    UPDATE_SCRAPE_SLEEP_MIN,
    UPDATE_YOUTUBE_COOLDOWN_SECONDS,
    YTDLP_COMMENT_MAX_SLEEP_INTERVAL,
    YTDLP_COMMENT_SLEEP_INTERVAL,
)
from models.channel import YouTubeChannel
from models.song import Song
from models.video import YouTubeVideo
from repositories.channel_repository import ChannelRepository
from repositories.song_repository import SongRepository
from repositories.video_repository import VideoRepository
from services.analyzer.llm_cleaner import maybe_clean_song_list_comment
from services.analyzer.yt_comment_analyzer import CommentAnalyzer
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
    """Outcome of a manual channel video-list force reload (no comment analysis)."""

    channel_id: str
    mode: str  # "force" | "reclassify"
    scraped: int
    deleted: int
    reclassified: int
    cleared: int
    message: str

logger = logging.getLogger(__name__)


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
        seconds = (
            UPDATE_YOUTUBE_COOLDOWN_SECONDS if seconds is None else seconds
        )
        cls._youtube_cooldown_until = time.monotonic() + max(0.0, seconds)
        logger.warning(
            "YouTube cooldown set for %ss (until monotonic+%.0f)",
            seconds,
            seconds,
        )

    async def update(self) -> None:
        remaining = self.youtube_cooldown_remaining()
        if remaining > 0:
            logger.warning(
                "Skipping update cycle: YouTube cooldown active (%.0fs remaining)",
                remaining,
            )
            return

        self._comment_scrapes_this_cycle = 0
        logger.info(
            "Starting update cycle (max_videos=%s, max_comment_scrapes=%s, "
            "jitter=%.1f–%.1fs, max_attempts=%s)",
            UPDATE_MAX_VIDEOS,
            UPDATE_MAX_COMMENT_SCRAPES,
            UPDATE_SCRAPE_SLEEP_MIN,
            UPDATE_SCRAPE_SLEEP_MAX,
            UPDATE_MAX_ANALYZE_ATTEMPTS,
        )

        try:
            channels = await self.channel_repo.get_all()
            logger.info("Fetched %s channels from the database.", len(channels))

            for channel in channels:
                if self.youtube_cooldown_remaining() > 0:
                    logger.warning(
                        "Cooldown active mid-cycle; stopping remaining channels"
                    )
                    break
                if self._comment_scrapes_this_cycle >= UPDATE_MAX_COMMENT_SCRAPES:
                    logger.info(
                        "Comment scrape cap reached (%s); skipping remaining channels",
                        UPDATE_MAX_COMMENT_SCRAPES,
                    )
                    break

                try:
                    await self._process_channel(channel)
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
                    break
                except Exception:
                    await self.session.rollback()
                    logger.exception(
                        "Non-block failure for channel %s; continuing", channel.id
                    )
        except Exception:
            await self.session.rollback()
            raise

    async def refresh_channel_video_list(
        self, channel: YouTubeChannel
    ) -> ChannelVideoRefreshResult:
        """Force-reload: full-metadata scrape, then replace all channel videos.

        Flat tab lists omit ``upload_date``, so a soft upsert never fills dates.
        This scrapes with full metadata first, then deletes existing video/song
        rows and inserts the new list (same transaction — scrape failure keeps
        old rows).

        Does **not** scrape comments / setlists.
        """
        remaining = self.youtube_cooldown_remaining()
        scraped_count = 0
        deleted_before = 0
        mode = "reclassify"
        message = "Reclassified types and cleared non-karaoke analysis."
        scrape_ok = False

        if remaining > 0:
            message = (
                f"YouTube cooldown active ({remaining:.0f}s left); "
                "skipped delete+rescrape; reclassified only."
            )
            logger.warning(
                "Channel %s force reload: cooldown %.0fs; reclassify-only",
                channel.id,
                remaining,
            )
        else:
            try:
                # Scrape first so a YouTube failure does not wipe the DB.
                scraped = await self._scrape_channel_videos(
                    channel, full_metadata=True
                )
                deleted_before = await self.video_repo.delete_all_for_channel(
                    channel.id
                )
                videos = await self.video_repo.upsert_many(scraped)
                scraped_count = len(videos)
                scrape_ok = True
                mode = "force"
                message = (
                    f"Force reloaded: deleted {deleted_before}, "
                    f"scraped {scraped_count} video(s) with dates."
                )
                logger.info(
                    "Channel %s force reload: deleted %s, upserted %s",
                    channel.id,
                    deleted_before,
                    scraped_count,
                )
            except YouTubeAccessBlocked as exc:
                self.set_youtube_cooldown()
                message = (
                    f"YouTube blocked ({exc}); "
                    "kept existing rows; skipped clear."
                )
                logger.warning(
                    "Channel %s force reload blocked: %s",
                    channel.id,
                    exc,
                )
            except Exception as exc:
                logger.exception(
                    "Channel %s force reload scrape failed; reclassify-only",
                    channel.id,
                )
                message = (
                    f"YouTube scrape failed ({exc}); kept existing rows; "
                    "skipped clear."
                )

        reclassified = await self.video_repo.reclassify_for_channel(channel.id)
        deleted_other = 0
        cleared_ids: list[str] = []
        # Destructive cleanup only after a successful replace. A failed scrape
        # must not wipe setlists on the rows we intentionally kept.
        if scrape_ok:
            deleted_other = await self.video_repo.delete_non_persisted_for_channel(
                channel.id
            )
            cleared_ids = await self.video_repo.clear_analysis_for_non_karaoke(
                channel.id,
                max_attempts=UPDATE_MAX_ANALYZE_ATTEMPTS,
            )
            for video_id in cleared_ids:
                await self.song_repo.replace_for_video(video_id, [])
        else:
            logger.warning(
                "Channel %s: force scrape did not succeed — "
                "skipping delete/clear of analysis (reclassify only)",
                channel.id,
            )

        logger.info(
            "Channel %s force reload done mode=%s deleted=%s scraped=%s "
            "reclassified=%s deleted_other=%s cleared=%s",
            channel.id,
            mode,
            deleted_before,
            scraped_count,
            reclassified,
            deleted_other,
            len(cleared_ids),
        )
        return ChannelVideoRefreshResult(
            channel_id=channel.id,
            mode=mode,
            scraped=scraped_count,
            deleted=deleted_before,
            reclassified=reclassified,
            cleared=len(cleared_ids) + deleted_other,
            message=(
                f"{message} Removed {deleted_other} other video(s); "
                f"cleared analysis on {len(cleared_ids)}."
            ),
        )

    async def _process_channel(self, channel: YouTubeChannel) -> None:
        logger.info("Processing channel %s (%s)", channel.name, channel.id)

        # Optional metadata refresh when seed row has no raw_data yet.
        if channel.raw_data is None:
            channel = await self._refresh_channel(channel)

        videos = await self._scrape_and_upsert_videos(channel)
        if not videos:
            logger.info("No videos to consider for channel %s", channel.id)
            return

        # Keep types aligned; drop chatter/other; clear stray song analysis.
        await self.video_repo.reclassify_for_channel(channel.id)
        deleted = await self.video_repo.delete_non_persisted_for_channel(channel.id)
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

        remaining_scrapes = UPDATE_MAX_COMMENT_SCRAPES - self._comment_scrapes_this_cycle
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

        for index, video in enumerate(needing):
            if self._comment_scrapes_this_cycle >= UPDATE_MAX_COMMENT_SCRAPES:
                logger.info(
                    "Hit UPDATE_MAX_COMMENT_SCRAPES=%s; stopping comment scrapes",
                    UPDATE_MAX_COMMENT_SCRAPES,
                )
                break

            if index > 0:
                await self._jitter_sleep()

            try:
                await self._analyze_video(video)
            except YouTubeAccessBlocked:
                raise
            except Exception:
                logger.exception(
                    "Non-block failure analyzing video %s; continuing", video.id
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
            ).get_channel_videos()

        try:
            scraped = await asyncio.to_thread(_scrape)
        except Exception as exc:
            raise_if_block_error(exc)
            raise

        # Prefer recent uploads across Streams + Videos; empty dates sort last.
        scraped_sorted = sorted(
            scraped,
            key=lambda v: v.upload_date
            or upload_date_from_entry(
                v.raw_data if isinstance(v.raw_data, dict) else None
            )
            or "",
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

        self._comment_scrapes_this_cycle += 1
        logger.info(
            "Comment scrape %s/%s for karaoke stream %s (%s)",
            self._comment_scrapes_this_cycle,
            UPDATE_MAX_COMMENT_SCRAPES,
            video.id,
            video.title,
        )

        def _scrape_comments() -> list:
            scraper = YouTubeVideoCommentScraper(
                video.url,
                sleep_interval=YTDLP_COMMENT_SLEEP_INTERVAL,
                max_sleep_interval=YTDLP_COMMENT_MAX_SLEEP_INTERVAL,
            )
            return scraper.get_video_top_comments(UPDATE_MAX_COMMENTS_PER_VIDEO)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
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

        analyzer = CommentAnalyzer(comments, video_id=video.id)
        if analyzer.has_song_list_comment():
            songs = analyzer.extract_song_list()
            video.has_song_list_comment = True
            video.song_list_comment_raw_data = analyzer.song_list_comment
            songs = await self._maybe_llm_clean(video, analyzer, songs)
            await self.song_repo.replace_for_video(video.id, songs)
            logger.info(
                "Video %s: found setlist with %s song(s)", video.id, len(songs)
            )
        else:
            video.has_song_list_comment = False
            video.song_list_comment_raw_data = None
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

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        video.cleaning_attempts = attempts + 1
        video.last_cleaned_at = now

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
        await asyncio.sleep(delay)
