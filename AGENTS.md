# AGENTS.md — Setlist

## What this project is

Public-ready homelab service that scrapes VTuber karaoke streams, detects setlist comments (timestamp lists), extracts songs, and exposes them through a minimal HTTP API + search UI. **Phases 0–9 landed** (pipeline, Tier B pacing, search API, extraction quality, React UI, administrator auth, guest limits, public-service pages, deployment hardening, bilingual public documentation, and updater crash safety/observability).

Stack: **FastAPI + SQLAlchemy 2 (async) + PostgreSQL + yt-dlp + Flyway** (backend); **React (Vite + TypeScript 6) + TanStack Router/Query + Zustand + Paraglide + Tailwind + shadcn/ui** (frontend).

## Layout

```
setlist/
├── frontend/              # Vite React search UI (run cwd = this dir)
│   ├── src/routes/        # TanStack Router pages (search, song, browse)
│   ├── src/api/           # Typed fetch client + Query hooks
│   ├── src/stores/        # Zustand UI prefs (locale, theme, recent searches)
│   ├── messages/          # Paraglide en + zh-hant + ja
│   └── README.md          # Frontend run / proxy notes
├── backend/               # FastAPI service (run cwd = this dir)
│   ├── main.py            # App + background periodic updater
│   ├── config.py          # Env via python-dotenv
│   ├── deps.py            # Shared FastAPI deps (session, pagination)
│   ├── db/                # Engine + sqlacodegen ORM models
│   ├── models/            # Pydantic DTOs (auth / Channel / Video / Song / search)
│   ├── repositories/      # DB access (reads + upserts; updater commits)
│   ├── routers/v1/        # HTTP API (auth, health, search, reports, admin operations)
│   ├── utils/             # Small helpers (YouTube timestamp deep links)
│   ├── services/
│   │   ├── data_updater.py
│   │   ├── auth.py        # Single-admin signed sessions
│   │   ├── rate_limit.py  # Guest/login limits + trusted-proxy client IPs
│   │   ├── analyzer/      # Comment → song-list heuristics
│   │   └── yt_scraper/    # yt-dlp wrappers + ad-hoc test.py
│   └── tests/             # pytest unit + PostgreSQL integration coverage
├── db/
│   ├── migrations/        # Flyway SQL (V1–V10; schema source of truth)
│   └── devscript/         # PowerShell one-shot Postgres + sqlacodegen
├── .devcontainer/         # Dev Container image/config (Python 3.14 + Node 26)
├── scripts/               # Repository checks, including credential scanning
├── docker-compose.yml     # Production frontend + API + Postgres + Flyway
└── docker-compose.dev.yml # Dev Container workspace + Postgres + Flyway
```

## How to run

### Dev Container (preferred)

1. Open the repo in Cursor/VS Code → **Reopen in Container**.
2. Compose starts `db` (Postgres 18), runs Flyway migrations, then attaches to `app`.
3. Python deps are baked into the image; `postCreateCommand` runs `npm ci` into
   a container-only `node_modules` volume.
4. `postStartCommand` automatically starts FastAPI and Vite with hot reload.
5. Health: `GET /v1/health` (port 8000 forwarded); UI:
   `http://localhost:5173`. Inside the container, DB host is `db`.
6. OpenAPI is available at `/docs` in `APP_ENV=dev`.
7. Background scraping is opt-in in dev. `docker-compose.dev.yml` sets
   `BACKGROUND_UPDATER_ENABLED=false`; enable it only intentionally.
8. Administrator features require a development `.env` with an Argon2id hash
   and session secret. Authentication is never bypassed by `APP_ENV=dev`.

### Local (without Dev Container)

1. Start Postgres + migrate (Windows scripts under `db/devscript/`, or):
   ```bash
   docker compose -f docker-compose.dev.yml up -d db flyway
   ```
2. Optional: regenerate ORM with `db/devscript/sqlacodegen.ps1` (overwrites `backend/db/models.py`)
3. From `backend/`:
   ```bash
   pip install -r requirements-dev.txt
   # APP_ENV=dev enables docs and local CORS origins; admin auth still applies
   APP_ENV=dev BACKGROUND_UPDATER_ENABLED=false uvicorn main:app --host 0.0.0.0 --port 8000
   ```
4. From `frontend/`:
   ```bash
   npm ci && npm run dev
   ```
5. Health: `GET /v1/health` · UI: http://localhost:5173.
6. To test administrator features, configure `ADMIN_PASSWORD_HASH` and
   `SESSION_SECRET`; otherwise login fails closed and guest features still work.

Default DB (also in `config.py`): `vks_db_user` / `vks_db_pwd` @ `localhost:5432/vks_db` (use host `db` in Compose). Override with `DATABASE_URL` or `DB_*` env vars. Never commit `.env`.

## Architecture notes agents must respect

