# AGENTS.md — vtuber-karaoke-search

## What this project is

Personal experiment to scrape VTuber karaoke streams, detect setlist comments (timestamp lists), extract songs, and search them via a minimal HTTP API. **Data-updater + search API exist; there is no UI yet.**

Stack: **FastAPI + SQLAlchemy 2 (async) + PostgreSQL + yt-dlp + Flyway**.

## Layout

```
vtuber-karaoke-search/
├── data_updater/          # FastAPI service (run cwd = this dir)
│   ├── main.py            # App + background periodic updater
│   ├── config.py          # Env via python-dotenv
│   ├── deps.py            # Shared FastAPI deps (session, pagination)
│   ├── db/                # Engine + sqlacodegen ORM models
│   ├── models/            # Pydantic DTOs (Channel / Video / Song / search)
│   ├── repositories/      # DB access (reads + upserts; updater commits)
│   ├── routers/v1/        # HTTP API (health, search, lists; example gated to APP_ENV=dev)
│   ├── utils/             # Small helpers (YouTube timestamp deep links)
│   ├── services/
│   │   ├── data_updater.py
│   │   ├── analyzer/      # Comment → song-list heuristics
│   │   └── yt_scraper/    # yt-dlp wrappers + ad-hoc test.py
│   └── tests/             # pytest (analyzer, timestamp helper; optional DB write smoke)
├── db/
│   ├── migrations/        # Flyway SQL (V1__*.sql, V2 title index)
│   └── devscript/         # PowerShell one-shot Postgres + sqlacodegen
├── .devcontainer/         # Dev Container (Python 3.12 + Postgres + Flyway)
├── docker-compose.yml     # Includes .devcontainer/docker-compose.yml
└── docker-compose.dev.yml # Same include (alias)
```

## How to run

### Dev Container (preferred)

1. Open the repo in Cursor/VS Code → **Reopen in Container**.
2. Compose starts `db` (Postgres 18), runs Flyway migrations, then attaches to `app`.
3. Deps install via `postCreateCommand` (`pip install -r data_updater/requirements.txt`).
4. From `data_updater/`:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
5. Health: `GET /v1/health` (port 8000 forwarded). Inside the container, DB host is `db` (not `localhost`).
6. Search (example): `GET /v1/songs/search?q=Stellar` — OpenAPI at `/docs` when `APP_ENV=dev`.

### Local (without Dev Container)

1. Start Postgres + migrate (Windows scripts under `db/devscript/`, or):
   ```bash
   docker compose -f .devcontainer/docker-compose.yml up -d db flyway
   ```
2. Optional: regenerate ORM with `db/devscript/sqlacodegen.ps1` (overwrites `data_updater/db/models.py`)
3. From `data_updater/`:
   ```bash
   pip install -r requirements.txt
   # APP_ENV=dev for docs + short update interval
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
4. Health: `GET /v1/health`

Default DB (also in `config.py`): `vks_db_user` / `vks_db_pwd` @ `localhost:5432/vks_db` (use host `db` in Compose). Override with `DATABASE_URL` or `DB_*` env vars. Never commit `.env`.

## Architecture notes agents must respect

- **Schema source of truth** is Flyway SQL in `db/migrations/`. ORM models in `data_updater/db/models.py` are generated — prefer editing SQL + regenerating over hand-editing generated models unless necessary.
- **Pydantic models** (`data_updater/models/`) are the API/domain DTOs; repositories map ORM → Pydantic with `model_validate` / `from_attributes`.
- **Imports assume cwd = `data_updater/`** (e.g. `from config import ...`). Do not introduce package-relative imports without making it a proper installable package.
- **yt-dlp scrapers are synchronous and blocking.** If calling them from async FastAPI code, wrap with `asyncio.to_thread` (or similar). Do not block the event loop.
- **Background updater** lives in `main.py` lifespan and calls `DataUpdater.update()` on an interval (`DATA_UPDATE_INTERVAL`; default 10s in `APP_ENV=dev`, else 30m; override via env). Keep long scraping work isolated and resilient (one failure should not kill the loop).
- **Repositories do not commit.** `DataUpdater` owns `session.commit()` / `rollback()` (commit per channel in Phase 2). Read-only search routes open a session via `deps.get_session` and do not commit.
- **Song setlist writes** use `SongRepository.replace_for_video` (delete all songs for that video, then insert) so re-analysis can shrink the list cleanly.
- **Video list upserts** only refresh metadata columns; analysis fields are updated via `VideoRepository.update_analysis`.
- **Search deep links** use `utils.youtube_timestamp.youtube_url_with_timestamp` (`mm:ss` / `hh:mm:ss` → `&t=Ns`).

## Intended data pipeline

1. Channels in DB → scrape channel metadata / videos (yt-dlp) — **wired in `DataUpdater`**
2. Per video → fetch top comments → `CommentAnalyzer` finds timestamp-heavy “song list” comments — **wired**
3. Extract songs → persist; schema also reserves LLM cleaning fields (`cleaning_*`, `cleaned_song_list_comment`, `analyzed_by_llm`) that have **no implementation yet**
4. Search API — **wired** (`/v1/songs/search`, song/channel/video list endpoints); UI not present

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
- Do not invent a frontend unless the user asks — search API is enough until Phase 6.
- Do not rewrite the whole stack (Poetry/uv, Alembic vs Flyway, etc.) unless requested; incremental completion of the pipeline is more valuable.

## Known gaps (as of last review)

- Phase 4 search API done (ILIKE title search, deep links, pagination, trigram index).
- No CI or UI yet (Phase 5 optional extraction quality; Phase 6 UI).
- Tune Tier B caps/cooldown if YouTube still limits you (Tier C proxies/cookies only if needed).

Track progress in [TODO.md](TODO.md) / [PLAN.md](PLAN.md).
