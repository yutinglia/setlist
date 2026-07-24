import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment configuration
IS_DEV = os.getenv("APP_ENV", "prod") == "dev"

# CORS: loose in dev; explicit comma-separated origins in prod (empty = no browser origins)
_CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip()]

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
# Default: 10s in dev, 30m otherwise. Override with DATA_UPDATE_INTERVAL (seconds).
_DEFAULT_UPDATE_INTERVAL = 10 if IS_DEV else 60 * 30
DATA_UPDATE_INTERVAL = int(
    os.getenv("DATA_UPDATE_INTERVAL", str(_DEFAULT_UPDATE_INTERVAL))
)

# Phase 2 — YouTube access-limit avoidance (Tier B)
UPDATE_MAX_COMMENT_SCRAPES = int(os.getenv("UPDATE_MAX_COMMENT_SCRAPES", "5"))
UPDATE_MAX_VIDEOS = int(os.getenv("UPDATE_MAX_VIDEOS", "20"))
UPDATE_SCRAPE_SLEEP_MIN = float(os.getenv("UPDATE_SCRAPE_SLEEP_MIN", "3"))
UPDATE_SCRAPE_SLEEP_MAX = float(os.getenv("UPDATE_SCRAPE_SLEEP_MAX", "8"))
UPDATE_YOUTUBE_COOLDOWN_SECONDS = int(
    os.getenv("UPDATE_YOUTUBE_COOLDOWN_SECONDS", "3600")
)
UPDATE_MAX_ANALYZE_ATTEMPTS = int(os.getenv("UPDATE_MAX_ANALYZE_ATTEMPTS", "3"))

# yt-dlp sleep intervals for comment scraping (raised vs channel/video list scrapers)
YTDLP_COMMENT_SLEEP_INTERVAL = float(os.getenv("YTDLP_COMMENT_SLEEP_INTERVAL", "2"))
YTDLP_COMMENT_MAX_SLEEP_INTERVAL = float(
    os.getenv("YTDLP_COMMENT_MAX_SLEEP_INTERVAL", "10")
)

# How many top comments to fetch per video
UPDATE_MAX_COMMENTS_PER_VIDEO = int(os.getenv("UPDATE_MAX_COMMENTS_PER_VIDEO", "50"))
