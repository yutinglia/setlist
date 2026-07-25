# AGENTS.md — vtuber-karaoke-search

## What this project is

Personal experiment to scrape VTuber karaoke streams, detect setlist comments (timestamp lists), extract songs, and search them via a minimal HTTP API + search UI. **Phases 0–6 MVP landed** (pipeline, Tier B pacing, search API, extraction quality, React search UI).

Stack: **FastAPI + SQLAlchemy 2 (async) + PostgreSQL + yt-dlp + Flyway** (backend); **React (Vite) + TanStack Router/Query + Zustand + Paraglide + Tailwind + shadcn/ui** (frontend).

## Layout

```
vtuber-karaoke-search/
├── frontend/              # Vite React search UI (run cwd = this dir)
│   ├── src/routes/        # TanStack Router pages (search, song, browse)
│   ├── src/api/           # Typed fetch client + Query hooks
│   ├── src/stores/        # Zustand UI prefs (locale, recent searches)
│   ├── messages/          # Paraglide en + zh-hant
│   └── README.md          # Frontend run / proxy notes
├── data_updater/          # FastAPI service (run cwd = this dir)
│   ├── main.py            # App + background periodic updater
│   ├── config.py          # Env via python-dotenv
│   ├── deps.py            # Shared FastAPI deps (session, pagination)
│   ├── db/                # Engine + sqlacodegen ORM models
│   ├── models/            # Pydantic DTOs (Channel / Video / Song / search)
│   ├── repositories/      # DB access (reads + upserts; updater commits)
│   ├── routers/v1/        # HTTP API (health, search, lists; management env-gated)
│   ├── utils/             # Small helpers (YouTube timestamp deep links)
│   ├── services/
│   │   ├── data_updater.py
│   │   ├── analyzer/      # Comment → song-list heuristics
│   │   └── yt_scraper/    # yt-dlp wrappers + ad-hoc test.py
│   └── tests/             # pytest (analyzer, timestamp helper; optional DB write smoke)
├── db/
│   ├── migrations/        # Flyway SQL (V1__*.sql, V2 title index)
│   └── devscript/         # PowerShell one-shot Postgres + sqlacodegen
├── .devcontainer/         # Dev Container image/config (Python 3.12 + Node 22)
├── docker-compose.yml     # Production-oriented API + Postgres + Flyway
└── docker-compose.dev.yml # Dev Container workspace + Postgres + Flyway
```

## How to run

### Dev Container (preferred)

1. Open the repo in Cursor/VS Code → **Reopen in Container**.
2. Compose starts `db` (Postgres 18), runs Flyway migrations, then attaches to `app`.
3. Python deps are baked into the image; `postCreateCommand` runs `npm ci` into
   a container-only `node_modules` volume.
4. From `data_updater/`:
   ```bash
   APP_ENV=dev BACKGROUND_UPDATER_ENABLED=false uvicorn main:app --host 0.0.0.0 --port 8000
   ```
5. Health: `GET /v1/health` (port 8000 forwarded). Inside the container, DB host is `db` (not `localhost`).
6. Search API (example): `GET /v1/songs/search?q=Stellar` — OpenAPI at `/docs` when `APP_ENV=dev`.
7. Background scraping is opt-in in dev: set `BACKGROUND_UPDATER_ENABLED=true`.
8. Search UI (needs Node 20+):
   ```bash
   cd frontend && npm install && npm run dev
   ```
   Open http://localhost:5173 — Vite proxies `/v1` to the API.

### Local (without Dev Container)

1. Start Postgres + migrate (Windows scripts under `db/devscript/`, or):
   ```bash
   docker compose -f docker-compose.dev.yml up -d db flyway
   ```
2. Optional: regenerate ORM with `db/devscript/sqlacodegen.ps1` (overwrites `data_updater/db/models.py`)
3. From `data_updater/`:
   ```bash
   pip install -r requirements-dev.txt
   # APP_ENV=dev enables docs, loose CORS, and trusted management endpoints
   APP_ENV=dev BACKGROUND_UPDATER_ENABLED=false uvicorn main:app --host 0.0.0.0 --port 8000
   ```
4. From `frontend/`:
   ```bash
   npm install && npm run dev
   ```
5. Health: `GET /v1/health` · UI: http://localhost:5173

Default DB (also in `config.py`): `vks_db_user` / `vks_db_pwd` @ `localhost:5432/vks_db` (use host `db` in Compose). Override with `DATABASE_URL` or `DB_*` env vars. Never commit `.env`.

## Architecture notes agents must respect

