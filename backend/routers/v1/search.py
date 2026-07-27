import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from config import BACKGROUND_UPDATER_ENABLED, CHANNEL_ADD_COOLDOWN_SECONDS
from deps import get_session, pagination_params, require_management_admin
from models.channel import (
    MAX_CHANNELS_PER_BULK_ADD,
    ChannelBulkAddItemResult,
    ChannelBulkAddResponse,
    ChannelBulkCreate,
    ChannelCreate,
)
from models.search import (
    ChannelRead,
    Paginated,
    SongSearchResult,
    SongSuggestion,
    VideoRead,
)
from models.song import Song
from repositories import ChannelRepository, SongRepository, VideoRepository
from services.channel_creator import (
    ChannelAddCooldownActive,
    ChannelCreator,
    ChannelResolutionFailed,
    YouTubeCooldownActive,
)
from services.data_updater import DataUpdater
from services.update_cycle_trigger import update_cycle_trigger
from services.youtube_operation_lock import YouTubeUpdaterBusyError
from services.yt_scraper.errors import YouTubeAccessBlocked

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


class VideoSongReloadResponse(BaseModel):
    video_id: str
    song_count: int = Field(ge=0)
    has_song_list_comment: bool
    analysis_status: str
    message: str


_UPLOAD_DATE_PATTERN = r"^\d{8}$"


@router.get("/songs/search", response_model=Paginated[SongSearchResult])
async def search_songs(
    q: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="Literal substring match on song title",
    ),
    channel_id: list[str] | None = Query(
        None,
        max_length=25,
        description="Repeat to limit results to any of these channel ids",
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
        channel_ids=channel_id,
        video_type=type,
        upload_date_from=upload_date_from,
        upload_date_to=upload_date_to,
    )
    return Paginated(items=items, total=total, limit=limit, offset=offset)


