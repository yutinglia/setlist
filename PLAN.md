# Plan: Finish vtuber-karaoke-search

## Goal

Turn the current scaffold into a working **data pipeline** that scrapes VTuber karaoke streams, detects setlist comments, stores songs, then add a minimal **search API**. Do not build a UI until search returns real data.

## Current state (baseline)

| Area | Status |
|------|--------|
| Postgres schema (Flyway V1 + V2 title index) | Done |
| yt-dlp scrapers (channel / videos / comments) | Done, used by DataUpdater |
| Comment → song-list heuristics | Done (`video_id` required; unit tests) |
| Repositories | Read + upsert / `replace_for_video` (updater-owned commits) |
| `DataUpdater.update()` | Wired (scrape → analyze → persist) + Tier B pacing |
| Search / UI | Search API + Phase 5 extraction + Phase 6 search UI MVP |

| Requirements (`data_updater/requirements.txt`) | Direct deps updated (Jul 2026) |
| Dev Container + Compose (Postgres + Flyway) | Done |
| README / AGENTS / TODO docs | Done (keep in sync when behavior changes) |
| `.env.example` + `DATA_UPDATE_INTERVAL` env | Done |

## Principles

1. **Pipeline first, search second, UI last.**
2. Prefer completing existing modules over rewrites (keep FastAPI + Flyway + yt-dlp + sqlacodegen).
3. One channel end-to-end before scaling to many channels / LLM cleaning.
4. Scraping must not block the FastAPI event loop; respect yt-dlp sleep intervals.

---

## Phase 0 — Docs & local run (½ day)

**Why:** Agents and future-you can actually start the stack.

- [x] Fill `README.md`: what it is, how to run Postgres + migrate, how to run `data_updater`, env vars.
- [x] Add `.env.example` (`APP_ENV`, `DB_*` / `DATABASE_URL`, optional updater interval).
- [x] Make `DATA_UPDATE_INTERVAL` configurable via env (remove hardcoded TODO in `config.py`).
- [x] Document Docker / Dev Container run path (covers Linux; PowerShell scripts remain under `db/devscript/`).

**Exit:** Fresh clone → DB up → `GET /v1/health` works.

---

## Phase 1 — Domain fixes & write path (1 day)

**Why:** Analyzer and repos cannot persist anything correctly today.

### 1a. Fix domain models / analyzer

- [x] Make `Song.video_id` optional at construction time **or** pass `video_id` into `CommentAnalyzer` / `extract_song_list(video_id=...)`.
- [x] Prefer: analyzer takes `video_id` and always sets it on extracted songs.
- [x] Harden parsing slightly: strip separators both sides of timestamp; skip empty titles; keep `minimum_timestamp_count` configurable.
- [x] Add a few unit tests for `CommentAnalyzer` (pinned-style multiline comment, no timestamps, too few timestamps, title-before/after timestamp if you support both).

### 1b. Repository writes

Add to each repository (or a shared base):

- [x] `ChannelRepository.upsert(channel)` 
- [x] `VideoRepository.upsert(video)` / `upsert_many`
- [x] `SongRepository.replace_for_video(video_id, songs)` (delete+insert or upsert by `(video_id, timestamp, title)` — pick one and document it)
- [x] Explicit `session.commit()` / rollback ownership: either repositories commit, or `DataUpdater` commits once per channel — **choose updater-owned commits**.

### 1c. Session hygiene

- [x] Prefer `async_sessionmaker` over `sessionmaker(..., class_=AsyncSession)`.
- [x] Ensure one session per update cycle (already roughly true in `main.py`); commit/rollback inside `DataUpdater`.

**Exit:** Can insert a fake channel/video/songs in a script or test and read them back.

---

## Phase 2 — Wire `DataUpdater` end-to-end (2–3 days)

**Why:** This is the product’s core loop.

### Pipeline per cycle

