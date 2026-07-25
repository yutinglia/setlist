# vtuber-karaoke-search

Scrape VTuber karaoke streams, detect setlist comments (timestamp lists), store songs, and search them via a minimal HTTP API + React search UI.

**Status:** Phases 0–6 MVP are in place (pipeline + Tier B pacing, search API, extraction quality, search UI). Optional LLM cleaning is off by default (`LLM_CLEANING_ENABLED`). See [PLAN.md](PLAN.md) and [TODO.md](TODO.md).

## Stack

- **FastAPI** (`data_updater/`) — API + background data updater
- **PostgreSQL 18** + **Flyway** migrations (`db/migrations/`)
- **yt-dlp** — channel / video / comment scraping
- **SQLAlchemy 2** (async) + **sqlacodegen** for ORM models
- **React / Vite** (`frontend/`) — search UI (TanStack Router/Query, Zustand, Paraglide, Tailwind, shadcn/ui)

## Quick start (Dev Container)

1. Open this repo in Cursor or VS Code.
2. **Dev Containers: Reopen in Container**.
3. Compose starts Postgres, runs Flyway, prepares the Python/Node toolchain,
   and automatically starts the API and UI with hot reload.
4. The editor forwards ports 8000 and 5173 to the host. Open
   http://localhost:5173.

Service logs are available inside the Dev Container at
`/tmp/vtuber-karaoke-search-dev/backend.log` and
`/tmp/vtuber-karaoke-search-dev/frontend.log`.

| URL | Purpose |
|-----|---------|
| http://localhost:5173 | Search UI |
| http://localhost:5173/status | Live updater status |
| http://localhost:8000/v1/health | Health check |
| http://localhost:8000/v1/updater/status | Process-local updater status |
| http://localhost:8000/v1/songs/search?q=... | Search songs by title |
| http://localhost:8000/docs | OpenAPI (when `APP_ENV=dev`) |

More detail: [.devcontainer/README.md](.devcontainer/README.md) · [frontend/README.md](frontend/README.md).

## Quick start (local Docker)

```bash
# Postgres + migrations
docker compose -f docker-compose.dev.yml up -d db flyway

# Python deps (3.12 recommended)
cd data_updater
pip install -r requirements-dev.txt
APP_ENV=dev BACKGROUND_UPDATER_ENABLED=false uvicorn main:app --host 0.0.0.0 --port 8000

# UI (separate terminal)
cd frontend
npm install && npm run dev
```

Or run the production-oriented API container (uvicorn + background updater):

```bash
docker compose up --build data_updater
# Health: http://localhost:8000/v1/health  (includes DB ping)
```

Without Compose, Windows one-shot DB scripts live under `db/devscript/`.

## Search UI

Brand name in the UI: **Setlist** (`vtuber-karaoke-search`). Locales: English + Traditional Chinese (`en` / `zh-hant`).

- Debounced song search with pagination and YouTube `&t=` deep links
- Song detail, channel list → videos → video songs
- Live updater phase, channel/video context, cooldown, and last-error status
- Dev-only channel management; metadata refresh preserves existing setlists
- Vite proxies `/v1` to `http://127.0.0.1:8000` in dev; or set `VITE_API_BASE_URL`
- Use `APP_ENV=dev` for loose CORS, or set `CORS_ORIGINS` to the Vite origin (e.g. `http://localhost:5173`) in prod

## Search API (v1)

