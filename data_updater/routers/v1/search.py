from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session, pagination_params
from models.channel import YouTubeChannel
from models.search import Paginated, SongSearchResult
from models.song import Song
from models.video import YouTubeVideo
from repositories import ChannelRepository, SongRepository, VideoRepository
from services.data_updater import DataUpdater

router = APIRouter(tags=["Songs"])


class ChannelVideoRefreshResponse(BaseModel):
    channel_id: str
    mode: str = Field(
        description="'scrape' when YouTube list was fetched, else 'reclassify'"
    )
    scraped: int = Field(ge=0)
    reclassified: int = Field(ge=0, description="Rows whose type changed")
    message: str


@router.get("/songs/search", response_model=Paginated[SongSearchResult])
async def search_songs(
    q: str = Query(..., min_length=1, description="Substring match on song title"),
    pagination: tuple[int, int] = Depends(pagination_params),
    session: AsyncSession = Depends(get_session),
):
    """Search songs by title (ILIKE). Returns deep-linked YouTube URLs."""
    limit, offset = pagination
    repo = SongRepository(session)
    items, total = await repo.search_by_title(q, limit=limit, offset=offset)
    return Paginated(items=items, total=total, limit=limit, offset=offset)


@router.get("/songs/{song_id}", response_model=SongSearchResult)
async def get_song(
    song_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Song detail with video URL (including ``&t=``) and channel info."""
    detail = await SongRepository(session).get_detail(song_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Song not found")
    return detail


@router.get("/channels", response_model=Paginated[YouTubeChannel])
async def list_channels(
    pagination: tuple[int, int] = Depends(pagination_params),
    session: AsyncSession = Depends(get_session),
):
    """List tracked channels."""
    limit, offset = pagination
    repo = ChannelRepository(session)
    items = await repo.get_all(limit=limit, offset=offset)
    total = await repo.count_all()
    return Paginated(items=items, total=total, limit=limit, offset=offset)


@router.get("/channels/{channel_id}/videos", response_model=Paginated[YouTubeVideo])
async def list_channel_videos(
    channel_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    session: AsyncSession = Depends(get_session),
):
    """List videos for a tracked channel."""
    channel_repo = ChannelRepository(session)
    if await channel_repo.get_by_id(channel_id) is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    limit, offset = pagination
    video_repo = VideoRepository(session)
    items = await video_repo.get_by_channel_id(
        channel_id, limit=limit, offset=offset
    )
    total = await video_repo.count_by_channel_id(channel_id)
    return Paginated(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/channels/{channel_id}/videos/refresh",
    response_model=ChannelVideoRefreshResponse,
)
async def refresh_channel_videos(
    channel_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Scrape this channel's video list and reclassify karaoke/song types.

    Does not scrape comments or extract setlists.
    """
    channel_repo = ChannelRepository(session)
    channel = await channel_repo.get_by_id(channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    updater = DataUpdater(
        session,
        channel_repo,
        VideoRepository(session),
        SongRepository(session),
    )
    try:
        result = await updater.refresh_channel_video_list(channel)
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return ChannelVideoRefreshResponse(
        channel_id=result.channel_id,
        mode=result.mode,
        scraped=result.scraped,
        reclassified=result.reclassified,
        message=result.message,
    )


@router.get("/videos/{video_id}/songs", response_model=Paginated[Song])
async def list_video_songs(
    video_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    session: AsyncSession = Depends(get_session),
):
    """List songs extracted for a video."""
    video_repo = VideoRepository(session)
    if await video_repo.get_by_id(video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found")
    limit, offset = pagination
    song_repo = SongRepository(session)
    items = await song_repo.get_by_video_id(video_id, limit=limit, offset=offset)
    total = await song_repo.count_by_video_id(video_id)
    return Paginated(items=items, total=total, limit=limit, offset=offset)