```
for channel in DB channels:
  1. (optional) refresh channel metadata via YouTubeChannelScraper
  2. scrape video list via YouTubeChannelVideoScraper
  3. upsert videos (skip shorts/live already filtered)
  for video in videos needing work (respect caps + cooldown):
     - skip if has_song_list_comment and songs exist (or if analyze_attempts >= N)
     - scrape top comments (yt-dlp via asyncio.to_thread)
     - on suspected YouTube block → abort remaining scrapes this cycle + set cooldown
     - else CommentAnalyzer → detect + extract
     - update video analysis fields + persist songs
     - sleep jitter between comment scrapes
  commit per channel (or per video if safer)
```

### YouTube access-limit avoidance (Tier B) — required in this phase

Do **not** rely only on yt-dlp `sleep_interval`. Implement updater-level pacing + block handling:

| Control | Default (env-tunable) | Behavior |
|---------|----------------------|----------|
| Comment scrapes per cycle | `UPDATE_MAX_COMMENT_SCRAPES=5` | Hard stop after N videos scraped for comments |
| Videos upserted / considered per cycle | `UPDATE_MAX_VIDEOS=20` | Prefer recent uploads first |
| Inter-scrape jitter | `UPDATE_SCRAPE_SLEEP_MIN/MAX` (e.g. 3–8s) | `asyncio.sleep(random)` **between** comment scrapes |
| Skip / retry | `analyze_attempts >= 3` | Skip successful extracts; stop retrying exhausted videos |
| yt-dlp sleeps (comments) | raise to ~2–5s / max ~10s | Keep existing opts; make configurable |
| Block detection | — | Treat as block: yt-dlp bot/HTTP errors, or comments unexpectedly empty when other signals suggest failure |
| Cycle abort on block | — | Stop further YouTube calls this cycle; bump attempts / set `last_analyzed_at` on the failing video |
| Cooldown | `UPDATE_YOUTUBE_COOLDOWN_SECONDS` (e.g. 3600) | After a block, skip all YouTube work until cooldown expires (in-memory flag OK for v1; optional DB/env later) |

**Out of scope for Phase 2:** proxies, multi-account rotation, cookies (Tier C — only if Tier B still gets limited).

**Dev note:** do not run with `DATA_UPDATE_INTERVAL=10` while scraping is enabled; use a safer interval or disable the background loop when testing scrapers manually.

### Implementation checklist

- [x] Offload all yt-dlp calls with `asyncio.to_thread(...)`.
- [x] Define “needs analysis” query (e.g. `analyze_attempts < 3` AND not yet successfully extracted, or `last_analyzed_at` older than X).
- [x] Cap work per cycle (`UPDATE_MAX_COMMENT_SCRAPES`, `UPDATE_MAX_VIDEOS`).
- [x] Inter-scrape jitter sleep between comment scrapes.
- [x] Block detection + abort remaining YouTube work for the cycle + cooldown before next YouTube work.
- [x] Increment `analyze_attempts`, set `last_analyzed_at`, `has_song_list_comment`, store raw comment JSON when found.
- [x] Structured logging (`logging` module) instead of `print` in touched files.
- [x] Per-channel / per-video try/except so one non-block failure does not abort the whole cycle (keep loop in `main.py`); blocks *do* abort remaining scrapes by design.

### Seed data

- [x] Small SQL or admin path to insert 1–2 known karaoke channels for manual testing (document in README).

**Exit:** With one seeded channel, after one updater cycle, `songs` table has rows and timestamps look sane. Caps/cooldown can be verified by logs (no unbounded scrape storms).

---

## Phase 3 — Hardening & ops (1–2 days)

**Why:** Safe to leave running overnight.

- [x] Compose: `postgres` + `flyway` + app workspace (`.devcontainer/`; root compose includes it).
- [x] Dev Container Dockerfile (Python 3.12). Production `data_updater` image + Compose service (`docker compose up --build data_updater`); IDE `app` stays `sleep infinity`.
- [x] Fix CORS: explicit origins in prod (`CORS_ORIGINS`); keep loose only when `APP_ENV=dev`.
- [x] Gate `example` router to `APP_ENV=dev`; keep `/v1/health`.
- [x] Health check pings DB (`SELECT 1`; 503 if unavailable).
- [x] yt-dlp bump notes in `data_updater/NOTE.md` (keep pin in `requirements.txt` after upgrades).
- [x] Root `.gitignore`: `.env`, `__pycache__`, venvs, caches, etc.

