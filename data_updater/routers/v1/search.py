import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config import BACKGROUND_UPDATER_ENABLED, MANAGEMENT_API_ENABLED, SCRAPE_POLICY
from deps import get_session, pagination_params
from models.channel import VIDEO_BACKFILL_PENDING, ChannelCreate, YouTubeChannel
from models.search import ChannelRead, Paginated, SongSearchResult, VideoRead
from models.song import Song
from repositories import ChannelRepository, SongRepository, VideoRepository
from services.data_updater import DataUpdater, youtube_operation_lock
from services.update_cycle_trigger import update_cycle_trigger
from services.yt_scraper.channel_scraper import YouTubeChannelScraper
from services.yt_scraper.errors import YouTubeAccessBlocked, raise_if_block_error

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Songs"])


class ChannelVideoRefreshResponse(BaseModel):
    channel_id: str
    mode: str = Field(description="'refresh' for a non-destructive metadata upsert")
    scraped: int = Field(ge=0)
    deleted: int = Field(ge=0, description="Backward-compatible field; always zero")
    reclassified: int = Field(
        ge=0, description="Backward-compatible field; always zero"
    )
    cleared: int = Field(
        ge=0,
        description="Backward-compatible field; always zero",
    )
    message: str


def require_management_api() -> None:
    """Keep scraper/mutation controls off the public production API by default."""
    if not MANAGEMENT_API_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")


_UPLOAD_DATE_PATTERN = r"^\d{8}$"


@router.get("/songs/search", response_model=Paginated[SongSearchResult])
async def search_songs(
    q: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="Literal substring match on song title",
    ),
    channel_id: str | None = Query(
        None,
        description="Limit results to songs from this channel id",
    ),
    type: Literal["karaoke", "song"] | None = Query(
        None,
        description="Filter by video type (karaoke stream or song upload)",
    ),
    upload_date_from: str | None = Query(
        None,
        pattern=_UPLOAD_DATE_PATTERN,
        description="Inclusive lower bound on video upload_date (YYYYMMDD)",
    ),
    upload_date_to: str | None = Query(
        None,
        pattern=_UPLOAD_DATE_PATTERN,
        description="Inclusive upper bound on video upload_date (YYYYMMDD)",
    ),
    pagination: tuple[int, int] = Depends(pagination_params),
    session: AsyncSession = Depends(get_session),
):
    """Search songs by title (ILIKE). Optional channel / type / date filters.

    Returns deep-linked YouTube URLs.
    """
    if (
        upload_date_from is not None
        and upload_date_to is not None
        and upload_date_from > upload_date_to
    ):
        raise HTTPException(
            status_code=422,
            detail="upload_date_from must be less than or equal to upload_date_to",
        )
    limit, offset = pagination
    repo = SongRepository(session)
    items, total = await repo.search_by_title(
        q,
        limit=limit,
        offset=offset,
        channel_id=channel_id,
        video_type=type,
        upload_date_from=upload_date_from,
        upload_date_to=upload_date_to,
    )
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


