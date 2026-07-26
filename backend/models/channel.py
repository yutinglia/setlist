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

MAX_CHANNELS_PER_BULK_ADD = 10
ChannelBulkAddStatus = Literal[
    "created",
    "already_exists",
    "invalid",
    "failed",
    "skipped",
]


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


class ChannelBulkCreate(BaseModel):
    """Administrator bulk-add request with per-item validation outcomes."""

    urls: list[str] = Field(
        ...,
        min_length=1,
        max_length=MAX_CHANNELS_PER_BULK_ADD,
        description="One to ten YouTube channel URLs",
    )


class ChannelBulkAddItemResult(BaseModel):
    url: str
    status: ChannelBulkAddStatus
    channel_id: str | None = None
    channel_name: str | None = None
    message: str


class ChannelBulkAddResponse(BaseModel):
    items: list[ChannelBulkAddItemResult]
    created: int = Field(ge=0)
    already_exists: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    max_batch_size: int = MAX_CHANNELS_PER_BULK_ADD
    cooldown_seconds: int = Field(ge=0)


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
