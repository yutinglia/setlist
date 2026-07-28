"""Process-local live status for the background DataUpdater.

In-memory only (resets on process restart). Safe for concurrent reads from
HTTP handlers while the updater loop mutates phase details.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class UpdaterPhase(StrEnum):
    IDLE = "idle"
    WAITING = "waiting"
    COOLDOWN = "cooldown"
    STARTING = "starting"
    FETCHING_CHANNELS = "fetching_channels"
    REFRESHING_CHANNEL = "refreshing_channel"
    SCRAPING_VIDEOS = "scraping_videos"
    BACKFILLING_VIDEOS = "backfilling_videos"
    RECLASSIFYING = "reclassifying"
    SCRAPING_COMMENTS = "scraping_comments"
    ANALYZING = "analyzing"
    LLM_CLEANING = "llm_cleaning"
    JITTER = "jitter"
    COMMITTING = "committing"
    ERROR = "error"


@dataclass
class _StatusState:
    phase: UpdaterPhase = UpdaterPhase.IDLE
    detail: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    video_id: str | None = None
    video_title: str | None = None
    cycle_started_at: datetime | None = None
    last_cycle_finished_at: datetime | None = None
    last_error: str | None = None
    comment_scrapes_this_cycle: int = 0
    is_cycle_active: bool = False
    updated_at: datetime | None = None


class UpdaterStatusTracker:
    """Thread-safe snapshot of what the scraper/analyzer is doing right now."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = _StatusState(updated_at=_utc_now())

    def set(
        self,
        phase: UpdaterPhase,
        *,
        detail: str | None = None,
        channel_id: str | None = None,
        channel_name: str | None = None,
        video_id: str | None = None,
        video_title: str | None = None,
        comment_scrapes_this_cycle: int | None = None,
        clear_channel: bool = False,
        clear_video: bool = False,
        last_error: str | None = None,
        clear_error: bool = False,
    ) -> None:
        with self._lock:
            s = self._state
            s.phase = phase
            s.detail = detail
            s.updated_at = _utc_now()
            self._update_channel(
                s,
                clear=clear_channel,
                channel_id=channel_id,
                channel_name=channel_name,
            )
            self._update_video(
                s,
                clear=clear_video,
                video_id=video_id,
                video_title=video_title,
            )
            if comment_scrapes_this_cycle is not None:
                s.comment_scrapes_this_cycle = comment_scrapes_this_cycle
            self._update_error(
                s,
                clear=clear_error,
                last_error=last_error,
            )

    @staticmethod
    def _update_channel(
        state: _StatusState,
        *,
        clear: bool,
        channel_id: str | None,
        channel_name: str | None,
    ) -> None:
        if clear:
            state.channel_id = None
            state.channel_name = None
            return
        if channel_id is not None:
            state.channel_id = channel_id
        if channel_name is not None:
            state.channel_name = channel_name

    @staticmethod
    def _update_video(
        state: _StatusState,
        *,
        clear: bool,
        video_id: str | None,
        video_title: str | None,
    ) -> None:
        if clear:
            state.video_id = None
            state.video_title = None
            return
        if video_id is not None:
            state.video_id = video_id
        if video_title is not None:
            state.video_title = video_title

    @staticmethod
    def _update_error(
        state: _StatusState,
        *,
        clear: bool,
        last_error: str | None,
    ) -> None:
        if clear:
            state.last_error = None
        elif last_error is not None:
            state.last_error = last_error

    def begin_cycle(self) -> None:
        with self._lock:
            s = self._state
            now = _utc_now()
            s.is_cycle_active = True
            s.cycle_started_at = now
            s.comment_scrapes_this_cycle = 0
            s.phase = UpdaterPhase.STARTING
            s.detail = "Starting update cycle"
            s.channel_id = None
            s.channel_name = None
            s.video_id = None
            s.video_title = None
            s.last_error = None
            s.updated_at = now

    def end_cycle(
        self,
        *,
        error: str | None = None,
        phase: UpdaterPhase | None = None,
        detail: str | None = None,
    ) -> None:
        with self._lock:
            s = self._state
            now = _utc_now()
            if s.is_cycle_active:
                s.last_cycle_finished_at = now
            s.is_cycle_active = False
            s.channel_id = None
            s.channel_name = None
            s.video_id = None
            s.video_title = None
            s.updated_at = now
            if error:
                s.phase = phase or UpdaterPhase.ERROR
                s.detail = detail or error
                s.last_error = error
            elif phase is not None:
                s.phase = phase
                s.detail = detail
            else:
                s.phase = UpdaterPhase.WAITING
                s.detail = detail or "Waiting for next update cycle"

    def stop(self, *, detail: str = "Updater stopped") -> None:
        """Mark the updater inactive and close an active cycle if necessary."""
        with self._lock:
            s = self._state
            now = _utc_now()
            if s.is_cycle_active:
                s.last_cycle_finished_at = now
            s.phase = UpdaterPhase.IDLE
            s.detail = detail
            s.channel_id = None
            s.channel_name = None
            s.video_id = None
            s.video_title = None
            s.last_error = None
            s.is_cycle_active = False
            s.updated_at = now

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            s = self._state
            return {
                "phase": s.phase.value,
                "detail": s.detail,
                "channel_id": s.channel_id,
                "channel_name": s.channel_name,
                "video_id": s.video_id,
                "video_title": s.video_title,
                "cycle_started_at": s.cycle_started_at,
                "last_cycle_finished_at": s.last_cycle_finished_at,
                "last_error": s.last_error,
                "comment_scrapes_this_cycle": s.comment_scrapes_this_cycle,
                "is_cycle_active": s.is_cycle_active,
                "updated_at": s.updated_at,
            }


# Singleton used by DataUpdater, main loop, and the status HTTP route.
updater_status = UpdaterStatusTracker()
