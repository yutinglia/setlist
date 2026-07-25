# TODO

Checklist aligned with [PLAN.md](PLAN.md). Check items off as they land.

## Done recently

- [x] Direct-dependency `requirements.txt` (FastAPI 0.139, yt-dlp 2026.7, sqlacodegen 4, …)
- [x] Dev Container (Python 3.12 + Postgres 18 + Flyway)
- [x] Keep development and production Compose stacks separate
- [x] `AGENTS.md` / `PLAN.md` / README / NOTE refresh
- [x] `.env.example` + env-configurable `DATA_UPDATE_INTERVAL`
- [x] `CommentAnalyzer` always sets `video_id`; parsing hardened; unit tests
- [x] Repository upserts / `replace_for_video`; updater-owned commits; `async_sessionmaker`
- [x] Phase 2: `DataUpdater` pipeline + Tier B pacing + seed channels
- [x] Phase 3: CORS, health DB ping, `.gitignore`, production `data_updater` image/service
- [x] Phase 4: search API + title trigram index + pagination
- [x] Phase 5: pinned/uploader preference, more line formats, dedupe, optional LLM cleaning
- [x] Phase 6: search UI (`frontend/` — Vite React, TanStack, Paraglide, Tailwind, shadcn)

## Phase 0 — Docs & local run

- [x] Fill `README.md`
- [x] Add `.env.example`
- [x] Make `DATA_UPDATE_INTERVAL` configurable via env (`config.py`)
- [x] Document Docker / Dev Container run path (Linux-friendly)

## Phase 1 — Domain fixes & write path

- [x] Pass `video_id` into `CommentAnalyzer` / extracted `Song`s
- [x] Harden timestamp/title parsing slightly
- [x] Unit tests for `CommentAnalyzer`
- [x] Repository upserts (`Channel` / `Video` / `Song`)
- [x] Updater-owned commits; prefer `async_sessionmaker`

## Phase 2 — Wire `DataUpdater`

- [x] Channel → videos → comments → analyze → persist
- [x] `asyncio.to_thread` for all yt-dlp calls
- [x] Skip / retry policy via `analyze_attempts` / `last_analyzed_at`
- [x] Cap scrapes per cycle (`UPDATE_MAX_COMMENT_SCRAPES`, `UPDATE_MAX_VIDEOS`)
- [x] Inter-scrape jitter sleep between comment scrapes
- [x] Block detection → abort remaining YouTube work this cycle + cooldown
- [x] Structured logging (replace `print` in touched files)
- [x] Seed 1–2 karaoke channels for manual testing

## Phase 3 — Hardening & ops

- [x] Compose: postgres + flyway + app workspace (Dev Container)
- [x] Production-oriented `data_updater` image / service (`data_updater/Dockerfile` + Compose `data_updater`)
- [x] Tighten CORS outside `APP_ENV=dev` (`CORS_ORIGINS`)
- [x] Gate `/v1/example` to `APP_ENV=dev`
- [x] Health check pings DB
- [x] Document yt-dlp bump process (`data_updater/NOTE.md`)
- [x] Expand root `.gitignore` (`.env`, `__pycache__`, …)

## Phase 4 — Search API

- [x] `GET /v1/songs/search?q=`
- [x] Song / channel / video list endpoints
- [x] Timestamp → YouTube `&t=` helper
- [x] Title index migration (`V2__...`)
- [x] Pagination

## Phase 5 — Extraction quality (optional)

- [x] Prefer pinned / uploader comments
- [x] More line formats
- [x] Optional LLM cleaning (schema columns already exist; `LLM_CLEANING_ENABLED`)
- [x] Dedupe / re-analysis policy (`replace_for_video` last-write-wins)

## Phase 6 — Search UI

- [x] `frontend/` Vite + React + TypeScript
- [x] TanStack Router / Query, Zustand UI prefs, Paraglide `en` + `zh-hant`
- [x] Tailwind + shadcn/ui (input, button, skeleton)
- [x] Search + song detail + channel/video browse
- [x] Debounced search, loading/empty/error, pagination
- [x] Dev proxy / `VITE_API_BASE_URL` + docs

## Out of scope for now

- Auth / multi-user / public hardening
- Alembic or Poetry/uv rewrite
- Celery/RQ (unless scrape volume demands it)
- Tier C YouTube proxies/cookies (only if Tier B still fails)
- CI