- **Schema source of truth** is Flyway SQL in `db/migrations/`. ORM models in `backend/db/models.py` are generated — prefer editing SQL + regenerating over hand-editing generated models unless necessary.
- **Pydantic models** (`backend/models/`) are the API/domain DTOs; repositories map ORM → Pydantic with `model_validate` / `from_attributes`.
- **Imports assume cwd = `backend/`** (e.g. `from config import ...`). Do not introduce package-relative imports without making it a proper installable package.
- **Frontend** lives under `frontend/` with its own cwd; do not mix Python package imports into the UI tree.
- **yt-dlp scrapers are synchronous and blocking.** Production application paths use the killable subprocess runner with bounded network retries and a whole-operation timeout; test doubles may use `asyncio.to_thread`. Do not block the event loop or bypass the shared YouTube operation lock.
- **Background updater** lives in `main.py` lifespan and calls `DataUpdater.update()` every `DATA_UPDATE_INTERVAL` (default 5m in every environment). Scraping is opt-in in config; production Compose explicitly enables it. Persisted per-channel due times enforce the 6h steady scan interval. Use `python run_updater_once.py` to test the identical path locally.
- **Repositories do not commit.** `DataUpdater` owns transactions: each backfill page/cursor and each analysis result is durable, with a final channel commit. Read-only search routes open a session via `deps.get_session` and do not commit.
- **Song setlist writes** use `SongRepository.replace_for_video` (delete all songs for that video, then insert) so successful re-analysis can shrink the list cleanly. **Conflict policy:** last successful analysis wins (no merge); a later negative observation preserves the previous successful setlist/songs. Within one extract, duplicates keyed by `(timestamp, casefold(title))` are dropped (first kept).
- **Video list upserts** only refresh metadata columns; analysis fields are updated via `VideoRepository.update_analysis` (includes optional LLM cleaning columns when used). Preserve all normal archives, including `type=other`, so future rules can reclassify them without another historical scrape.
- **Flat video-list dates** use yt-dlp's `youtubetab:approximate_date` from the same tab response. Persist `upload_date_precision`; exact full metadata may upgrade approximate dates, while later flat scrapes must never downgrade an exact date. Comment scraping reuses metadata already returned by its existing request.
- **yt-dlp source snapshots** separate flat-list `raw_data` from full-video `metadata_raw_data`, with source/capture/schema metadata. Use `utils.ytdlp_snapshot`; its bounded stable-field policy excludes volatile playback formats, signed URLs, headers, captions/subtitles, and comments (stored separately). Do not shallow-merge sparse and rich source payloads.
- **New-channel video backfill** is cursor-based and paced (100 entries/tab/page, up to 3 durable pages/cycle by default). Failed/partial tab pages keep the same offset and retry; active channels rotate by oldest attempt time so one channel cannot starve the rest. Comment analysis is a separate global queue.
- **Search deep links** use `utils.youtube_timestamp.youtube_url_with_timestamp` (`mm:ss` / `hh:mm:ss` → `&t=Ns`).
- **Updater status** combines process-local detail with the persisted cycle outcome, owner, last success, and heartbeat at `GET /v1/updater/status`. YouTube cooldown and runtime state live in the singleton `scraper_state` row. Heartbeat writes use independent transactions and must never commit scraper work. Keep public error text redacted and detailed exceptions in server logs.
- **YouTube work is a cross-process singleton.** Keep the process-local lock plus the dedicated-connection PostgreSQL advisory lock around background and administrator-triggered scraping. Owner-guard persistent state updates so a stale process cannot overwrite the current worker.
- **Authorization** uses one environment-configured administrator (`ADMIN_PASSWORD_HASH` is Argon2id; never store plaintext credentials). Signed HttpOnly sessions protect private reads, and all mutations require both admin auth and the per-session CSRF token. `MANAGEMENT_API_ENABLED` is only a kill switch, never an auth substitute.
- **Guest API traffic** is rate-limited per resolved client IP in-process. Only honor `X-Forwarded-For` from `TRUSTED_PROXY_CIDRS`. Updater status is admin-only; guests may search and browse public records.
- **Authentication responses** and authenticated API responses must remain
  `Cache-Control: no-store`; session-bearing responses vary on `Cookie`.
- **Production topology** exposes only the bundled frontend nginx proxy. Keep
  the loopback bind when the TLS proxy is on the same host; when the proxy is on
  another machine, bind only the private LAN interface and firewall it to that
  proxy. The frontend serves the SPA and proxies `/v1`; FastAPI and Postgres
  stay internal. Keep this same-origin topology unless there is a documented
  reason to introduce credentialed CORS.
- **Setlist comment choice** prefers pinned, then uploader, then more parsed
  songs, then likes (`CommentAnalyzer`). Explicit setlist sections stop at
  unrelated chapters/announcements or large timestamp regressions while
  preserving encore sections.