- **Schema source of truth** is Flyway SQL in `db/migrations/`. ORM models in `data_updater/db/models.py` are generated — prefer editing SQL + regenerating over hand-editing generated models unless necessary.
- **Pydantic models** (`data_updater/models/`) are the API/domain DTOs; repositories map ORM → Pydantic with `model_validate` / `from_attributes`.
- **Imports assume cwd = `data_updater/`** (e.g. `from config import ...`). Do not introduce package-relative imports without making it a proper installable package.
- **Frontend** lives under `frontend/` with its own cwd; do not mix Python package imports into the UI tree.
- **yt-dlp scrapers are synchronous and blocking.** If calling them from async FastAPI code, wrap with `asyncio.to_thread` (or similar). Do not block the event loop.
- **Background updater** lives in `main.py` lifespan and calls `DataUpdater.update()` on an interval (`DATA_UPDATE_INTERVAL`; default 10s in `APP_ENV=dev`, else 30m; override via env). It defaults off in dev and on in prod via `BACKGROUND_UPDATER_ENABLED`. Keep long scraping work isolated and resilient (one failure should not kill the loop).
- **Repositories do not commit.** `DataUpdater` owns `session.commit()` / `rollback()` (commit per channel in Phase 2). Read-only search routes open a session via `deps.get_session` and do not commit.
- **Song setlist writes** use `SongRepository.replace_for_video` (delete all songs for that video, then insert) so re-analysis can shrink the list cleanly. **Conflict policy:** last successful analysis wins (no merge). Within one extract, duplicates keyed by `(timestamp, casefold(title))` are dropped (first kept).
- **Video list upserts** only refresh metadata columns; analysis fields are updated via `VideoRepository.update_analysis` (includes optional LLM cleaning columns when used).
- **New-channel video backfill** is cursor-based and paced. Failed/partial tab pages keep the same offset and retry; active channels rotate by oldest attempt time so one channel cannot starve the rest.
- **Search deep links** use `utils.youtube_timestamp.youtube_url_with_timestamp` (`mm:ss` / `hh:mm:ss` → `&t=Ns`).
- **Updater status** is process-local at `GET /v1/updater/status`; keep public error text redacted and detailed exceptions in server logs.
- **Setlist comment choice** prefers pinned, then uploader, then denser timestamps / likes (`CommentAnalyzer`).
- **Optional LLM cleaning** is behind `LLM_CLEANING_ENABLED` (default off); uses schema columns `cleaning_attempts`, `cleaned_song_list_comment`, `analyzed_by_llm`. Regex extract remains primary.
- **Frontend server cache** = TanStack Query; Zustand is for UI prefs only (locale, recent searches).

## Intended data pipeline

1. Channels in DB → scrape channel metadata / videos (yt-dlp) — **wired in `DataUpdater`**
2. Per video → fetch top comments → `CommentAnalyzer` finds timestamp-heavy “song list” comments — **wired**
3. Extract songs → persist; optional LLM cleaning of setlist text is gated by `LLM_CLEANING_ENABLED` and writes `cleaning_*` / `cleaned_song_list_comment` / `analyzed_by_llm`
4. Search API — **wired** (`/v1/songs/search`, song/channel/video list endpoints)
5. Search UI — **wired** (`frontend/` — search, song detail, channel/video browse, en/zh-hant)

Seed channels: `db/devscript/seed_channels.sql` (see README).

## Conventions

- Prefer small, focused modules matching existing folders (`repositories/`, `services/`, `routers/v1/`).
- New HTTP routes go under `routers/v1/` and are registered in `routers/v1/__init__.py`.
- Keep yt-dlp rate limiting (`sleep_interval` / `max_sleep_interval`) when scraping; YouTube blocks aggressive clients.
- **Phase 2 Tier B (required):** cycle scrape caps, inter-scrape jitter, skip/retry via `analyze_attempts`, block detection → abort remaining YouTube calls + cooldown. No proxies/cookies unless Tier B still fails.
- Use structured logging eventually; today the code uses `print` — when touching a file, prefer `logging` over adding more prints.
- Mixed ZH/EN comments exist; match the file you edit. Prefer English for new public docs/API strings.

## Do not

- Do not expose Postgres publicly; default credentials are for local Docker only.
- Do not add CORS `allow_origins=["*"]` with `allow_credentials=True` outside `APP_ENV=dev`. Prod uses explicit `CORS_ORIGINS`.
- Do not treat `services/yt_scraper/test.py` as a real test suite; it is a manual scratch script with known attribute bugs.
- Do not add auth, admin, or scraper controls to the UI for MVP.
- Do not rewrite the whole stack (Poetry/uv, Alembic vs Flyway, etc.) unless requested; incremental completion of the pipeline is more valuable.

## Known gaps (as of last review)

- Phases 0–6 MVP done (pipeline, Tier B pacing, search API, extraction quality, search UI).
- No auth / multi-user / public deploy hardening. CI covers lint, tests, frontend build, and the production image.
- Tune Tier B caps/cooldown if YouTube still limits you (Tier C proxies/cookies only if needed).
- LLM cleaning is optional and off by default; enable only with a real `LLM_API_KEY` if regex quality is still weak.

Track progress in [TODO.md](TODO.md) / [PLAN.md](PLAN.md).
