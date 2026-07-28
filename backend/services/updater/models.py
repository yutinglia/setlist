"""Shared state and outcomes for updater collaborators."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CycleProgress:
    """Mutable per-cycle work counters shared by focused updater services."""

    comment_scrapes: int = 0
    backfill_channels: int = 0
    steady_channels: int = 0

    def reset(self) -> None:
        self.comment_scrapes = 0
        self.backfill_channels = 0
        self.steady_channels = 0


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


class RetryableVideoAnalysisError(Exception):
    """A scraper failure whose retry state is safe to commit.

    This separates expected upstream failures from analyzer/programming errors.
    The analysis queue commits the retry schedule for this exception only;
    unexpected failures roll the complete per-video transaction back.
    """
