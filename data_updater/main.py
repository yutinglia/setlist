from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging

from config import IS_DEV, DATA_UPDATE_INTERVAL, CORS_ORIGINS
from db import async_session_factory
from repositories import ChannelRepository, VideoRepository, SongRepository
from routers.v1 import router as v1_router
from services.data_updater import DataUpdater
from services.updater_status import UpdaterPhase, updater_status

logger = logging.getLogger(__name__)

docs_url = "/docs" if IS_DEV else None
redoc_url = "/redoc" if IS_DEV else None
openapi_url = "/openapi.json" if IS_DEV else None


async def run_periodic_data_updater():
    updater_status.set(
        UpdaterPhase.WAITING,
        detail="Waiting for first update cycle",
        clear_channel=True,
        clear_video=True,
    )
    while True:
        logger.info("Updating song list data...")
        try:
            async with async_session_factory() as session:
                channel_repo = ChannelRepository(session)
                video_repo = VideoRepository(session)
                song_repo = SongRepository(session)
                data_updater = DataUpdater(
                    session, channel_repo, video_repo, song_repo
                )
                await data_updater.update()
            logger.info("Song list data updated successfully.")
        except asyncio.CancelledError:
            logger.info("Data updater task cancelled. Terminating loop.")
            updater_status.set(
                UpdaterPhase.IDLE,
                detail="Updater stopped",
                clear_channel=True,
                clear_video=True,
            )
            break
        except Exception as exc:
            logger.exception("Error updating song list data")
            updater_status.end_cycle(error=str(exc))
        logger.info("Waiting for the next update cycle...")
        remaining = DataUpdater.youtube_cooldown_remaining()
        if remaining > 0:
            updater_status.set(
                UpdaterPhase.COOLDOWN,
                detail=f"YouTube cooldown ({remaining:.0f}s remaining)",
                clear_channel=True,
                clear_video=True,
            )
        else:
            updater_status.set(
                UpdaterPhase.WAITING,
                detail=f"Waiting {DATA_UPDATE_INTERVAL}s for next cycle",
                clear_channel=True,
                clear_video=True,
            )
        await asyncio.sleep(DATA_UPDATE_INTERVAL)


# 啟動時啟動背景任務
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動背景任務
    updater_task = asyncio.create_task(run_periodic_data_updater())
    logger.info("Background data updater task started.")

    yield  # 應用程式運行中

    # 關閉時取消背景任務
    logger.info("Shutting down background data updater task...")
    updater_task.cancel()
    try:
        await updater_task
    except asyncio.CancelledError:
        logger.info("Background data updater task cancelled successfully.")


app = FastAPI(
    title="VTuber Karaoke Search Data Updater API",
    description="API for updating VTuber karaoke song data",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

# CORS: loose only in APP_ENV=dev; prod uses explicit CORS_ORIGINS
if IS_DEV:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=bool(CORS_ORIGINS),
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 註冊 v1 路由
app.include_router(v1_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
