from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class YouTubeVideo(BaseModel):
    """Pydantic model for YouTube Video, matching the SQLAlchemy Videos model."""

    id: str = Field(..., max_length=255)
    title: str = Field(..., max_length=500)
    url: str = Field(..., max_length=500)
    channel_id: str = Field(..., max_length=255)
    upload_date: Optional[str] = Field(default=None, max_length=50)
    type: Optional[str] = Field(default=None, max_length=50)
    raw_data: Optional[dict[str, Any]] = None
    comments_raw_data: Optional[dict[str, Any]] = None
    analyze_attempts: Optional[int] = Field(default=0)
    last_analyzed_at: Optional[datetime] = None
    has_song_list_comment: Optional[bool] = Field(default=False)
    song_list_comment_raw_data: Optional[dict[str, Any]] = None
    cleaning_attempts: Optional[int] = Field(default=0)
    last_cleaned_at: Optional[datetime] = None
    cleaned_song_list_comment: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
    }
