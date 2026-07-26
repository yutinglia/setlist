from datetime import datetime

from pydantic import BaseModel, Field


class Song(BaseModel):
    """Pydantic model for Song, matching the SQLAlchemy Songs model."""

    id: int | None = None
    title: str = Field(..., max_length=500)
    video_id: str = Field(..., max_length=255)
    timestamp: str | None = Field(default=None, max_length=50)
    analyzed_by_llm: bool = Field(default=False)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {
        "from_attributes": True,
    }
