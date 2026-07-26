"""DTO for live scraper/analyzer status."""

from datetime import datetime

from pydantic import BaseModel, Field


class UpdaterStatusResponse(BaseModel):
    """What the background DataUpdater is doing right now."""

    phase: str = Field(
        description=(
            "Current phase: idle, waiting, cooldown, starting, fetching_channels, "
            "refreshing_channel, scraping_videos, backfilling_videos, reclassifying, "
            "scraping_comments, analyzing, llm_cleaning, jitter, committing, error"
        )
    )
    detail: str | None = Field(
        default=None, description="Human-readable description of current work"
    )
    channel_id: str | None = None
    channel_name: str | None = None
    video_id: str | None = None
    video_title: str | None = None
    cycle_started_at: datetime | None = None
    last_cycle_finished_at: datetime | None = None
    last_error: str | None = None
    persistent_cycle_started_at: datetime | None = None
    persistent_cycle_finished_at: datetime | None = None
    persistent_last_success_at: datetime | None = None
    persistent_heartbeat_at: datetime | None = None
    persistent_outcome: str = Field(
        description=(
            "Database-backed lifecycle outcome: never, running, success, "
            "cooldown, error, or cancelled"
        )
    )
    persistent_owner_id: str | None = Field(
        default=None,
        description="Process identity that most recently owned the updater lock",
    )
    is_stalled: bool = Field(
        description="True when a running cycle has exceeded the heartbeat deadline"
    )
    heartbeat_stale_seconds: float = Field(
        gt=0, description="Heartbeat age that marks a running updater as stalled"
    )
    comment_scrapes_this_cycle: int = Field(ge=0)
    comment_scrape_cap: int = Field(
        ge=0, description="UPDATE_MAX_COMMENT_SCRAPES for this process"
    )
    is_cycle_active: bool = Field(
        description="True while a periodic background update cycle is running"
    )
    background_updater_enabled: bool = Field(
        description="Whether the periodic updater is enabled for this process"
    )
    youtube_cooldown_remaining_seconds: float = Field(
        ge=0, description="Seconds left on YouTube block cooldown, or 0"
    )
    update_interval_seconds: int = Field(
        ge=0, description="Seconds between update cycles (DATA_UPDATE_INTERVAL)"
    )
    steady_scan_interval_seconds: int = Field(
        ge=0, description="Minimum successful discovery interval per channel"
    )
    backfill_page_size: int = Field(
        ge=1, description="Playlist entries requested from each tab per page"
    )
    backfill_pages_per_cycle: int = Field(
        ge=1, description="Maximum durable pages per backfill channel per cycle"
    )
    updated_at: datetime | None = Field(
        default=None, description="When this status snapshot was last mutated"
    )
