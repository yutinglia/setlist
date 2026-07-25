"""Read-only aggregate report DTOs."""

from datetime import datetime

from pydantic import BaseModel, Field


class BackfillReport(BaseModel):
    pending: int = Field(ge=0)
    running: int = Field(ge=0)
    done: int = Field(ge=0)
    failed: int = Field(ge=0)


class VideoReport(BaseModel):
    total: int = Field(ge=0)
    karaoke: int = Field(ge=0)
    song: int = Field(ge=0)
    other: int = Field(ge=0)
    with_list_snapshot: int = Field(ge=0)
    with_metadata_snapshot: int = Field(ge=0)
    date_unknown: int = Field(ge=0)
    date_approximate: int = Field(ge=0)
    date_exact: int = Field(ge=0)
    latest_discovered_at: datetime | None = None


class AnalysisStatusReport(BaseModel):
    pending: int = Field(ge=0)
    retry: int = Field(ge=0)
    no_setlist: int = Field(ge=0)
    done: int = Field(ge=0)
    exhausted: int = Field(ge=0)
    skipped: int = Field(ge=0)


class AnalysisReport(BaseModel):
    attempted: int = Field(
        ge=0,
        description="Videos with a recorded comment-analysis attempt",
    )
    with_setlist: int = Field(ge=0)
    videos_with_comments: int = Field(
        ge=0,
        description="Videos with a persisted comment snapshot, including empty lists",
    )
    comments: int = Field(
        ge=0,
        description="Total comment objects in persisted comment snapshots",
    )
    latest_analyzed_at: datetime | None = None
    status: AnalysisStatusReport


class SongReport(BaseModel):
    total: int = Field(ge=0)
    analyzed_by_llm: int = Field(ge=0)


class SummaryReport(BaseModel):
    """Database-backed pipeline inventory at one point in time."""

    generated_at: datetime
    channels: int = Field(ge=0)
    backfill: BackfillReport
    videos: VideoReport
    analysis: AnalysisReport
    songs: SongReport
