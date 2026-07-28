"""FastAPI application factory and background-worker composition."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from container import ApplicationContainer
from routers.v1 import router as v1_router
from services.cache import PUBLIC_CACHE_NAMESPACES
from services.rate_limit import GuestRateLimitMiddleware
from services.update_cycle_trigger import UpdateCycleRequest, UpdateCycleTrigger
from services.updater_runtime_state import (
    UPDATER_PROCESS_OWNER_ID,
    UpdaterRuntimeStateStore,
)
from services.updater_status import UpdaterPhase

logger = logging.getLogger(__name__)


async def wait_for_next_update_cycle(
    runtime_state_store: UpdaterRuntimeStateStore,
    trigger: UpdateCycleTrigger,
    *,
    timeout_seconds: float,
    heartbeat_interval_seconds: float,
    owner_id: str = UPDATER_PROCESS_OWNER_ID,
) -> UpdateCycleRequest | None:
    """Wait for queued work while keeping the idle worker heartbeat fresh."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return None
        request = await trigger.wait(min(remaining, heartbeat_interval_seconds))
        if request is not None:
            return request
        try:
            owned = await runtime_state_store.heartbeat(owner_id)
            if not owned:
                logger.warning(
                    "Idle updater heartbeat does not own the durable runtime state"
                )
        except Exception:
            logger.exception("Could not persist idle updater heartbeat")


async def run_periodic_data_updater(container: ApplicationContainer) -> None:
    """Run update cycles using collaborators owned by one app container."""
    settings = container.settings
    status_tracker = container.updater_status
    status_tracker.set(
        UpdaterPhase.WAITING,
        detail="Waiting for first update cycle",
        clear_channel=True,
        clear_video=True,
    )
    priority_channel_id: str | None = None
    while True:
        logger.info("Updating song list data...")
        try:
            async with container.session_factory() as session:
                await container.data_updater(session).update(
                    priority_channel_id=priority_channel_id,
                )
            logger.info("Song list data updated successfully.")
        except asyncio.CancelledError:
            logger.info("Data updater task cancelled. Terminating loop.")
            status_tracker.stop()
            break
        except Exception:
            logger.exception("Error updating song list data")
            status_tracker.end_cycle(error="The update cycle failed")
        logger.info("Waiting for the next update cycle...")
        remaining = container.youtube_cooldown.remaining()
        if remaining > 0:
            status_tracker.set(
                UpdaterPhase.COOLDOWN,
                detail=f"YouTube cooldown ({remaining:.0f}s remaining)",
                clear_channel=True,
                clear_video=True,
            )
        else:
            status_tracker.set(
                UpdaterPhase.WAITING,
                detail=(f"Waiting {settings.data_update_interval}s for next cycle"),
                clear_channel=True,
                clear_video=True,
            )
        request = await wait_for_next_update_cycle(
            container.runtime_state_store,
            container.update_cycle_trigger,
            timeout_seconds=settings.data_update_interval,
            heartbeat_interval_seconds=(settings.updater_heartbeat_interval_seconds),
        )
        priority_channel_id = (
            request.priority_channel_id if request is not None else None
        )
        if request is not None:
            logger.info(
                "Update cycle awakened by newly queued work%s",
                (
                    f" for channel {priority_channel_id}"
                    if priority_channel_id is not None
                    else ""
                ),
            )


def create_app(
    container: ApplicationContainer | None = None,
) -> FastAPI:
    """Create an isolated app; tests may inject a fully replaced container."""
    app_container = container or ApplicationContainer.build()
    settings = app_container.settings

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        updater_task: asyncio.Task[None] | None = None
        # Discard response entries that may predate this API process. If the
        # optional cache is unavailable, its dirty namespaces remain bypassed
        # and are cleared automatically after the adapter recovers.
        await app_container.cache.invalidate(*PUBLIC_CACHE_NAMESPACES)
        app_container.update_cycle_trigger.clear()
        if settings.background_updater_enabled:
            updater_task = asyncio.create_task(run_periodic_data_updater(app_container))
            logger.info("Background data updater task started.")
        else:
            app_container.updater_status.stop(detail="Background updater is disabled")
            logger.info("Background data updater is disabled.")

        try:
            yield
        finally:
            if updater_task is not None:
                logger.info("Shutting down background data updater task...")
                updater_task.cancel()
                done, _pending = await asyncio.wait(
                    {updater_task},
                    timeout=settings.updater_shutdown_grace_seconds,
                )
                if updater_task not in done:
                    logger.error(
                        "Background updater did not stop within %.1fs",
                        settings.updater_shutdown_grace_seconds,
                    )
                    app_container.updater_status.stop(
                        detail="Updater shutdown deadline exceeded"
                    )
                else:
                    try:
                        updater_task.result()
                    except asyncio.CancelledError:
                        logger.info(
                            "Background data updater task cancelled successfully."
                        )
                    except Exception:
                        logger.exception("Background updater failed during shutdown")
            app_container.update_cycle_trigger.clear()
            await app_container.close()

    docs_url = "/docs" if settings.is_dev else None
    redoc_url = "/redoc" if settings.is_dev else None
    openapi_url = "/openapi.json" if settings.is_dev else None
    application = FastAPI(
        title="Setlist Backend API",
        description=(
            "Search, administration, and background updates for VTuber "
            "karaoke setlist data"
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    application.state.container = app_container

    # Middleware receives the same immutable settings and authentication
    # service as route dependencies.
    application.add_middleware(
        GuestRateLimitMiddleware,
        settings=settings.rate_limit,
        auth_service=app_container.auth_service,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-CSRF-Token"],
    )
    application.include_router(v1_router)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