**Exit:** `docker compose up --build data_updater` brings API + DB; updater runs without blocking health checks.

---

## Phase 4 — Minimal search API (1–2 days)

**Why:** Delivers the project name without a frontend yet.

### Endpoints (v1)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/songs/search?q=` | ILIKE / full-text on `songs.title` |
| GET | `/v1/songs/{id}` | Song detail + video URL + timestamp |
| GET | `/v1/channels` | List tracked channels |
| GET | `/v1/channels/{id}/videos` | Videos for a channel |
| GET | `/v1/videos/{id}/songs` | Songs for a video |

### Response shape (example)

```json
{
  "title": "曲名",
  "timestamp": "12:34",
  "video_id": "...",
  "video_url": "https://www.youtube.com/watch?v=...&t=754s",
  "channel_id": "...",
  "channel_name": "..."
}
```

- [x] Convert `mm:ss` / `hh:mm:ss` → YouTube `&t=` seconds helper.
- [x] Add DB index on `songs.title` (trigram or simple `LOWER(title)` btree) via Flyway `V2__...sql`, then regenerate ORM if needed.
- [x] Pagination (`limit`/`offset` or cursor).

**Exit:** Querying a known song title returns a clickable deep link.

---

## Phase 5 — Quality of extraction (optional, after search works)

Defer LLM until regex path is useful.

- [x] Prefer pinned / uploader comments when choosing song list.
- [x] Support more line formats (`01. Title 0:12:00`, `Title - 1:23`, parenthesized timestamps, full-width colons, etc.).
- [x] Optional LLM cleaning using existing schema columns (`cleaning_attempts`, `cleaned_song_list_comment`, `analyzed_by_llm`) — behind `LLM_CLEANING_ENABLED` (default off).
- [x] Dedupe songs within a video; conflict policy if re-analysis changes the list (`replace_for_video` last-write-wins; intra-extract dedupe by `(timestamp, casefold(title))`).

---

## Phase 6 — Search UI (MVP)

- [x] React (Vite + TypeScript) app under `frontend/`
- [x] TanStack Router + TanStack Query + Zustand (UI prefs) + Paraglide (`en` / `zh-hant`) + Tailwind + shadcn/ui
- [x] Search page → `GET /v1/songs/search` with debounce, pagination, deep links
- [x] Song detail + channel → videos → video songs browse
- [x] Dev proxy / `VITE_API_BASE_URL` + CORS notes (`APP_ENV=dev` or `CORS_ORIGINS`)

**Still out of scope:** auth, multi-user, public deploy hardening, Flyway→Alembic / Poetry/uv rewrite, Celery/RQ, Tier C proxies/cookies.

---

## Suggested order of PRs / commits

1. Phase 0 — finish `.env.example` + env-configurable interval (docs/compose mostly done)  
2. Phase 1 — analyzer fix + write repos + tests  
3. Phase 2 — `DataUpdater` pipeline + seed channel  
4. Phase 3 — CORS/logging + production API image + `.gitignore` ✅  
5. Phase 4 — search endpoints + title index ✅  
6. Phase 5 — extraction improvements / optional LLM ✅  
7. Phase 6 — search UI MVP ✅

---

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| YouTube / yt-dlp breakage | Pin version; rate-limit; `ignoreerrors`; cap scrapes per cycle |
| YouTube access / bot limits | Tier B: cycle caps, inter-scrape jitter, skip/retry, block detect → abort cycle + cooldown (no proxies/cookies yet) |
| Event loop blocked | Always `asyncio.to_thread` for yt-dlp |
| Duplicate / stale songs | `replace_for_video` or unique constraint; track `last_analyzed_at` |
| Long first sync | Work caps + prioritize recent uploads |
| Schema drift (sqlacodegen) | Migrations first; regenerate models; don’t hand-edit generated files lightly |

---

## Success criteria

1. Seeded channel → automatic songs in DB within one update cycle.  
2. `GET /v1/songs/search?q=...` returns results with timestamp deep links.  
3. `docker compose up` (or documented manual path) is reproducible on a clean machine.  
4. Updater failures are logged and do not crash the API process.  
5. Search UI can query the API and open YouTube deep links (Phase 6).
