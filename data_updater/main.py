from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio

from routers.v1 import router as v1_router

IS_DEV = os.getenv("APP_ENV", "prod") == "dev"

# 數據更新任務間隔時間（秒）TODO: move to config file
DATA_UPDATE_INTERVAL = 60 * 30  # 完成一次更新後等待30分鐘(60秒 * 30)再進行下一次更新
DATA_UPDATE_INTERVAL = 10  # for testing

docs_url = "/docs" if IS_DEV else None
redoc_url = "/redoc" if IS_DEV else None
openapi_url = "/openapi.json" if IS_DEV else None


async def run_periodic_data_updater():
    while True:
        print("Updating song list data...")
        try:
            # 在此處調用實際的數據更新函數 TODO: implement the actual data update logic
            await asyncio.sleep(10)  # 模擬數據更新過程
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
