import math
import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL

# Load environment variables from .env file
load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be one of: true/false, 1/0, yes/no, on/off")


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _env_float(name: str, default: float, *, minimum: float = 0.0) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {raw!r}")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


# Environment configuration
APP_ENV = os.getenv("APP_ENV", "prod").strip().lower()
if APP_ENV not in {"dev", "prod", "test"}:
    raise ValueError("APP_ENV must be one of: dev, prod, test")
IS_DEV = APP_ENV == "dev"

# Scraping is intentionally opt-in during development. Starting a dev server
# (especially with auto-reload) must not hit YouTube every ten seconds by surprise.
BACKGROUND_UPDATER_ENABLED = _env_bool(
    "BACKGROUND_UPDATER_ENABLED", default=not IS_DEV and APP_ENV != "test"
)

# Mutation/scraper endpoints are local management tools, not public API surface.
MANAGEMENT_API_ENABLED = _env_bool("MANAGEMENT_API_ENABLED", default=IS_DEV)

# CORS is loose in dev. Production uses explicit comma-separated origins;
# an empty value allows no browser origins.
_CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip()]

# Database configuration
# default values for one-time database
# ref: ../db/devscript/one_time_postgres_docker.ps1
# !! WARNING: In production, make sure to hide your postgres behind docker network,
# !! and do not expose it to public internet.
# !! Also, change the default username and password to secure your database.
DB_HOST = os.getenv("DB_HOST", "localhost").strip()
DB_PORT = _env_int("DB_PORT", 5432, minimum=1)
if DB_PORT > 65_535:
    raise ValueError("DB_PORT must be <= 65535")
DB_NAME = os.getenv("DB_NAME", "vks_db").strip()
DB_USER = os.getenv("DB_USER", "vks_db_user").strip()
DB_PASSWORD = os.getenv("DB_PASSWORD", "vks_db_pwd")
if not DB_HOST or not DB_NAME or not DB_USER:
    raise ValueError("DB_HOST, DB_NAME, and DB_USER must not be empty")
_DATABASE_URL_OVERRIDE = os.getenv("DATABASE_URL")
if _DATABASE_URL_OVERRIDE:
    DATABASE_URL = _DATABASE_URL_OVERRIDE
else:
    DATABASE_URL = URL.create(
        "postgresql+asyncpg",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    ).render_as_string(hide_password=False)

# Data updater configuration
# Default: 10s in dev, 30m otherwise. Override with DATA_UPDATE_INTERVAL (seconds).
_DEFAULT_UPDATE_INTERVAL = 10 if IS_DEV else 60 * 30
DATA_UPDATE_INTERVAL = _env_int(
    "DATA_UPDATE_INTERVAL", _DEFAULT_UPDATE_INTERVAL, minimum=1
)

# Phase 2 — YouTube access-limit avoidance (Tier B)
UPDATE_MAX_COMMENT_SCRAPES = _env_int("UPDATE_MAX_COMMENT_SCRAPES", 5, minimum=0)
UPDATE_MAX_VIDEOS = _env_int("UPDATE_MAX_VIDEOS", 20, minimum=1)
UPDATE_MAX_METADATA_SCRAPES = _env_int("UPDATE_MAX_METADATA_SCRAPES", 10, minimum=0)
UPDATE_SCRAPE_SLEEP_MIN = _env_float("UPDATE_SCRAPE_SLEEP_MIN", 3)
UPDATE_SCRAPE_SLEEP_MAX = _env_float("UPDATE_SCRAPE_SLEEP_MAX", 8)
if UPDATE_SCRAPE_SLEEP_MAX < UPDATE_SCRAPE_SLEEP_MIN:
    raise ValueError("UPDATE_SCRAPE_SLEEP_MAX must be >= UPDATE_SCRAPE_SLEEP_MIN")
UPDATE_YOUTUBE_COOLDOWN_SECONDS = _env_int("UPDATE_YOUTUBE_COOLDOWN_SECONDS", 3600)
UPDATE_MAX_ANALYZE_ATTEMPTS = _env_int("UPDATE_MAX_ANALYZE_ATTEMPTS", 3, minimum=1)

# New-channel full-catalog backfill (one playlist page per channel per cycle)
UPDATE_BACKFILL_PAGE_SIZE = _env_int(
    "UPDATE_BACKFILL_PAGE_SIZE", UPDATE_MAX_VIDEOS, minimum=1
)
UPDATE_BACKFILL_CHANNELS_PER_CYCLE = _env_int(
    "UPDATE_BACKFILL_CHANNELS_PER_CYCLE", 1, minimum=1
)
# yt-dlp sleep intervals for comment scraping (raised vs channel/video list scrapers)
YTDLP_COMMENT_SLEEP_INTERVAL = _env_float("YTDLP_COMMENT_SLEEP_INTERVAL", 2)
YTDLP_COMMENT_MAX_SLEEP_INTERVAL = _env_float("YTDLP_COMMENT_MAX_SLEEP_INTERVAL", 10)
if YTDLP_COMMENT_MAX_SLEEP_INTERVAL < YTDLP_COMMENT_SLEEP_INTERVAL:
    raise ValueError(
        "YTDLP_COMMENT_MAX_SLEEP_INTERVAL must be >= YTDLP_COMMENT_SLEEP_INTERVAL"
    )

# How many top comments to fetch per video
UPDATE_MAX_COMMENTS_PER_VIDEO = _env_int("UPDATE_MAX_COMMENTS_PER_VIDEO", 50, minimum=1)

# Phase 5 — optional LLM setlist cleaning (off by default; regex path is primary)
LLM_CLEANING_ENABLED = _env_bool("LLM_CLEANING_ENABLED", False)
LLM_API_URL = os.getenv(
    "LLM_API_URL",
    "https://api.openai.com/v1/chat/completions",
)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_SECONDS = _env_float("LLM_TIMEOUT_SECONDS", 30, minimum=0.1)
LLM_MAX_CLEANING_ATTEMPTS = _env_int("LLM_MAX_CLEANING_ATTEMPTS", 2, minimum=1)
LLM_MAX_INPUT_CHARS = _env_int("LLM_MAX_INPUT_CHARS", 20_000, minimum=100)