List/search endpoints accept `limit` (1–100, default 20) and `offset`
(0–1,000,000, default 0).

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v1/songs/search?q=` | Literal substring match; returns `video_url` with `&t=` deep link |
| GET | `/v1/songs/{id}` | Song detail + deep link + channel |
| GET | `/v1/channels` | Tracked channels |
| GET | `/v1/channels/{id}/videos` | Videos for a channel |
| GET | `/v1/videos/{id}/songs` | Songs for a video |
| GET | `/v1/updater/status` | Process-local scraper/analyzer status; internal errors are redacted |
| GET | `/v1/report/summary` | Database totals for scraped records, analysis, comments, songs, and backfill |
| POST | `/v1/channels` | Trusted management mode only; add a validated YouTube channel |
| POST | `/v1/channels/{id}/videos/refresh` | Trusted management mode only; safe metadata upsert |

Example:

```bash
curl 'http://localhost:8000/v1/songs/search?q=Stellar'
# → video_url like https://www.youtube.com/watch?v=...&t=300s
```

## Environment

Copy [`.env.example`](.env.example) to `.env` and adjust. Do not commit a real `.env`.

| Variable | Default | Notes |
|----------|---------|-------|
| `APP_ENV` | `prod` | `dev` enables docs, loose CORS, and management; scraper policy is unchanged |
| `BACKGROUND_UPDATER_ENABLED` | `false` | Opt in explicitly; production Compose defaults it to `true` |
| `MANAGEMENT_API_ENABLED` | `true` (dev) / `false` (prod) | Enables mutating channel/scraper endpoints |
| `CORS_ORIGINS` | _(empty)_ | Comma-separated browser origins in prod; ignored when `APP_ENV=dev` |
| `DB_HOST` | `localhost` | Use `db` inside Compose / Dev Container |
| `DB_PORT` | `5432` | |
| `DB_NAME` | `vks_db` | |
| `DB_USER` | `vks_db_user` | Local/dev only — change for anything public |
| `DB_PASSWORD` | `vks_db_pwd` | Local/dev only |
| `DATABASE_URL` | built from `DB_*` | `postgresql+asyncpg://...` |
| `DATA_UPDATE_INTERVAL` | `300` | Environment-independent worker heartbeat; only due work calls YouTube |
| `UPDATE_STEADY_SCAN_INTERVAL` | `21600` | Successful recent-record scan interval per channel (6 hours) |
| `UPDATE_STEADY_CHANNELS_PER_CYCLE` | `3` | Due steady-state channels checked per worker cycle |
| `UPDATE_MAX_COMMENT_SCRAPES` | `3` | Max comment scrapes per updater cycle |
| `UPDATE_MAX_VIDEOS` | `40` | Recent entries considered per channel scan |
| `UPDATE_BACKFILL_PAGE_SIZE` | `100` | Flat playlist entries requested from each tab per durable page |
| `UPDATE_BACKFILL_PAGES_PER_CYCLE` | `3` | Max pages processed for one backfill channel per worker cycle |
| `UPDATE_BACKFILL_CHANNELS_PER_CYCLE` | `1` | Max backfill channels processed per worker cycle |
| `UPDATE_MAX_METADATA_SCRAPES` | `10` | Per-video enrichment cap for manual metadata refresh |
| `UPDATE_LIST_SLEEP_MIN` / `MAX` | `3` / `7` | Jitter between backfill pages |
| `UPDATE_SCRAPE_SLEEP_MIN` / `MAX` | `20` / `40` | Jitter between comment scrapes |
| `UPDATE_MAX_ANALYZE_ATTEMPTS` | `3` | Max content-analysis attempts; blocks do not consume attempts |
| `UPDATE_ANALYSIS_RECHECK_SECONDS` | `86400` | Delay before rechecking a successful “no setlist” archive |
| `UPDATE_YOUTUBE_COOLDOWN_SECONDS` | `21600` | Skip all YouTube work after a suspected block (6 hours) |
| `YTDLP_COMMENT_SLEEP_INTERVAL` / `MAX` | `2` / `10` | yt-dlp sleeps for comment scrapes |
| `LLM_CLEANING_ENABLED` | `false` | Optional OpenAI-compatible setlist cleaning after regex extract |
| `LLM_API_URL` | OpenAI chat completions URL | Used only when cleaning is enabled |
| `LLM_API_KEY` | _(empty)_ | Required when `LLM_CLEANING_ENABLED=true` |
| `LLM_MODEL` | `gpt-4o-mini` | Chat model id |
| `LLM_MAX_CLEANING_ATTEMPTS` | `2` | Cap LLM clean tries per video |
| `LLM_MAX_INPUT_CHARS` | `20000` | Truncate unusually large comments before optional LLM calls |
| `VITE_API_BASE_URL` | _(empty)_ | Frontend only; leave empty in Vite dev (proxy). See `frontend/.env.example` |
| `VITE_MANAGEMENT_UI_ENABLED` | `false` in production builds | Show management UI only when the backend also enables it |

