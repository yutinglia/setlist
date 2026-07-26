import math
import os
from ipaddress import ip_network

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

# Mutation/scraper endpoints always require an authenticated administrator.
# This flag is only an emergency kill switch; it is not an authorization layer.
MANAGEMENT_API_ENABLED = _env_bool("MANAGEMENT_API_ENABLED", default=True)

# Single-administrator authentication. Only password hashes and a random session
# signing secret belong in deployment environment variables; never store a
# plaintext password in configuration.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin").strip()
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()
AUTH_SESSION_TTL_SECONDS = _env_int(
    "AUTH_SESSION_TTL_SECONDS", 12 * 60 * 60, minimum=300
)
AUTH_COOKIE_SECURE = _env_bool("AUTH_COOKIE_SECURE", default=APP_ENV == "prod")
if not ADMIN_USERNAME:
    raise ValueError("ADMIN_USERNAME must not be empty")
if ADMIN_PASSWORD_HASH and not ADMIN_PASSWORD_HASH.startswith("$argon2id$"):
    raise ValueError("ADMIN_PASSWORD_HASH must be an Argon2id hash")
if SESSION_SECRET and len(SESSION_SECRET.encode("utf-8")) < 32:
    raise ValueError("SESSION_SECRET must be at least 32 bytes")

# Anonymous API clients are limited per source address. Authenticated admin
# sessions are exempt so the private updater dashboard can poll normally.
GUEST_RATE_LIMIT_ENABLED = _env_bool("GUEST_RATE_LIMIT_ENABLED", default=True)
GUEST_RATE_LIMIT_REQUESTS = _env_int("GUEST_RATE_LIMIT_REQUESTS", 60, minimum=1)
GUEST_RATE_LIMIT_WINDOW_SECONDS = _env_int(
    "GUEST_RATE_LIMIT_WINDOW_SECONDS", 60, minimum=1
)
LOGIN_RATE_LIMIT_REQUESTS = _env_int("LOGIN_RATE_LIMIT_REQUESTS", 5, minimum=1)
LOGIN_RATE_LIMIT_WINDOW_SECONDS = _env_int(
    "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 5 * 60, minimum=1
)

_TRUSTED_PROXY_CIDRS_RAW = os.getenv("TRUSTED_PROXY_CIDRS", "")
TRUSTED_PROXY_CIDRS = tuple(
    ip_network(value.strip(), strict=False)
    for value in _TRUSTED_PROXY_CIDRS_RAW.split(",")
    if value.strip()
)

# Cross-origin cookies require explicit origins in every environment. The Vite
# dev server normally uses its same-origin proxy, while these defaults support
# direct local API calls without permitting arbitrary credentialed origins.
_DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173" if IS_DEV else ""
_CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
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

YTDLP_SOCKET_TIMEOUT_SECONDS = _env_float("YTDLP_SOCKET_TIMEOUT_SECONDS", 30, minimum=1)
YTDLP_RETRIES = _env_int("YTDLP_RETRIES", 2)
YTDLP_EXTRACTOR_RETRIES = _env_int("YTDLP_EXTRACTOR_RETRIES", 2)
YTDLP_OPERATION_TIMEOUT_SECONDS = _env_float(
    "YTDLP_OPERATION_TIMEOUT_SECONDS", 300, minimum=10
)
YTDLP_TERMINATE_GRACE_SECONDS = _env_float(
    "YTDLP_TERMINATE_GRACE_SECONDS", 5, minimum=0.1
)
UPDATER_SHUTDOWN_GRACE_SECONDS = _env_float(
    "UPDATER_SHUTDOWN_GRACE_SECONDS", 20, minimum=1
)
UPDATER_HEARTBEAT_INTERVAL_SECONDS = _env_float(
    "UPDATER_HEARTBEAT_INTERVAL_SECONDS", 30, minimum=1
)
UPDATER_HEARTBEAT_STALE_SECONDS = _env_float(
    "UPDATER_HEARTBEAT_STALE_SECONDS", 120, minimum=2
)
if UPDATER_HEARTBEAT_STALE_SECONDS <= UPDATER_HEARTBEAT_INTERVAL_SECONDS:
    raise ValueError(
        "UPDATER_HEARTBEAT_STALE_SECONDS must be greater than "
        "UPDATER_HEARTBEAT_INTERVAL_SECONDS"
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
    ytdlp_socket_timeout_seconds=YTDLP_SOCKET_TIMEOUT_SECONDS,
    ytdlp_retries=YTDLP_RETRIES,
    ytdlp_extractor_retries=YTDLP_EXTRACTOR_RETRIES,
    ytdlp_operation_timeout_seconds=YTDLP_OPERATION_TIMEOUT_SECONDS,
    ytdlp_terminate_grace_seconds=YTDLP_TERMINATE_GRACE_SECONDS,
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
