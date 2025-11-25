from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Song(BaseModel):
    """Pydantic model for Song, matching the SQLAlchemy Songs model."""

    id: Optional[int] = None
    title: str = Field(..., max_length=500)
    video_id: str = Field(..., max_length=255)
    timestamp: Optional[str] = Field(default=None, max_length=50)
    analyzed_by_llm: Optional[bool] = Field(default=False)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
    }
