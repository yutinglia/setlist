import asyncio
import logging

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session, pagination_params
from models.channel import ChannelCreate, YouTubeChannel
from models.search import Paginated, SongSearchResult
from models.song import Song
from models.video import YouTubeVideo
from repositories import ChannelRepository, SongRepository, VideoRepository
from services.data_updater import DataUpdater
from services.yt_scraper.channel_scraper import YouTubeChannelScraper
from services.yt_scraper.errors import YouTubeAccessBlocked, raise_if_block_error

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Songs"])


class ChannelVideoRefreshResponse(BaseModel):
    channel_id: str
    mode: str = Field(
        description="'force' when videos were deleted+rescraped, else 'reclassify'"
    )
    scraped: int = Field(ge=0)
    deleted: int = Field(
        ge=0, description="Videos deleted before re-insert on force reload"
    )
    reclassified: int = Field(ge=0, description="Rows whose type changed")
    cleared: int = Field(
        ge=0,
        description="Non-karaoke videos whose comments/setlists were cleared",
    )
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


@router.post(
    "/channels",
    response_model=YouTubeChannel,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    body: ChannelCreate,
    session: AsyncSession = Depends(get_session),
):
    """Scrape a YouTube channel URL and add it to the tracked list.

    Does not scrape videos; the background updater (or video refresh) will
    pick them up. Returns 409 if the channel id is already tracked.
    """

    def _scrape() -> YouTubeChannel:
        return YouTubeChannelScraper().get_channel_info(body.url)

    try:
        scraped = await asyncio.to_thread(_scrape)
    except Exception as scrape_exc:
        try:
            raise_if_block_error(scrape_exc)
        except YouTubeAccessBlocked as block_exc:
            logger.warning(
                "YouTube blocked while adding channel %s: %s", body.url, block_exc
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="YouTube temporarily blocked this request; try again later",
            ) from block_exc
        if isinstance(scrape_exc, YouTubeAccessBlocked):
            logger.warning(
                "YouTube blocked while adding channel %s: %s", body.url, scrape_exc
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="YouTube temporarily blocked this request; try again later",
            ) from scrape_exc
        logger.exception("Failed to scrape channel %s", body.url)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not resolve channel from URL: {scrape_exc}",
        ) from scrape_exc

    if not scraped.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve a channel id from that URL",
        )

    repo = ChannelRepository(session)
    existing = await repo.get_by_id(scraped.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Channel already tracked: {existing.name} ({existing.id})",
        )

    try:
        created = await repo.upsert(scraped)
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return created


@router.get("/channels/{channel_id}/videos", response_model=Paginated[YouTubeVideo])
async def list_channel_videos(
    channel_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    type: Literal["karaoke", "song"] | None = Query(
        None,
        description="Filter by video type (karaoke stream or song upload)",
    ),
    session: AsyncSession = Depends(get_session),
):
    """List videos for a tracked channel (optional karaoke/song filter)."""
    channel_repo = ChannelRepository(session)
    if await channel_repo.get_by_id(channel_id) is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    limit, offset = pagination
    video_repo = VideoRepository(session)
    items = await video_repo.get_by_channel_id(
        channel_id, limit=limit, offset=offset, video_type=type
    )
    total = await video_repo.count_by_channel_id(channel_id, video_type=type)
    return Paginated(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/channels/{channel_id}/videos/refresh",
    response_model=ChannelVideoRefreshResponse,
)
async def refresh_channel_videos(
    channel_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Force-reload this channel's videos: full-metadata scrape, then replace DB rows.

    Deletes existing videos/songs for the channel after a successful scrape and
    re-inserts. Does not scrape comments or extract setlists.
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
        deleted=result.deleted,
        reclassified=result.reclassified,
        cleared=result.cleared,
        message=result.message,
    )


@router.get("/videos/{video_id}", response_model=YouTubeVideo)
async def get_video(
    video_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Video metadata (title, type, YouTube URL)."""
    video = await VideoRepository(session).get_by_id(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


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
