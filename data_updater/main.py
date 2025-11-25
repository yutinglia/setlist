from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from config import IS_DEV, DATA_UPDATE_INTERVAL
from db import async_session_factory
from repositories import ChannelRepository, VideoRepository, SongRepository
from routers.v1 import router as v1_router
from services.data_updater import DataUpdater

docs_url = "/docs" if IS_DEV else None
redoc_url = "/redoc" if IS_DEV else None
openapi_url = "/openapi.json" if IS_DEV else None


async def run_periodic_data_updater():
    while True:
        print("Updating song list data...")
        try:
            async with async_session_factory() as session:
                channel_repo = ChannelRepository(session)
                video_repo = VideoRepository(session)
                song_repo = SongRepository(session)
                data_updater = DataUpdater(channel_repo, video_repo, song_repo)
                await data_updater.update()
            print("Song list data updated successfully.")
        except asyncio.CancelledError:
            print("Data updater task cancelled. Terminating loop.")
            break
        except Exception as e:
            print(f"Error updating song list data: {e}")
        print("Waiting for the next update cycle...")
        await asyncio.sleep(DATA_UPDATE_INTERVAL)


# 啟動時啟動背景任務
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動背景任務
    updater_task = asyncio.create_task(run_periodic_data_updater())
    print("Background data updater task started.")

    yield  # 應用程式運行中

    # 關閉時取消背景任務
    print("Shutting down background data updater task...")
    updater_task.cancel()
    try:
        await updater_task
    except asyncio.CancelledError:
        print("Background data updater task cancelled successfully.")


app = FastAPI(
    title="VTuber Karaoke Search Data Updater API",
    description="API for updating VTuber karaoke song data",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊 v1 路由
app.include_router(v1_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
