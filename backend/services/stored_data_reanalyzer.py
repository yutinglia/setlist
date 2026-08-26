"""Offline reclassification and replay of persisted top-comment snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.song import Song
from models.video import ANALYSIS_DONE, YouTubeVideo
from repositories.channel_repository import ChannelRepository
from repositories.song_repository import SongRepository
from repositories.video_repository import VideoRepository
from services.analyzer.comment_attribution import apply_setlist_comment_attribution
from services.analyzer.yt_comment_analyzer import CommentAnalyzer
from services.cache import PUBLIC_CACHE_NAMESPACES, ResponseCache
from services.youtube_operation_lock import (
    YouTubeOperationCoordinator,
    YouTubeUpdaterBusyError,
    default_youtube_operation_coordinator,
)
from utils.video_type import VIDEO_TYPE_KARAOKE


class UnsafeStoredDataReanalysisError(RuntimeError):
    """Raised before commit when destructive candidates lack explicit approval."""

    def __init__(
        self,
        *,
        clear_video_ids: tuple[str, ...] = (),
        successful_video_ids: tuple[str, ...] = (),
    ) -> None:
        self.clear_video_ids = clear_video_ids
        self.successful_video_ids = successful_video_ids
        details: list[str] = []
        if clear_video_ids:
            details.append(f"song-clearing videos={','.join(clear_video_ids)}")
        if successful_video_ids:
            details.append(
                "successful-setlist rewrites=" + ",".join(successful_video_ids)
            )
        super().__init__(
            "Stored-data apply requires explicit per-video approval: "
            + "; ".join(details)
        )


@dataclass(frozen=True)
class StoredDataReanalysisResult:
    """Summary of one atomic stored-data maintenance pass."""

    applied: bool
    reclassified_videos: int
    cleared_non_karaoke_videos: int
    stored_comment_videos: int
    detected_setlists: int
    recovered_setlists: int
    changed_setlists: int
    skipped_existing_setlists: int
    skipped_cleaned_setlists: int
    requeued_unresolved_videos: int
    songs_before: int
    songs_after: int
    cleared_songs: int = 0
    destructive_clear_video_ids: tuple[str, ...] = ()
    recovered_video_ids: tuple[str, ...] = ()
    changed_successful_video_ids: tuple[str, ...] = ()


@dataclass
class _ReanalysisStats:
    reclassified_videos: int = 0
    cleared_non_karaoke_videos: int = 0
    stored_comment_videos: int = 0
    detected_setlists: int = 0
    recovered_setlists: int = 0
    changed_setlists: int = 0
    skipped_existing_setlists: int = 0
    skipped_cleaned_setlists: int = 0
    requeued_unresolved_videos: int = 0
    songs_before: int = 0
    songs_after: int = 0
    cleared_songs: int = 0
    destructive_clear_video_ids: list[str] = field(default_factory=list)
    recovered_video_ids: list[str] = field(default_factory=list)
    changed_successful_video_ids: list[str] = field(default_factory=list)

    def result(self, *, applied: bool) -> StoredDataReanalysisResult:
        return StoredDataReanalysisResult(
            applied=applied,
            reclassified_videos=self.reclassified_videos,
            cleared_non_karaoke_videos=self.cleared_non_karaoke_videos,
            stored_comment_videos=self.stored_comment_videos,
            detected_setlists=self.detected_setlists,
            recovered_setlists=self.recovered_setlists,
            changed_setlists=self.changed_setlists,
            skipped_existing_setlists=self.skipped_existing_setlists,
            skipped_cleaned_setlists=self.skipped_cleaned_setlists,
            requeued_unresolved_videos=self.requeued_unresolved_videos,
            songs_before=self.songs_before,
            songs_after=self.songs_after,
            cleared_songs=self.cleared_songs,
            destructive_clear_video_ids=tuple(sorted(self.destructive_clear_video_ids)),
            recovered_video_ids=tuple(sorted(self.recovered_video_ids)),
            changed_successful_video_ids=tuple(
                sorted(self.changed_successful_video_ids)
            ),
        )


class StoredDataReanalyzer:
    """Replay classifier/analyzer changes without contacting YouTube.

    The caller owns no transaction details: a dry run always rolls back, while
    ``apply=True`` commits the complete pass atomically. The shared operation
    guard prevents a background updater from writing scraper results at the
    same time.
    """

    def __init__(
        self,
        session: AsyncSession,
        channel_repo: ChannelRepository,
        video_repo: VideoRepository,
        song_repo: SongRepository,
        *,
        max_analysis_attempts: int,
        operations: YouTubeOperationCoordinator | None = None,
        cache: ResponseCache | None = None,
    ) -> None:
        self.session = session
        self.channel_repo = channel_repo
        self.video_repo = video_repo
        self.song_repo = song_repo
        self.max_analysis_attempts = max_analysis_attempts
        self.operations = operations or default_youtube_operation_coordinator
        self.cache = cache

    async def run(
        self,
        *,
        apply: bool = False,
        include_successful: bool = False,
        requeue_unresolved: bool = False,
        approved_clear_video_ids: frozenset[str] = frozenset(),
        approved_successful_video_ids: frozenset[str] = frozenset(),
    ) -> StoredDataReanalysisResult:
        async with self.operations.guard(self.session) as acquired:
            if not acquired:
                raise YouTubeUpdaterBusyError(
                    "Another updater process is currently using scraper data"
                )
            try:
                result = await self._run_without_lock(
                    apply=apply,
                    include_successful=include_successful,
                    requeue_unresolved=requeue_unresolved,
                    approved_clear_video_ids=approved_clear_video_ids,
                    approved_successful_video_ids=approved_successful_video_ids,
                )
                if apply:
                    await self.session.commit()
                    if self.cache is not None:
                        await self.cache.invalidate(*PUBLIC_CACHE_NAMESPACES)
                else:
                    await self.session.rollback()
                return result
            except BaseException:
                await self.session.rollback()
                raise

    async def _run_without_lock(
        self,
        *,
        apply: bool,
        include_successful: bool,
        requeue_unresolved: bool,
        approved_clear_video_ids: frozenset[str],
        approved_successful_video_ids: frozenset[str],
    ) -> StoredDataReanalysisResult:
        stats = _ReanalysisStats()
        await self._reclassify_stored_videos(stats)
        await self._replay_stored_comments(
            stats,
            include_successful=include_successful,
        )
        if requeue_unresolved:
            stats.requeued_unresolved_videos = (
                await self.video_repo.requeue_unresolved_karaoke(
                    max_attempts=self.max_analysis_attempts
                )
            )
        if apply:
            unapproved_clears = tuple(
                sorted(
                    set(stats.destructive_clear_video_ids) - approved_clear_video_ids
                )
            )
            unapproved_successful = tuple(
                sorted(
                    set(stats.changed_successful_video_ids)
                    - approved_successful_video_ids
                )
            )
            if unapproved_clears or unapproved_successful:
                raise UnsafeStoredDataReanalysisError(
                    clear_video_ids=unapproved_clears,
                    successful_video_ids=unapproved_successful,
                )
        return stats.result(applied=apply)

    async def _reclassify_stored_videos(
        self,
        stats: _ReanalysisStats,
    ) -> None:
        cleared_ids: list[str] = []
        for channel in await self.channel_repo.get_all():
            stats.reclassified_videos += await self.video_repo.reclassify_for_channel(
                channel.id
            )
            cleared_ids.extend(
                await self.video_repo.clear_analysis_for_non_karaoke(
                    channel.id,
                    max_attempts=self.max_analysis_attempts,
                )
            )

        for video_id in cleared_ids:
            existing_songs = await self.song_repo.get_by_video_id(video_id)
            if existing_songs:
                stats.cleared_songs += len(existing_songs)
                stats.destructive_clear_video_ids.append(video_id)
            await self.song_repo.replace_for_video(video_id, [])
        stats.cleared_non_karaoke_videos = len(cleared_ids)

    async def _replay_stored_comments(
        self,
        stats: _ReanalysisStats,
        *,
        include_successful: bool,
    ) -> None:
        analyzed_at = datetime.now(UTC).replace(tzinfo=None)
        for video in await self.video_repo.get_with_stored_comments():
            await self._replay_video(
                video,
                stats,
                analyzed_at=analyzed_at,
                include_successful=include_successful,
            )

    async def _replay_video(
        self,
        video: YouTubeVideo,
        stats: _ReanalysisStats,
        *,
        analyzed_at: datetime,
        include_successful: bool,
    ) -> None:
        if video.type != VIDEO_TYPE_KARAOKE:
            return
        comments = self._snapshot_comments(video.comments_raw_data)
        if comments is None:
            return

        stats.stored_comment_videos += 1
        existing_songs = await self.song_repo.get_by_video_id(video.id)
        stats.songs_before += len(existing_songs)
        if video.has_song_list_comment and not include_successful:
            stats.skipped_existing_setlists += 1
            stats.songs_after += len(existing_songs)
            return
        analyzer = CommentAnalyzer(comments, video_id=video.id)
        if not analyzer.has_song_list_comment():
            stats.songs_after += len(existing_songs)
            return

        stats.detected_setlists += 1
        songs = analyzer.extract_song_list()
        if not songs or video.cleaned_song_list_comment is not None:
            stats.skipped_cleaned_setlists += int(
                bool(songs) and video.cleaned_song_list_comment is not None
            )
            stats.songs_after += len(existing_songs)
            return

        stats.songs_after += len(songs)
        newly_recovered = not video.has_song_list_comment
        changed = newly_recovered or self._song_pairs(
            existing_songs
        ) != self._song_pairs(songs)
        if not changed:
            return

        stats.recovered_setlists += int(newly_recovered)
        if newly_recovered:
            stats.recovered_video_ids.append(video.id)
        else:
            stats.changed_successful_video_ids.append(video.id)
        stats.changed_setlists += 1
        video.has_song_list_comment = True
        video.analysis_status = ANALYSIS_DONE
        video.next_analysis_at = None
        video.last_analyzed_at = analyzed_at
        video.song_list_comment_raw_data = analyzer.song_list_comment
        apply_setlist_comment_attribution(video, analyzer.song_list_comment)
        video.cleaned_song_list_comment = None
        await self.song_repo.replace_for_video(video.id, songs)
        await self.video_repo.update_analysis(video)

    @staticmethod
    def _song_pairs(songs: list[Song]) -> list[tuple[str, str]]:
        return [(song.timestamp or "", song.title.casefold().strip()) for song in songs]

    @staticmethod
    def _snapshot_comments(
        snapshot: dict[str, Any] | None,
    ) -> list[dict[str, Any]] | None:
        if not isinstance(snapshot, dict):
            return None
        comments = snapshot.get("comments")
        if not isinstance(comments, list):
            return None
        return [comment for comment in comments if isinstance(comment, dict)]
