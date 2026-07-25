from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from utils.youtube_channel_url import normalize_youtube_channel_url

VideoBackfillStatus = Literal["pending", "running", "done", "failed"]

VIDEO_BACKFILL_PENDING: VideoBackfillStatus = "pending"
VIDEO_BACKFILL_RUNNING: VideoBackfillStatus = "running"
VIDEO_BACKFILL_DONE: VideoBackfillStatus = "done"
VIDEO_BACKFILL_FAILED: VideoBackfillStatus = "failed"

VIDEO_BACKFILL_ACTIVE: frozenset[str] = frozenset(
    {VIDEO_BACKFILL_PENDING, VIDEO_BACKFILL_RUNNING, VIDEO_BACKFILL_FAILED}
)


class ChannelCreate(BaseModel):
    """Request body for adding a channel by YouTube URL."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="YouTube channel URL (e.g. https://www.youtube.com/@handle)",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return normalize_youtube_channel_url(value)


class YouTubeChannel(BaseModel):
    """Pydantic model for YouTube Channel, matching the SQLAlchemy Channels model."""

    id: str = Field(..., max_length=255)
    name: str = Field(..., max_length=500)
    url: str = Field(..., max_length=500)
    thumbnail_url: str | None = Field(default=None, max_length=500)
    raw_data: dict[str, Any] | None = None
    video_backfill_status: VideoBackfillStatus = Field(
        default=VIDEO_BACKFILL_DONE,
        description=(
            "pending/running/failed = paced full-catalog ingest or retry; "
            "done = recent-only refresh"
        ),
    )
    video_backfill_offset: int = Field(
        default=1,
        ge=1,
        description="Next 1-based yt-dlp playliststart for backfill pages",
    )
    video_backfill_updated_at: datetime | None = None
    last_video_scan_at: datetime | None = None
    next_video_scan_at: datetime | None = None
    video_scan_failures: int = Field(default=0, ge=0)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {
        "from_attributes": True,
    }