- **Optional LLM cleaning** is behind `LLM_CLEANING_ENABLED` (default off); uses schema columns `cleaning_attempts`, `cleaned_song_list_comment`, `analyzed_by_llm`. Regex extract remains primary.
- **Frontend server cache** = TanStack Query; Zustand is for UI prefs only (locale, recent searches).

## Intended data pipeline

1. Channels in DB → scrape channel metadata / videos (yt-dlp) — **wired in `DataUpdater`**
2. Per video → fetch top comments → `CommentAnalyzer` finds timestamp-heavy “song list” comments — **wired**
3. Extract songs → persist; optional LLM cleaning of setlist text is gated by `LLM_CLEANING_ENABLED` and writes `cleaning_*` / `cleaned_song_list_comment` / `analyzed_by_llm`
4. Search API — **wired** (`/v1/songs/search`, song/channel/video list endpoints)
5. Search UI — **wired** (`frontend/` — search, song detail, channel/video browse, en/zh-hant/ja)
6. Public-service controls — **wired** (single-admin auth, CSRF, guest/login
   limits, private status/admin mutations, legal/privacy pages)

Seed channels: `db/devscript/seed_channels.sql` (see README).

## Conventions

- Prefer small, focused modules matching existing folders (`repositories/`, `services/`, `routers/v1/`).
- New HTTP routes go under `routers/v1/` and are registered in `routers/v1/__init__.py`.
- Keep yt-dlp rate limiting (`sleep_interval` / `max_sleep_interval`) when scraping; YouTube blocks aggressive clients.
- **Phase 2 Tier B (required):** cycle scrape caps, inter-scrape jitter, skip/retry via `analyze_attempts`, block detection → abort remaining YouTube calls + cooldown. No proxies/cookies unless Tier B still fails.
- Application code uses `logging`. Reserve `print` for interactive command-line
  helpers and the manual live scraper smoke script.
- Keep TypeScript on the latest compatible 6.x release. Dependabot intentionally
  ignores the TypeScript 7 semver-major update until Vite, TanStack, and the
  generated-code toolchain have been explicitly compatibility-tested.
- Mixed ZH/EN comments exist; match the file you edit. Prefer English for new public docs/API strings.
- Record reusable design, release, debugging, and operational findings in the
  closest public project document. Use `docs/<topic>.md` when a topic needs a
  standalone checklist, and keep significant English and Traditional Chinese
  public guidance synchronized.
- Keep public project documentation free of secrets, private hostnames and IP
  addresses, credentials, user-specific filesystem paths, and private
  deployment topology. Those details belong only in ignored local context.
- Frontend build-time scripts invoked by `frontend/package.json` must be inside
  `frontend/` unless `frontend/Dockerfile` explicitly copies them. Validate
  frontend changes both directly and through the production Docker build
  context.

## Do not

- Do not expose Postgres publicly; default credentials are for local Docker only.
- Do not add CORS `allow_origins=["*"]` with `allow_credentials=True` in any environment. Credentialed browser access always uses explicit `CORS_ORIGINS`.
- Do not commit administrator hashes, signing keys, production database passwords, `.env` files, or other deployment secrets. Sample configuration must use empty values/placeholders.
- Do not remove the MIT copyright/license notice or required third-party
  notices when redistributing code or assets.
- Do not expose updater status, scraper controls, or mutations to guests.
- Do not trust forwarding headers from arbitrary peers or convert the in-memory
  limiter into a claimed multi-replica security control.
- Do not treat `services/yt_scraper/test.py` as a real test suite; it performs
  live YouTube smoke checks and is intentionally outside pytest/CI.
- Do not add public registration or another role without first defining its
  authorization, persistence, privacy, and migration model.
- Do not rewrite the whole stack (Poetry/uv, Alembic vs Flyway, etc.) unless requested; incremental completion of the pipeline is more valuable.

## Known gaps (as of last review)

- Phases 0–9 are done (pipeline, Tier B pacing, search API/UI, extraction
  quality, single-admin auth, guest limits, public pages, production hardening,
  bilingual public documentation, and updater crash safety/observability).
- Auth intentionally supports one environment-configured administrator only;
  there is no registration, password recovery, OAuth, or multi-user model.
- Rate limits and sessions are self-contained for a single API process. A
  multi-replica deployment needs shared or gateway rate limiting.
- Tune Tier B caps/cooldown if YouTube still limits you (Tier C proxies/cookies only if needed).
- LLM cleaning is optional and off by default; enable only with a real `LLM_API_KEY` if regex quality is still weak.
- Project-authored code is MIT licensed. Third-party packages, fonts, linked
  media, service APIs, and extracted metadata retain their own terms.

Track design status in [PLAN.md](PLAN.md) and GitHub issues. Public setup is in
[README.md](README.md) and [README.zh-Hant.md](README.zh-Hant.md); contribution
and private vulnerability reporting rules are in
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