@router.get("/channels", response_model=Paginated[ChannelRead])
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
    response_model=ChannelRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    body: ChannelCreate,
    _: None = Depends(require_management_api),
    session: AsyncSession = Depends(get_session),
):
    """Scrape a YouTube channel URL and add it to the tracked list.

    Sets ``video_backfill_status=pending`` and wakes the background updater so
    it starts walking the full catalog in bounded, durable pages immediately.
    Returns 409 if the channel id is already tracked.
    """

    def _scrape() -> YouTubeChannel:
        return YouTubeChannelScraper(
            sleep_interval=SCRAPE_POLICY.ytdlp_list_sleep_interval,
            max_sleep_interval=SCRAPE_POLICY.ytdlp_list_max_sleep_interval,
        ).get_channel_info(body.url)

    repo = ChannelRepository(session)
    persisted_cooldown = await repo.get_youtube_cooldown_until()
    if persisted_cooldown is not None:
        remaining = (
            persisted_cooldown - datetime.now(UTC).replace(tzinfo=None)
        ).total_seconds()
        if remaining > DataUpdater.youtube_cooldown_remaining():
            DataUpdater.set_youtube_cooldown(remaining)

    async def _persist_cooldown() -> None:
        seconds = SCRAPE_POLICY.youtube_cooldown_seconds
        DataUpdater.set_youtube_cooldown(seconds)
        await repo.set_youtube_cooldown_until(
            datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=seconds)
        )
        await session.commit()

    try:
        async with youtube_operation_lock:
            cooldown = DataUpdater.youtube_cooldown_remaining()
            if cooldown > 0:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        f"YouTube cooldown active; try again in {cooldown:.0f} seconds"
                    ),
                )
            scraped = await asyncio.to_thread(_scrape)
    except HTTPException:
        raise
    except Exception as scrape_exc:
        try:
            raise_if_block_error(scrape_exc)
        except YouTubeAccessBlocked as block_exc:
            await _persist_cooldown()
            logger.warning(
                "YouTube blocked while adding channel %s: %s", body.url, block_exc
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="YouTube temporarily blocked this request; try again later",
            ) from block_exc
        if isinstance(scrape_exc, YouTubeAccessBlocked):
            await _persist_cooldown()
            logger.warning(
                "YouTube blocked while adding channel %s: %s", body.url, scrape_exc
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="YouTube temporarily blocked this request; try again later",
            ) from scrape_exc
        logger.warning("Failed to resolve channel %s: %s", body.url, scrape_exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve a YouTube channel from that URL",
        ) from scrape_exc

    if not scraped.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve a channel id from that URL",
        )

    existing = await repo.get_by_id(scraped.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Channel already tracked: {existing.name} ({existing.id})",
        )

    to_create = scraped.model_copy(
        update={
            "video_backfill_status": VIDEO_BACKFILL_PENDING,
            "video_backfill_offset": 1,
            "video_backfill_updated_at": None,
        }
    )

    try:
        created = await repo.create(to_create)
        if created is None:
            await session.rollback()
            existing = await repo.get_by_id(scraped.id)
            existing_label = (
                f"{existing.name} ({existing.id})"
                if existing is not None
                else scraped.id
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Channel already tracked: {existing_label}",
            )
        await session.commit()
    except HTTPException:
        raise
    except Exception:
        await session.rollback()
        raise

    if BACKGROUND_UPDATER_ENABLED:
        queued = update_cycle_trigger.request(priority_channel_id=created.id)
        logger.info(
            "Channel %s committed with pending backfill; updater wake %s",
            created.id,
            "queued" if queued else "already pending",
        )
    else:
        logger.warning(
            "Channel %s has pending backfill, but background updater is disabled",
            created.id,
        )

    return created


@router.get("/channels/{channel_id}/videos", response_model=Paginated[VideoRead])
async def list_channel_videos(
    channel_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    type: Literal["karaoke", "song"] | None = Query(
        None,
        description="Filter by video type (karaoke stream or song upload)",
    ),
    has_song_list: bool | None = Query(
        None,
        description="Filter by whether a setlist comment was found",
    ),
    session: AsyncSession = Depends(get_session),
):
    """List videos for a tracked channel (optional type / setlist filters)."""
    channel_repo = ChannelRepository(session)
    if await channel_repo.get_by_id(channel_id) is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    limit, offset = pagination
    video_repo = VideoRepository(session)
    items = await video_repo.get_by_channel_id(
        channel_id,
        limit=limit,
        offset=offset,
        video_type=type,
        has_song_list=has_song_list,
    )
    total = await video_repo.count_by_channel_id(
        channel_id, video_type=type, has_song_list=has_song_list
    )
    return Paginated(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/channels/{channel_id}/videos/refresh",
    response_model=ChannelVideoRefreshResponse,
)
async def refresh_channel_videos(
    channel_id: str,
    _: None = Depends(require_management_api),
    session: AsyncSession = Depends(get_session),
):
    """Safely refresh recent video metadata without deleting existing setlists."""
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
    except YouTubeAccessBlocked as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YouTube temporarily blocked this request; try again later",
        ) from exc
    except Exception as exc:
        logger.exception("Failed refreshing channel %s", channel_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not refresh videos from YouTube",
        ) from exc

    return ChannelVideoRefreshResponse(
        channel_id=result.channel_id,
        mode=result.mode,
        scraped=result.scraped,
        deleted=result.deleted,
        reclassified=result.reclassified,
        cleared=result.cleared,
        message=result.message,
    )


@router.get("/videos/{video_id}", response_model=VideoRead)
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
