import math
import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL

from services.scrape_policy import ScrapePolicy

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

# Scraping is opt-in in every environment. Production Compose explicitly enables
# it. This prevents APP_ENV from silently changing scraper behavior.
BACKGROUND_UPDATER_ENABLED = _env_bool("BACKGROUND_UPDATER_ENABLED", default=False)

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

# Scraper scheduling. Defaults are identical in dev/prod. The worker wakes every
# five minutes, but steady-state channel discovery is persisted and only becomes
# due every six hours. Backfill is deliberately much faster than comment analysis:
# a flat playlist page is cheap, while comment endpoints are more sensitive.
DATA_UPDATE_INTERVAL = _env_int("DATA_UPDATE_INTERVAL", 5 * 60, minimum=1)
UPDATE_STEADY_SCAN_INTERVAL = _env_int(
    "UPDATE_STEADY_SCAN_INTERVAL", 6 * 60 * 60, minimum=60
)
UPDATE_STEADY_RETRY_BASE = _env_int("UPDATE_STEADY_RETRY_BASE", 15 * 60, minimum=60)
UPDATE_STEADY_CHANNELS_PER_CYCLE = _env_int(
    "UPDATE_STEADY_CHANNELS_PER_CYCLE", 3, minimum=1
)
UPDATE_MAX_VIDEOS = _env_int("UPDATE_MAX_VIDEOS", 40, minimum=1)
UPDATE_MAX_METADATA_SCRAPES = _env_int("UPDATE_MAX_METADATA_SCRAPES", 10, minimum=0)

UPDATE_BACKFILL_PAGE_SIZE = _env_int("UPDATE_BACKFILL_PAGE_SIZE", 100, minimum=1)
UPDATE_BACKFILL_PAGES_PER_CYCLE = _env_int(
    "UPDATE_BACKFILL_PAGES_PER_CYCLE", 3, minimum=1
)
UPDATE_BACKFILL_CHANNELS_PER_CYCLE = _env_int(
    "UPDATE_BACKFILL_CHANNELS_PER_CYCLE", 1, minimum=1
)

UPDATE_MAX_COMMENT_SCRAPES = _env_int("UPDATE_MAX_COMMENT_SCRAPES", 3, minimum=0)
UPDATE_MAX_COMMENTS_PER_VIDEO = _env_int("UPDATE_MAX_COMMENTS_PER_VIDEO", 50, minimum=1)
UPDATE_MAX_ANALYZE_ATTEMPTS = _env_int("UPDATE_MAX_ANALYZE_ATTEMPTS", 3, minimum=1)
UPDATE_ANALYSIS_RECHECK_SECONDS = _env_int(
    "UPDATE_ANALYSIS_RECHECK_SECONDS", 24 * 60 * 60, minimum=60
)
UPDATE_ANALYSIS_RETRY_BASE = _env_int("UPDATE_ANALYSIS_RETRY_BASE", 30 * 60, minimum=60)

UPDATE_LIST_SLEEP_MIN = _env_float("UPDATE_LIST_SLEEP_MIN", 3)
UPDATE_LIST_SLEEP_MAX = _env_float("UPDATE_LIST_SLEEP_MAX", 7)
if UPDATE_LIST_SLEEP_MAX < UPDATE_LIST_SLEEP_MIN:
    raise ValueError("UPDATE_LIST_SLEEP_MAX must be >= UPDATE_LIST_SLEEP_MIN")

UPDATE_SCRAPE_SLEEP_MIN = _env_float("UPDATE_SCRAPE_SLEEP_MIN", 20)
UPDATE_SCRAPE_SLEEP_MAX = _env_float("UPDATE_SCRAPE_SLEEP_MAX", 40)
if UPDATE_SCRAPE_SLEEP_MAX < UPDATE_SCRAPE_SLEEP_MIN:
    raise ValueError("UPDATE_SCRAPE_SLEEP_MAX must be >= UPDATE_SCRAPE_SLEEP_MIN")

