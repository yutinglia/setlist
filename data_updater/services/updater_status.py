"""Process-local live status for the background DataUpdater.

In-memory only (resets on process restart). Safe for concurrent reads from
HTTP handlers while the updater loop mutates phase details.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UpdaterPhase(str, Enum):
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
    detail: Optional[str] = None
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    video_id: Optional[str] = None
    video_title: Optional[str] = None
    cycle_started_at: Optional[datetime] = None
    last_cycle_finished_at: Optional[datetime] = None
    last_error: Optional[str] = None
    comment_scrapes_this_cycle: int = 0
    is_cycle_active: bool = False
    updated_at: Optional[datetime] = None


class UpdaterStatusTracker:
    """Thread-safe snapshot of what the scraper/analyzer is doing right now."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = _StatusState(updated_at=_utc_now())

    def set(
        self,
        phase: UpdaterPhase,
        *,
        detail: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
        video_id: Optional[str] = None,
        video_title: Optional[str] = None,
        comment_scrapes_this_cycle: Optional[int] = None,
        clear_channel: bool = False,
        clear_video: bool = False,
        last_error: Optional[str] = None,
        clear_error: bool = False,
    ) -> None:
        with self._lock:
            s = self._state
            s.phase = phase
            s.detail = detail
            s.updated_at = _utc_now()
            if clear_channel:
                s.channel_id = None
                s.channel_name = None
            elif channel_id is not None or channel_name is not None:
                if channel_id is not None:
                    s.channel_id = channel_id
                if channel_name is not None:
                    s.channel_name = channel_name
            if clear_video:
                s.video_id = None
                s.video_title = None
            elif video_id is not None or video_title is not None:
                if video_id is not None:
                    s.video_id = video_id
                if video_title is not None:
                    s.video_title = video_title
            if comment_scrapes_this_cycle is not None:
                s.comment_scrapes_this_cycle = comment_scrapes_this_cycle
            if clear_error:
                s.last_error = None
            elif last_error is not None:
                s.last_error = last_error

    def begin_cycle(self) -> None:
        with self._lock:
            s = self._state
            s.is_cycle_active = True
            s.cycle_started_at = _utc_now()
            s.comment_scrapes_this_cycle = 0
            s.phase = UpdaterPhase.STARTING
            s.detail = "Starting update cycle"
            s.channel_id = None
            s.channel_name = None
            s.video_id = None
            s.video_title = None
            s.last_error = None
            s.updated_at = _utc_now()

    def end_cycle(
        self,
        *,
        error: Optional[str] = None,
        phase: Optional[UpdaterPhase] = None,
        detail: Optional[str] = None,
    ) -> None:
        with self._lock:
            s = self._state
            s.is_cycle_active = False
            s.last_cycle_finished_at = _utc_now()
            s.channel_id = None
            s.channel_name = None
            s.video_id = None
            s.video_title = None
            s.updated_at = _utc_now()
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
