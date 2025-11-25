import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment configuration
IS_DEV = os.getenv("APP_ENV", "prod") == "dev"

# Database configuration
# default values for one-time database
# ref: ../db/devscript/one_time_postgres_docker.ps1
# !! WARNING: In production, make sure to hide your postgres behind docker network,
# !! and do not expose it to public internet.
# !! Also, change the default username and password to secure your database.
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "vks_db")
DB_USER = os.getenv("DB_USER", "vks_db_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "vks_db_pwd")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Data updater configuration
# TODO: make this configurable via environment variables
DATA_UPDATE_INTERVAL = 60 * 30  # 完成一次更新後等待30分鐘再進行下一次更新
if IS_DEV:
    DATA_UPDATE_INTERVAL = 10  # for testing