YTDLP_LIST_SLEEP_INTERVAL = _env_float("YTDLP_LIST_SLEEP_INTERVAL", 1)
YTDLP_LIST_MAX_SLEEP_INTERVAL = _env_float("YTDLP_LIST_MAX_SLEEP_INTERVAL", 2)
if YTDLP_LIST_MAX_SLEEP_INTERVAL < YTDLP_LIST_SLEEP_INTERVAL:
    raise ValueError(
        "YTDLP_LIST_MAX_SLEEP_INTERVAL must be >= YTDLP_LIST_SLEEP_INTERVAL"
    )

YTDLP_COMMENT_SLEEP_INTERVAL = _env_float("YTDLP_COMMENT_SLEEP_INTERVAL", 2)
YTDLP_COMMENT_MAX_SLEEP_INTERVAL = _env_float("YTDLP_COMMENT_MAX_SLEEP_INTERVAL", 10)
if YTDLP_COMMENT_MAX_SLEEP_INTERVAL < YTDLP_COMMENT_SLEEP_INTERVAL:
    raise ValueError(
        "YTDLP_COMMENT_MAX_SLEEP_INTERVAL must be >= YTDLP_COMMENT_SLEEP_INTERVAL"
    )

# A real block is treated more conservatively than an ordinary transient error.
UPDATE_YOUTUBE_COOLDOWN_SECONDS = _env_int(
    "UPDATE_YOUTUBE_COOLDOWN_SECONDS", 6 * 60 * 60, minimum=60
)

SCRAPE_POLICY = ScrapePolicy(
    worker_interval_seconds=DATA_UPDATE_INTERVAL,
    steady_scan_interval_seconds=UPDATE_STEADY_SCAN_INTERVAL,
    steady_retry_base_seconds=UPDATE_STEADY_RETRY_BASE,
    steady_channels_per_cycle=UPDATE_STEADY_CHANNELS_PER_CYCLE,
    recent_videos_per_channel=UPDATE_MAX_VIDEOS,
    metadata_scrapes_per_refresh=UPDATE_MAX_METADATA_SCRAPES,
    backfill_page_size=UPDATE_BACKFILL_PAGE_SIZE,
    backfill_pages_per_cycle=UPDATE_BACKFILL_PAGES_PER_CYCLE,
    backfill_channels_per_cycle=UPDATE_BACKFILL_CHANNELS_PER_CYCLE,
    comment_scrapes_per_cycle=UPDATE_MAX_COMMENT_SCRAPES,
    max_comments_per_video=UPDATE_MAX_COMMENTS_PER_VIDEO,
    max_analysis_attempts=UPDATE_MAX_ANALYZE_ATTEMPTS,
    analysis_recheck_seconds=UPDATE_ANALYSIS_RECHECK_SECONDS,
    analysis_retry_base_seconds=UPDATE_ANALYSIS_RETRY_BASE,
    inter_list_sleep_min=UPDATE_LIST_SLEEP_MIN,
    inter_list_sleep_max=UPDATE_LIST_SLEEP_MAX,
    inter_comment_sleep_min=UPDATE_SCRAPE_SLEEP_MIN,
    inter_comment_sleep_max=UPDATE_SCRAPE_SLEEP_MAX,
    ytdlp_list_sleep_interval=YTDLP_LIST_SLEEP_INTERVAL,
    ytdlp_list_max_sleep_interval=YTDLP_LIST_MAX_SLEEP_INTERVAL,
    ytdlp_comment_sleep_interval=YTDLP_COMMENT_SLEEP_INTERVAL,
    ytdlp_comment_max_sleep_interval=YTDLP_COMMENT_MAX_SLEEP_INTERVAL,
    youtube_cooldown_seconds=UPDATE_YOUTUBE_COOLDOWN_SECONDS,
)

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
