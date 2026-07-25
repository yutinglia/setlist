"""DTO for live scraper/analyzer status."""

from datetime import datetime
from typing import Optional

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
    detail: Optional[str] = Field(
        default=None, description="Human-readable description of current work"
    )
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    video_id: Optional[str] = None
    video_title: Optional[str] = None
    cycle_started_at: Optional[datetime] = None
    last_cycle_finished_at: Optional[datetime] = None
    last_error: Optional[str] = None
    comment_scrapes_this_cycle: int = Field(ge=0)
    comment_scrape_cap: int = Field(
        ge=0, description="UPDATE_MAX_COMMENT_SCRAPES for this process"
    )
    is_cycle_active: bool = Field(
        description="True while an update cycle (or manual refresh) is running"
    )
    youtube_cooldown_remaining_seconds: float = Field(
        ge=0, description="Seconds left on YouTube block cooldown, or 0"
    )
    update_interval_seconds: int = Field(
        ge=0, description="Seconds between update cycles (DATA_UPDATE_INTERVAL)"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="When this status snapshot was last mutated"
    )
