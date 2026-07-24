# vtuber-karaoke-search

Scrape VTuber karaoke streams, detect setlist comments (timestamp lists), store songs, and search them via a minimal HTTP API.

**Status:** Phase 4 search API is in place (`GET /v1/songs/search`, song/channel/video lists, title trigram index, pagination). Updater pipeline is wired with Tier B YouTube pacing. No UI yet (Phase 6). See [PLAN.md](PLAN.md) and [TODO.md](TODO.md).

## Stack

- **FastAPI** (`data_updater/`) — API + background data updater
- **PostgreSQL 18** + **Flyway** migrations (`db/migrations/`)
- **yt-dlp** — channel / video / comment scraping
- **SQLAlchemy 2** (async) + **sqlacodegen** for ORM models

## Quick start (Dev Container)

1. Open this repo in Cursor or VS Code.
2. **Dev Containers: Reopen in Container**.
3. Compose starts Postgres, runs Flyway, installs Python deps.
4. Run the API:

```bash
cd data_updater
uvicorn main:app --host 0.0.0.0 --port 8000
```

| URL | Purpose |
|-----|---------|
| http://localhost:8000/v1/health | Health check |
| http://localhost:8000/v1/songs/search?q=... | Search songs by title |
| http://localhost:8000/docs | OpenAPI (when `APP_ENV=dev`) |

More detail: [.devcontainer/README.md](.devcontainer/README.md).

## Quick start (local Docker)

```bash
# Postgres + migrations
docker compose -f .devcontainer/docker-compose.yml up -d db flyway

# Python deps (3.12 recommended)
cd data_updater
pip install -r requirements.txt
APP_ENV=dev uvicorn main:app --host 0.0.0.0 --port 8000
```

Or run the production-oriented API container (uvicorn + background updater):

```bash
docker compose up --build data_updater
# Health: http://localhost:8000/v1/health  (includes DB ping)
```

Without Compose, Windows one-shot DB scripts live under `db/devscript/`.

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

## Seed karaoke channels

After Postgres + Flyway are up, insert the sample channels (Suisei + Marine):

```bash
psql "postgresql://vks_db_user:vks_db_pwd@localhost:5432/vks_db" \
  -f db/devscript/seed_channels.sql
```

Or via Compose:

```bash
docker compose -f .devcontainer/docker-compose.yml exec -T db \
  psql -U vks_db_user -d vks_db < db/devscript/seed_channels.sql
```

Then start the API from `data_updater/` (prefer `DATA_UPDATE_INTERVAL=1800`). One cycle scrapes recent videos, analyzes up to `UPDATE_MAX_COMMENT_SCRAPES` of them, and writes songs when a setlist comment is found. Logs show caps, jitter, and cooldown. After songs exist, try `GET /v1/songs/search?q=...`.

### Tests

From `data_updater/`:

```bash
pip install -r requirements.txt
pytest
```

Analyzer and timestamp-helper unit tests always run. Repository write smoke tests skip if Postgres is unreachable.

## Layout

```
vtuber-karaoke-search/
├── .devcontainer/     # Dev Container (app + Postgres + Flyway)
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
- [data_updater/NOTE.md](data_updater/NOTE.md) — yt-dlp payload shape notes
