from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from utils.youtube_upload_date import (
    UPLOAD_DATE_EXACT,
    UploadDatePrecision,
)

AnalysisStatus = Literal[
    "pending",
    "retry",
    "no_setlist",
    "done",
    "exhausted",
    "skipped",
]

ANALYSIS_PENDING: AnalysisStatus = "pending"
ANALYSIS_RETRY: AnalysisStatus = "retry"
ANALYSIS_NO_SETLIST: AnalysisStatus = "no_setlist"
ANALYSIS_DONE: AnalysisStatus = "done"
ANALYSIS_EXHAUSTED: AnalysisStatus = "exhausted"
ANALYSIS_SKIPPED: AnalysisStatus = "skipped"


class YouTubeVideo(BaseModel):
    """Pydantic model for YouTube Video, matching the SQLAlchemy Videos model."""

    id: str = Field(..., max_length=255)
    title: str = Field(..., max_length=500)
    url: str = Field(..., max_length=500)
    channel_id: str = Field(..., max_length=255)
    upload_date: str | None = Field(default=None, max_length=50)
    upload_date_precision: UploadDatePrecision | None = None
    playlist_position: int | None = Field(default=None, ge=1)
    type: str | None = Field(default=None, max_length=50)
    raw_data: dict[str, Any] | None = None
    metadata_raw_data: dict[str, Any] | None = None
    list_scraped_at: datetime | None = None
    metadata_scraped_at: datetime | None = None
    comments_raw_data: dict[str, Any] | None = None
    analyze_attempts: int = Field(default=0, ge=0)
    last_analyzed_at: datetime | None = None
    has_song_list_comment: bool = Field(default=False)
    song_list_comment_raw_data: dict[str, Any] | None = None
    setlist_comment_author: str | None = Field(default=None, max_length=255)
    setlist_comment_author_id: str | None = Field(default=None, max_length=255)
    setlist_comment_id: str | None = Field(default=None, max_length=255)
    cleaning_attempts: int = Field(default=0, ge=0)
    last_cleaned_at: datetime | None = None
    cleaned_song_list_comment: dict[str, Any] | None = None
    analysis_status: AnalysisStatus = ANALYSIS_PENDING
    next_analysis_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {
        "from_attributes": True,
    }

    @model_validator(mode="after")
    def normalize_upload_date_precision(self) -> "YouTubeVideo":
        """Keep the date/precision pair valid at every repository boundary."""
        if self.upload_date is None:
            self.upload_date_precision = None
        elif self.upload_date_precision is None:
            # Manually supplied and full-metadata dates are authoritative by
            # default. Flat-list callers explicitly mark approximate values.
            self.upload_date_precision = UPLOAD_DATE_EXACT
        return self
