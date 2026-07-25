from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from utils.youtube_channel_url import normalize_youtube_channel_url


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
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {
        "from_attributes": True,
    }
