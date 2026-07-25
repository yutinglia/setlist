"""Live status of the background scraper / analyzer."""

from fastapi import APIRouter

from config import (
    BACKGROUND_UPDATER_ENABLED,
    DATA_UPDATE_INTERVAL,
    UPDATE_MAX_COMMENT_SCRAPES,
)
from models.updater import UpdaterStatusResponse
from services.data_updater import DataUpdater
from services.updater_status import UpdaterPhase, updater_status

router = APIRouter(prefix="/updater", tags=["Updater"])
PUBLIC_ERROR_MESSAGE = "An updater operation failed; check server logs"


@router.get("/status", response_model=UpdaterStatusResponse)
async def get_updater_status() -> UpdaterStatusResponse:
    """Return what the scraper/analyzer is doing (process-local, in-memory)."""
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
    )