## Seed karaoke channels

After Postgres + Flyway are up, insert the sample channels (@UTANOch, @QuonTama, @Leona_Shishigami):

```bash
docker compose -f docker-compose.dev.yml exec -T db \
  psql -U vks_db_user -d vks_db < db/devscript/seed_channels.sql
```

Then start the API from `data_updater/` with
`BACKGROUND_UPDATER_ENABLED=true`. Development and production use the same
five-minute worker heartbeat and scraping policy. A persisted per-channel due
time means established channels call YouTube at most every six hours. Newly
added channels instead backfill full Streams + Videos history in 100-entry,
durable pages (up to three pages per cycle). A successful `POST /v1/channels`
immediately wakes the enabled background updater and prioritizes that channel;
multiple additions remain separate bounded cycles. Failed/partial pages retain
their cursor and retry fairly. Comment analysis is a separate global queue,
limited to three archives per cycle with 20–40 second jitter. Live, upcoming,
and post-live records are ignored until yt-dlp reports an archive. Flat
channel-tab entries derive an approximate date from the same list response
(no per-video metadata fan-out); the UI labels it as approximate. A later
manual metadata refresh or already-required comment scrape upgrades it to an
exact date. Exact dates are never downgraded by later flat refreshes. Playlist
position remains the fallback ordering when YouTube omits even relative date
text, and a block cooldown is persisted across process restarts.

Every normal archive discovered in the bounded Streams + Videos scans is kept,
including records currently classified as `other`. Only karaoke candidates
enter the comment queue. This preserves enough history to reclassify old rows
when the title rules improve instead of requiring another full channel
backfill.

Channel-list and full-video yt-dlp observations are stored separately with
source, capture time, schema version, and dropped-field provenance. Snapshots
retain stable metadata (including description, tags, statistics, language,
availability, dates, and unknown future extractor fields) within a 256 KiB
record / 64 KiB field bound. Volatile playback formats, signed URLs, headers,
captions, and subtitles are deliberately excluded; comments are stored in
their own analysis snapshot. A sparse list refresh therefore cannot erase
richer full metadata. A temporary negative re-analysis also preserves any
previous successful setlist and songs.

To test the exact background path once without leaving a scheduler running:

```bash
cd data_updater
python run_updater_once.py
```

After songs exist, try the UI or `GET /v1/songs/search?q=...`.

### Tests

From `data_updater/`:

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

Analyzer and timestamp-helper unit tests always run (including pinned/uploader preference and extra setlist formats). Repository write smoke tests skip if Postgres is unreachable.

GitHub Actions runs Ruff, all backend tests against PostgreSQL 18 after Flyway
migrations, the frontend lint/build, and a production runtime image build.

### Setlist extraction notes

- Comment choice prefers **pinned**, then **uploader**, then timestamp density / likes.
- Line formats include `1:23 Title`, `Title - 1:23`, `01. Title 0:12:00`, parenthesized timestamps, and full-width `：`.
- An explicit setlist section stops at a later stream-chapter heading, avoiding chat/announcement timestamps in mixed community comments.
- Songs are deduped within a video by `(timestamp, casefold(title))`. A successful re-analysis uses `replace_for_video` (delete + insert), while a temporary negative observation does not erase the previous successful setlist.

## Layout

```
vtuber-karaoke-search/
├── .devcontainer/     # Dev Container (app + Postgres + Flyway)
├── frontend/          # Vite React search UI
├── data_updater/      # FastAPI service (run with cwd = this dir)
├── db/migrations/     # Flyway SQL (schema source of truth; V1–V8)
├── .env.example       # Sample env vars (copy to .env)
├── AGENTS.md          # Instructions for coding agents
├── PLAN.md            # Phased implementation plan
└── TODO.md            # Checklist derived from the plan
```

## Docs for contributors / agents

- [AGENTS.md](AGENTS.md) — conventions and do-nots
- [PLAN.md](PLAN.md) — phases 0–6
- [frontend/README.md](frontend/README.md) — UI run / proxy
- [data_updater/NOTE.md](data_updater/NOTE.md) — yt-dlp payload shape notes
