"""Live status of the background scraper / analyzer."""

from fastapi import APIRouter, Depends, Response

from config import (
    BACKGROUND_UPDATER_ENABLED,
    DATA_UPDATE_INTERVAL,
    SCRAPE_POLICY,
    UPDATE_MAX_COMMENT_SCRAPES,
    UPDATER_HEARTBEAT_STALE_SECONDS,
)
from db import engine
from deps import require_admin_session
from models.updater import UpdaterStatusResponse
from services.data_updater import DataUpdater
from services.updater_runtime_state import UpdaterRuntimeStateStore
from services.updater_status import UpdaterPhase, updater_status
from utils.http_cache import prevent_private_response_caching

router = APIRouter(prefix="/updater", tags=["Updater"])
PUBLIC_ERROR_MESSAGE = "An updater operation failed; check server logs"
updater_runtime_state_store = UpdaterRuntimeStateStore(engine)


@router.get(
    "/status",
    response_model=UpdaterStatusResponse,
    dependencies=[Depends(require_admin_session)],
)
async def get_updater_status(response: Response) -> UpdaterStatusResponse:
    """Return process-local detail plus durable updater liveness state."""
    prevent_private_response_caching(response)
    snap = updater_status.snapshot()
    runtime = await updater_runtime_state_store.read()
    if snap["last_error"] is not None:
        snap["last_error"] = PUBLIC_ERROR_MESSAGE
        if snap["phase"] == UpdaterPhase.ERROR.value:
            snap["detail"] = PUBLIC_ERROR_MESSAGE
    return UpdaterStatusResponse(
        **snap,
        persistent_cycle_started_at=runtime.cycle_started_at,
        persistent_cycle_finished_at=runtime.cycle_finished_at,
        persistent_last_success_at=runtime.last_success_at,
        persistent_heartbeat_at=runtime.heartbeat_at,
        persistent_outcome=runtime.outcome,
        persistent_owner_id=runtime.owner_id,
        is_stalled=runtime.is_stalled(
            stale_after_seconds=UPDATER_HEARTBEAT_STALE_SECONDS
        ),
        heartbeat_stale_seconds=UPDATER_HEARTBEAT_STALE_SECONDS,
        comment_scrape_cap=UPDATE_MAX_COMMENT_SCRAPES,
        background_updater_enabled=BACKGROUND_UPDATER_ENABLED,
        youtube_cooldown_remaining_seconds=DataUpdater.youtube_cooldown_remaining(),
        update_interval_seconds=DATA_UPDATE_INTERVAL,
        steady_scan_interval_seconds=SCRAPE_POLICY.steady_scan_interval_seconds,
        backfill_page_size=SCRAPE_POLICY.backfill_page_size,
        backfill_pages_per_cycle=SCRAPE_POLICY.backfill_pages_per_cycle,
    )
