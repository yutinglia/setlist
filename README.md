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
3. Compose starts Postgres, runs Flyway, and prepares the Python/Node toolchain.
4. Run the API:

```bash
cd data_updater
APP_ENV=dev uvicorn main:app --host 0.0.0.0 --port 8000
```

5. Run the UI (Node 20+):

```bash
cd frontend
npm install
npm run dev
```

| URL | Purpose |
|-----|---------|
| http://localhost:5173 | Search UI |
| http://localhost:8000/v1/health | Health check |
| http://localhost:8000/v1/songs/search?q=... | Search songs by title |
| http://localhost:8000/docs | OpenAPI (when `APP_ENV=dev`) |

More detail: [.devcontainer/README.md](.devcontainer/README.md) · [frontend/README.md](frontend/README.md).

## Quick start (local Docker)

```bash
# Postgres + migrations
docker compose -f docker-compose.dev.yml up -d db flyway

# Python deps (3.12 recommended)
cd data_updater
pip install -r requirements.txt
APP_ENV=dev uvicorn main:app --host 0.0.0.0 --port 8000

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
- Vite proxies `/v1` to `http://127.0.0.1:8000` in dev; or set `VITE_API_BASE_URL`
- Use `APP_ENV=dev` for loose CORS, or set `CORS_ORIGINS` to the Vite origin (e.g. `http://localhost:5173`) in prod

## Search API (v1)

List/search endpoints accept `limit` (1–100, default 20) and `offset` (default 0).

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v1/songs/search?q=` | ILIKE on `songs.title`; returns `video_url` with `&t=` deep link |
| GET | `/v1/songs/{id}` | Song detail + deep link + channel |
| GET | `/v1/channels` | Tracked channels |
| GET | `/v1/channels/{id}/videos` | Videos for a channel |
| GET | `/v1/videos/{id}/songs` | Songs for a video |

Example:

```bash
curl 'http://localhost:8000/v1/songs/search?q=Stellar'
# → video_url like https://www.youtube.com/watch?v=...&t=300s
```

## Environment

Copy [`.env.example`](.env.example) to `.env` and adjust. Do not commit a real `.env`.

| Variable | Default | Notes |
|----------|---------|-------|
| `APP_ENV` | `prod` | Set `dev` for docs, `/v1/example`, loose CORS, short updater interval |
| `CORS_ORIGINS` | _(empty)_ | Comma-separated browser origins in prod; ignored when `APP_ENV=dev` |
| `DB_HOST` | `localhost` | Use `db` inside Compose / Dev Container |
| `DB_PORT` | `5432` | |
| `DB_NAME` | `vks_db` | |
| `DB_USER` | `vks_db_user` | Local/dev only — change for anything public |
| `DB_PASSWORD` | `vks_db_pwd` | Local/dev only |
| `DATABASE_URL` | built from `DB_*` | `postgresql+asyncpg://...` |
| `DATA_UPDATE_INTERVAL` | `10` (dev) / `1800` (prod) | Seconds between updater cycles; use `1800+` once scraping is on |
| `UPDATE_MAX_COMMENT_SCRAPES` | `5` | Max comment scrapes per updater cycle |
| `UPDATE_MAX_VIDEOS` | `20` | Max videos upserted/considered per channel per cycle |
| `UPDATE_SCRAPE_SLEEP_MIN` / `MAX` | `3` / `8` | Jitter sleep (seconds) between comment scrapes |
| `UPDATE_MAX_ANALYZE_ATTEMPTS` | `3` | Skip videos after this many failed/empty analyses |
| `UPDATE_YOUTUBE_COOLDOWN_SECONDS` | `3600` | Skip all YouTube work after a suspected block |
| `YTDLP_COMMENT_SLEEP_INTERVAL` / `MAX` | `2` / `10` | yt-dlp sleeps for comment scrapes |
| `LLM_CLEANING_ENABLED` | `false` | Optional OpenAI-compatible setlist cleaning after regex extract |
| `LLM_API_URL` | OpenAI chat completions URL | Used only when cleaning is enabled |
| `LLM_API_KEY` | _(empty)_ | Required when `LLM_CLEANING_ENABLED=true` |
| `LLM_MODEL` | `gpt-4o-mini` | Chat model id |
| `LLM_MAX_CLEANING_ATTEMPTS` | `2` | Cap LLM clean tries per video |
| `VITE_API_BASE_URL` | _(empty)_ | Frontend only; leave empty in Vite dev (proxy). See `frontend/.env.example` |

## Seed karaoke channels

After Postgres + Flyway are up, insert the sample channels (Suisei + Marine):

```bash
docker compose -f docker-compose.dev.yml exec -T db \
  psql -U vks_db_user -d vks_db < db/devscript/seed_channels.sql
```

Then start the API from `data_updater/` (prefer `DATA_UPDATE_INTERVAL=1800`). One cycle scrapes recent videos, analyzes up to `UPDATE_MAX_COMMENT_SCRAPES` of them, and writes songs when a setlist comment is found. Logs show caps, jitter, and cooldown. After songs exist, try the UI or `GET /v1/songs/search?q=...`.

### Tests

From `data_updater/`:

```bash
pip install -r requirements.txt
pytest
```

Analyzer and timestamp-helper unit tests always run (including pinned/uploader preference and extra setlist formats). Repository write smoke tests skip if Postgres is unreachable.

### Setlist extraction notes

- Comment choice prefers **pinned**, then **uploader**, then timestamp density / likes.
- Line formats include `1:23 Title`, `Title - 1:23`, `01. Title 0:12:00`, parenthesized timestamps, and full-width `：`.
- Songs are deduped within a video by `(timestamp, casefold(title))`. Re-analysis uses `replace_for_video` (delete + insert); last successful analysis wins — no merge.

## Layout

```
vtuber-karaoke-search/
├── .devcontainer/     # Dev Container (app + Postgres + Flyway)
├── frontend/          # Vite React search UI
├── data_updater/      # FastAPI service (run with cwd = this dir)
├── db/migrations/     # Flyway SQL (schema source of truth; V1 + V2 title index)
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
