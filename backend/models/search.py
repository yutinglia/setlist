from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from models.song import Song
from utils.youtube_upload_date import UploadDatePrecision

T = TypeVar("T")


class Paginated(BaseModel, Generic[T]):
    """Offset/limit page wrapper used by list and search endpoints."""

    items: list[T]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)


class ChannelRead(BaseModel):
    """Public channel fields; intentionally excludes the raw yt-dlp payload."""

    id: str
    name: str
    url: str
    thumbnail_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class VideoRead(BaseModel):
    """Public video fields; excludes comments and other scraper payloads."""

    id: str
    title: str
    url: str
    channel_id: str
    upload_date: str | None = None
    upload_date_precision: UploadDatePrecision | None = None
    type: str | None = None
    has_song_list_comment: bool = False
    setlist_comment_author: str | None = None
    setlist_comment_author_id: str | None = None
    setlist_comment_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SongSearchResult(BaseModel):
    """Song hit with video deep link and channel context for search/detail APIs."""

    id: int
    title: str
    timestamp: str | None = None
    video_id: str
    video_url: str
    video_title: str | None = None
    channel_id: str
    channel_name: str
    analyzed_by_llm: bool = False
    setlist_comment_author: str | None = None
    setlist_comment_author_id: str | None = None
    setlist_comment_id: str | None = None

    @classmethod
    def from_parts(
        cls,
        *,
        song: Song,
        video_title: str | None,
        channel_id: str,
        channel_name: str,
        deep_link_url: str,
        setlist_comment_author: str | None = None,
        setlist_comment_author_id: str | None = None,
        setlist_comment_id: str | None = None,
    ) -> "SongSearchResult":
        if song.id is None:
            raise ValueError("Song id is required for search results")
        return cls(
            id=song.id,
            title=song.title,
            timestamp=song.timestamp,
            video_id=song.video_id,
            video_url=deep_link_url,
            video_title=video_title,
            channel_id=channel_id,
            channel_name=channel_name,
            analyzed_by_llm=song.analyzed_by_llm,
            setlist_comment_author=setlist_comment_author,
            setlist_comment_author_id=setlist_comment_author_id,
            setlist_comment_id=setlist_comment_id,
        )


class SongSuggestion(BaseModel):
    """A distinct song title suggested from the indexed setlists."""

    title: str
    occurrences: int = Field(..., ge=1)


class SetlistContributor(BaseModel):
    """A public YouTube commenter credited for one or more indexed setlists."""

    author: str
    author_id: str
    song_count: int = Field(..., ge=1)
    video_count: int = Field(..., ge=1)
