"""Offline reclassification and replay of persisted top-comment snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.video import ANALYSIS_DONE
from repositories.channel_repository import ChannelRepository
from repositories.song_repository import SongRepository
from repositories.video_repository import VideoRepository
from services.analyzer.yt_comment_analyzer import CommentAnalyzer
from services.youtube_operation_lock import (
    YouTubeUpdaterBusyError,
    youtube_operation_guard,
)
from utils.video_type import VIDEO_TYPE_KARAOKE


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
    skipped_cleaned_setlists: int
    songs_before: int
    songs_after: int


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
    ) -> None:
        self.session = session
        self.channel_repo = channel_repo
        self.video_repo = video_repo
        self.song_repo = song_repo
        self.max_analysis_attempts = max_analysis_attempts

    async def run(self, *, apply: bool = False) -> StoredDataReanalysisResult:
        async with youtube_operation_guard(self.session) as acquired:
            if not acquired:
                raise YouTubeUpdaterBusyError(
                    "Another updater process is currently using scraper data"
                )
            try:
                result = await self._run_without_lock(apply=apply)
                if apply:
                    await self.session.commit()
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
    ) -> StoredDataReanalysisResult:
        reclassified = 0
        cleared_ids: list[str] = []
        for channel in await self.channel_repo.get_all():
            reclassified += await self.video_repo.reclassify_for_channel(channel.id)
            cleared_ids.extend(
                await self.video_repo.clear_analysis_for_non_karaoke(
                    channel.id,
                    max_attempts=self.max_analysis_attempts,
                )
            )

        for video_id in cleared_ids:
            await self.song_repo.replace_for_video(video_id, [])

        stored_comment_videos = 0
        detected_setlists = 0
        recovered_setlists = 0
        changed_setlists = 0
        skipped_cleaned_setlists = 0
        songs_before = 0
        songs_after = 0
        analyzed_at = datetime.now(UTC).replace(tzinfo=None)

        for video in await self.video_repo.get_with_stored_comments():
            if video.type != VIDEO_TYPE_KARAOKE:
                continue
            comments = self._snapshot_comments(video.comments_raw_data)
            if comments is None:
                continue

            stored_comment_videos += 1
            existing_songs = await self.song_repo.get_by_video_id(video.id)
            songs_before += len(existing_songs)

            analyzer = CommentAnalyzer(comments, video_id=video.id)
            if not analyzer.has_song_list_comment():
                songs_after += len(existing_songs)
                continue

            detected_setlists += 1
            songs = analyzer.extract_song_list()
            if not songs:
                songs_after += len(existing_songs)
                continue

            if video.cleaned_song_list_comment is not None:
                skipped_cleaned_setlists += 1
                songs_after += len(existing_songs)
                continue
            songs_after += len(songs)

            old_pairs = [
                (song.timestamp or "", song.title.casefold().strip())
                for song in existing_songs
            ]
            new_pairs = [
                (song.timestamp or "", song.title.casefold().strip()) for song in songs
            ]
            newly_recovered = not video.has_song_list_comment
            changed = newly_recovered or old_pairs != new_pairs
            if not changed:
                continue

            recovered_setlists += int(newly_recovered)
            changed_setlists += 1
            video.has_song_list_comment = True
            video.analysis_status = ANALYSIS_DONE
            video.next_analysis_at = None
            video.last_analyzed_at = analyzed_at
            video.song_list_comment_raw_data = analyzer.song_list_comment
            video.cleaned_song_list_comment = None
            await self.song_repo.replace_for_video(video.id, songs)
            await self.video_repo.update_analysis(video)

        return StoredDataReanalysisResult(
            applied=apply,
            reclassified_videos=reclassified,
            cleared_non_karaoke_videos=len(cleared_ids),
            stored_comment_videos=stored_comment_videos,
            detected_setlists=detected_setlists,
            recovered_setlists=recovered_setlists,
            changed_setlists=changed_setlists,
            skipped_cleaned_setlists=skipped_cleaned_setlists,
            songs_before=songs_before,
            songs_after=songs_after,
        )

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