@router.get("/songs/suggestions", response_model=list[SongSuggestion])
async def suggest_songs(
    q: str = Query(
        ...,
        min_length=2,
        max_length=200,
        description="Literal substring match used for title suggestions",
    ),
    channel_id: list[str] | None = Query(
        None,
        max_length=25,
        description="Repeat to limit suggestions to any of these channel ids",
    ),
    type: Literal["karaoke", "song"] | None = Query(
        None,
        description="Filter suggestions by video type",
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
    limit: int = Query(8, ge=1, le=10),
    session: AsyncSession = Depends(get_session),
):
    """Suggest distinct indexed song titles without running a full search."""
    if (
        upload_date_from is not None
        and upload_date_to is not None
        and upload_date_from > upload_date_to
    ):
        raise HTTPException(
            status_code=422,
            detail="upload_date_from must be less than or equal to upload_date_to",
        )
    return await SongRepository(session).suggest_titles(
        q,
        limit=limit,
        channel_ids=channel_id,
        video_type=type,
        upload_date_from=upload_date_from,
        upload_date_to=upload_date_to,
    )


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


@router.get("/channels/{channel_id}", response_model=ChannelRead)
async def get_channel(
    channel_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Return one tracked channel without exposing its raw scraper payload."""
    channel = await ChannelRepository(session).get_by_id(channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.post(
    "/channels",
    response_model=ChannelRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    body: ChannelCreate,
    _=Depends(require_management_admin),
    session: AsyncSession = Depends(get_session),
):
    """Scrape a YouTube channel URL and add it to the tracked list.

    Sets ``video_backfill_status=pending`` and wakes the background updater so
    it starts walking the full catalog in bounded, durable pages immediately.
    Returns 409 if the channel id is already tracked.
    """

    repo = ChannelRepository(session)
    creator = ChannelCreator(session, repo)
    try:
        outcome = await creator.create(body.url)
    except YouTubeUpdaterBusyError as busy_exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Another updater operation is running; try again shortly",
        ) from busy_exc
    except ChannelAddCooldownActive as cooldown_exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Channel add cooldown active; "
                f"try again in {cooldown_exc.remaining_seconds:.0f} seconds"
            ),
            headers={
                "Retry-After": creator.retry_after_header(
                    cooldown_exc.remaining_seconds
                )
            },
        ) from cooldown_exc
    except YouTubeCooldownActive as cooldown_exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "YouTube cooldown active; "
                f"try again in {cooldown_exc.remaining_seconds:.0f} seconds"
            ),
            headers={
                "Retry-After": creator.retry_after_header(
                    cooldown_exc.remaining_seconds
                )
            },
        ) from cooldown_exc
    except YouTubeAccessBlocked as block_exc:
        logger.warning(
            "YouTube blocked while adding channel %s: %s", body.url, block_exc
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YouTube temporarily blocked this request; try again later",
        ) from block_exc
    except ChannelResolutionFailed as scrape_exc:
        logger.warning("Failed to resolve channel %s: %s", body.url, scrape_exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve a YouTube channel from that URL",
        ) from scrape_exc

    if outcome.status == "already_exists":
        existing = outcome.channel
        existing_label = (
            f"{existing.name} ({existing.id})" if existing is not None else body.url
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Channel already tracked: {existing_label}",
        )
    created = outcome.channel
    if created is None:
        raise RuntimeError("Created channel outcome did not include a channel")

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


@router.post(
    "/channels/bulk",
    response_model=ChannelBulkAddResponse,
)
async def create_channels_bulk(
    body: ChannelBulkCreate,
    _=Depends(require_management_admin),
    session: AsyncSession = Depends(get_session),
):
    """Add up to ten channels with durable pacing and one updater wake-up."""
    item_results: list[ChannelBulkAddItemResult | None] = [None] * len(body.urls)
    valid_urls: list[str] = []
    valid_positions: list[int] = []
    for index, raw_url in enumerate(body.urls):
        try:
            valid = ChannelCreate(url=raw_url)
        except ValidationError:
            item_results[index] = ChannelBulkAddItemResult(
                url=raw_url,
                status="invalid",
                message="Enter a valid YouTube channel URL",
            )
            continue
        valid_urls.append(valid.url)
        valid_positions.append(index)

    creator = ChannelCreator(session, ChannelRepository(session))
    try:
        outcomes = await creator.create_bulk(valid_urls) if valid_urls else []
    except YouTubeUpdaterBusyError as busy_exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Another updater operation is running; try again shortly",
        ) from busy_exc
    except YouTubeCooldownActive as cooldown_exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "YouTube cooldown active; "
                f"try again in {cooldown_exc.remaining_seconds:.0f} seconds"
            ),
            headers={
                "Retry-After": creator.retry_after_header(
                    cooldown_exc.remaining_seconds
                )
            },
        ) from cooldown_exc

    created_channel_ids: list[str] = []
    for position, outcome in zip(valid_positions, outcomes, strict=True):
        channel = outcome.channel
        item_results[position] = ChannelBulkAddItemResult(
            url=outcome.requested_url,
            status=outcome.status,
            channel_id=channel.id if channel is not None else None,
            channel_name=channel.name if channel is not None else None,
            message=outcome.message,
        )
        if outcome.status == "created" and channel is not None:
            created_channel_ids.append(channel.id)

    completed_items = [item for item in item_results if item is not None]
    if len(completed_items) != len(body.urls):
        raise RuntimeError("Bulk channel creation returned an incomplete result")

    if created_channel_ids and BACKGROUND_UPDATER_ENABLED:
        # One coalesced wake is intentional. Pending rows remain durable and the
        # normal per-cycle backfill cap rotates through them every worker tick.
        update_cycle_trigger.request()
        logger.info(
            "Bulk channel add committed %s channel(s); queued one updater wake",
            len(created_channel_ids),
        )
    elif created_channel_ids:
        logger.warning(
            "Bulk channel add left %s pending backfill(s), but updater is disabled",
            len(created_channel_ids),
        )

    counts = {
        result_status: sum(item.status == result_status for item in completed_items)
        for result_status in (
            "created",
            "already_exists",
            "invalid",
            "failed",
            "skipped",
        )
    }
    return ChannelBulkAddResponse(
        items=completed_items,
        created=counts["created"],
        already_exists=counts["already_exists"],
        failed=counts["invalid"] + counts["failed"],
        skipped=counts["skipped"],
        max_batch_size=MAX_CHANNELS_PER_BULK_ADD,
        cooldown_seconds=CHANNEL_ADD_COOLDOWN_SECONDS,
    )


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
    _=Depends(require_management_admin),
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
    except YouTubeUpdaterBusyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Another updater operation is running; try again shortly",
        ) from exc
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


@router.post(
    "/videos/{video_id}/songs/reload",
    response_model=VideoSongReloadResponse,
)
async def reload_video_song_list(
    video_id: str,
    _=Depends(require_management_admin),
    session: AsyncSession = Depends(get_session),
):
    """Re-fetch top comments and replace a video's songs on successful analysis."""
    channel_repo = ChannelRepository(session)
    video_repo = VideoRepository(session)
    song_repo = SongRepository(session)
    video = await video_repo.get_by_id(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    updater = DataUpdater(session, channel_repo, video_repo, song_repo)
    try:
        result = await updater.reload_video_song_list(video)
    except YouTubeUpdaterBusyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Another updater operation is running; try again shortly",
        ) from exc
    except YouTubeAccessBlocked as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YouTube temporarily blocked this request; try again later",
        ) from exc
    except Exception as exc:
        logger.exception("Failed reloading song list for video %s", video_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reload this song list from YouTube",
        ) from exc

    return VideoSongReloadResponse(
        video_id=result.video_id,
        song_count=result.song_count,
        has_song_list_comment=result.has_song_list_comment,
        analysis_status=result.analysis_status,
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
