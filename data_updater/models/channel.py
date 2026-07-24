from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


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
    def strip_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("url must not be empty")
        return cleaned


class YouTubeChannel(BaseModel):
    """Pydantic model for YouTube Channel, matching the SQLAlchemy Channels model."""

    id: str = Field(..., max_length=255)
    name: str = Field(..., max_length=500)
    url: str = Field(..., max_length=500)
    thumbnail_url: Optional[str] = Field(default=None, max_length=500)
    raw_data: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
    }
