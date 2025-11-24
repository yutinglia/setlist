from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


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
