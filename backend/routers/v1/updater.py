"""Live status of the background scraper / analyzer."""

from fastapi import APIRouter, Depends, Response

from container import ApplicationContainer
from deps import get_container, require_admin_session
from models.updater import UpdaterStatusResponse
from services.updater_status import UpdaterPhase
from utils.http_cache import prevent_private_response_caching

router = APIRouter(prefix="/updater", tags=["Updater"])
PUBLIC_ERROR_MESSAGE = "An updater operation failed; check server logs"


@router.get(
    "/status",
    response_model=UpdaterStatusResponse,
    dependencies=[Depends(require_admin_session)],
)
async def get_updater_status(
    response: Response,
    container: ApplicationContainer = Depends(get_container),
) -> UpdaterStatusResponse:
    """Return process-local detail plus durable updater liveness state."""
    prevent_private_response_caching(response)
    settings = container.settings
    snap = container.updater_status.snapshot()
    runtime = await container.runtime_state_store.read()
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
        is_stalled=settings.background_updater_enabled
        and runtime.is_stalled(
            stale_after_seconds=settings.updater_heartbeat_stale_seconds
        ),
        heartbeat_stale_seconds=settings.updater_heartbeat_stale_seconds,
        comment_scrape_cap=settings.scrape_policy.comment_scrapes_per_cycle,
        background_updater_enabled=settings.background_updater_enabled,
        youtube_cooldown_remaining_seconds=(container.youtube_cooldown.remaining()),
        update_interval_seconds=settings.data_update_interval,
        steady_scan_interval_seconds=(
            settings.scrape_policy.steady_scan_interval_seconds
        ),
        backfill_page_size=settings.scrape_policy.backfill_page_size,
        backfill_pages_per_cycle=settings.scrape_policy.backfill_pages_per_cycle,
    )
