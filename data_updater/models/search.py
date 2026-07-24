from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

from models.song import Song

T = TypeVar("T")


class Paginated(BaseModel, Generic[T]):
    """Offset/limit page wrapper used by list and search endpoints."""

    items: list[T]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)


class SongSearchResult(BaseModel):
    """Song hit with video deep link and channel context for search/detail APIs."""

    id: int
    title: str
    timestamp: Optional[str] = None
    video_id: str
    video_url: str
    video_title: Optional[str] = None
    channel_id: str
    channel_name: str
    analyzed_by_llm: Optional[bool] = False

    @classmethod
    def from_parts(
        cls,
        *,
        song: Song,
        video_url: str,
        video_title: str | None,
        channel_id: str,
        channel_name: str,
        deep_link_url: str,
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
        )
