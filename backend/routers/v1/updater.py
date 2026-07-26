"""Live status of the background scraper / analyzer."""

from fastapi import APIRouter, Depends, Response

from config import (
    BACKGROUND_UPDATER_ENABLED,
    DATA_UPDATE_INTERVAL,
    SCRAPE_POLICY,
    UPDATE_MAX_COMMENT_SCRAPES,
)
from deps import require_admin_session
from models.updater import UpdaterStatusResponse
from services.data_updater import DataUpdater
from services.updater_status import UpdaterPhase, updater_status
from utils.http_cache import prevent_private_response_caching

router = APIRouter(prefix="/updater", tags=["Updater"])
PUBLIC_ERROR_MESSAGE = "An updater operation failed; check server logs"


@router.get(
    "/status",
    response_model=UpdaterStatusResponse,
    dependencies=[Depends(require_admin_session)],
)
async def get_updater_status(response: Response) -> UpdaterStatusResponse:
    """Return what the scraper/analyzer is doing (process-local, in-memory)."""
    prevent_private_response_caching(response)
    snap = updater_status.snapshot()
    if snap["last_error"] is not None:
        snap["last_error"] = PUBLIC_ERROR_MESSAGE
        if snap["phase"] == UpdaterPhase.ERROR.value:
            snap["detail"] = PUBLIC_ERROR_MESSAGE
    return UpdaterStatusResponse(
        **snap,
        comment_scrape_cap=UPDATE_MAX_COMMENT_SCRAPES,
        background_updater_enabled=BACKGROUND_UPDATER_ENABLED,
        youtube_cooldown_remaining_seconds=DataUpdater.youtube_cooldown_remaining(),
        update_interval_seconds=DATA_UPDATE_INTERVAL,
        steady_scan_interval_seconds=SCRAPE_POLICY.steady_scan_interval_seconds,
        backfill_page_size=SCRAPE_POLICY.backfill_page_size,
        backfill_pages_per_cycle=SCRAPE_POLICY.backfill_pages_per_cycle,
    )
