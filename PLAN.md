# Implementation plan and current status

## Goal

Operate Setlist as a public-ready, self-hosted VTuber karaoke index: scrape
conservatively, extract timestamped songs, expose a useful search API/UI, and
reserve operational controls for one authenticated administrator.

This file preserves the implementation phases and their design decisions.
Phases 0–10 are complete; future work should be added here only after it enters
scope, with individual work tracked in GitHub issues.

## Current state (baseline)

| Area | Status |
|------|--------|
| Postgres schema (Flyway V1–V14) | Done |
| yt-dlp scrapers (channel / videos / comments) | Done, used by DataUpdater |
| Comment → song-list heuristics | Done (`video_id` required; unit tests) |
| Repositories | Read + upsert / `replace_for_video` (updater-owned commits) |
| `DataUpdater.update()` | Wired + atomic durable work units + cross-process singleton + delayed global analysis queue |
| Search / UI | Public API + trilingual React search/browse UI + shared hero/header title suggestions + contributor credits |
| Access control | Single-admin Argon2id login, signed sessions, CSRF |
| Public service limits | Per-IP guest/login limits; admin-only status/mutations |
| Channel ingest | Admin bulk add (max 10), durable cooldown queue fallback, one coalesced updater wake |
| Deployment | Tag-only release; private scheduled/manual control plane; same-origin frontend proxy; API/Postgres private |

| Requirements (`backend/requirements.txt`) | Direct deps updated (Jul 2026) |
| Frontend compiler | TypeScript 6.x; TypeScript 7 deferred pending toolchain compatibility |
| Dev Container + Compose (Postgres + Flyway) | Done |
| Public documentation | English + Traditional Chinese README, contribution/security policy |
| `.env.example` + `DATA_UPDATE_INTERVAL` env | Done |

## Principles

1. **Pipeline first, search second, UI last.** (Historical implementation
   order; all three now exist.)
2. Prefer completing existing modules over rewrites (keep FastAPI + Flyway + yt-dlp + sqlacodegen).
3. One channel end-to-end before scaling to many channels / LLM cleaning.
4. Scraping must not block the FastAPI event loop; respect yt-dlp sleep intervals.

---

## Phase 0 — Docs & local run (½ day)

**Why:** Agents and future-you can actually start the stack.

- [x] Fill `README.md`: what it is, how to run Postgres + migrate, how to run `backend`, env vars.
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
     - scrape top comments (blocking yt-dlp offloaded from the event loop)
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
| Comment scrapes per cycle | `UPDATE_MAX_COMMENT_SCRAPES=3` | Hard stop after N videos scraped for comments |
| Videos upserted / considered per scan | `UPDATE_MAX_VIDEOS=40` | Prefer recent uploads first |
| Inter-comment jitter | `UPDATE_SCRAPE_SLEEP_MIN/MAX=20/40` | `asyncio.sleep(random)` between comment scrapes |
| Skip / retry | `analyze_attempts >= 3` | Skip successful extracts; stop retrying exhausted videos |
| yt-dlp sleeps (comments) | raise to ~2–5s / max ~10s | Keep existing opts; make configurable |
| Block detection | — | Treat as block: yt-dlp bot/HTTP errors, or comments unexpectedly empty when other signals suggest failure |
| Cycle abort on block | — | Stop further YouTube calls this cycle; bump attempts / set `last_analyzed_at` on the failing video |
| Cooldown | `UPDATE_YOUTUBE_COOLDOWN_SECONDS=21600` | After a block, skip all YouTube work for six hours; blocks do not exhaust video attempts |

**Out of scope for Phase 2:** proxies, multi-account rotation, cookies (Tier C — only if Tier B still gets limited).

**Dev note:** dev/prod use the same defaults. Keep the background updater opt-in
locally and run `python run_updater_once.py` for one production-equivalent cycle.

### Implementation checklist

- [x] Offload all yt-dlp calls; production now uses killable subprocesses and
  unit-test doubles retain a thread fallback.
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
- [x] Dev Container Dockerfile (Python 3.14). Production backend and frontend
  images in the root Compose stack; IDE `app` stays `sleep infinity`.
- [x] Fix credentialed CORS: explicit origins in every environment
  (`APP_ENV=dev` only supplies exact localhost defaults).
- [x] Remove the placeholder example router; keep `/v1/health` and require an
  authenticated administrator for management mutations.
- [x] Health check pings DB (`SELECT 1`; 503 if unavailable).
- [x] yt-dlp bump notes in `backend/NOTE.md` (keep pin in `requirements.txt` after upgrades).
- [x] Root `.gitignore`: `.env`, `__pycache__`, venvs, caches, etc.

**Exit:** With required production secrets configured, `docker compose up
--build` brings up the same-origin frontend proxy, API, DB, and Flyway; updater
work does not block health checks.

---

## Phase 4 — Minimal search API (1–2 days)

**Why:** Establish the public data contract before building the frontend.

### Endpoints (v1)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/songs/search?q=` | ILIKE on `songs.title`; optional `channel_id`, `type`, `upload_date_from` / `upload_date_to` |
| GET | `/v1/songs/suggestions?q=` | Lightweight distinct title suggestions with exact/prefix/frequency ranking and the same optional filters |
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
- [x] Score candidates by parsed songs rather than raw timestamps; stop explicit
  setlist sections at unrelated chapters/announcements or large timestamp
  regressions while preserving encore sections.
- [x] Normalize zero-width characters and remove YouTube custom-emoji tokens
  from extracted titles; validate real-world formats across multiple EN/JP
  VTuber channels with the application yt-dlp integration.
- [x] Optional LLM cleaning using existing schema columns (`cleaning_attempts`, `cleaned_song_list_comment`, `analyzed_by_llm`) — behind `LLM_CLEANING_ENABLED` (default off).
- [x] Dedupe songs within a video; conflict policy if re-analysis changes the list (`replace_for_video` last-write-wins; intra-extract dedupe by `(timestamp, casefold(title))`).

---

## Phase 6 — Search UI (MVP)

- [x] React (Vite + TypeScript) app under `frontend/`
- [x] TanStack Router + TanStack Query + Zustand (UI prefs) + Paraglide (`en` / `zh-hant` / `ja`) + Tailwind + shadcn/ui
- [x] Search-focused home page with title suggestions and a compact database
  summary; submitted terms route to the dedicated results page
- [x] Search page → grid results from `GET /v1/songs/search` with pagination and
  deep links; 500 ms debounced `GET /v1/songs/suggestions` after two characters;
  advanced filters, including repeated channel selections, apply to both
- [x] Grid-based channel → videos → video songs browsing, with primary card
  actions separated from untimestamped or timestamped YouTube actions
- [x] Contextual detail-page back navigation restores the prior search/filter
  state and uses a non-empty hierarchy fallback for direct entries
- [x] Administrator-only live updater status page →
  `GET /v1/updater/status`; guests do not poll it
- [x] Dev proxy / `VITE_API_BASE_URL` + CORS notes (`APP_ENV=dev` or `CORS_ORIGINS`)

**Still out of scope:** multi-user accounts, Flyway→Alembic / Poetry/uv rewrite, Celery/RQ, Tier C proxies/cookies.

---

## Phase 7 — Public homelab hardening

- [x] Single administrator login backed by an environment-only Argon2id hash.
- [x] Signed HttpOnly session cookie plus per-session CSRF validation.
- [x] Server-side authorization for updater status and every scraper mutation.
- [x] Per-IP guest API limits and stricter login limits, with explicit trusted proxies.
- [x] Administrator-only channel controls and per-video song-list reload.
- [x] Public How to Use, About, Terms, Privacy, and Copyright/removal pages,
  including guest guidance for requesting a channel from the relevant host.
- [x] Production secret requirements, deployment documentation, and CI credential scan.

**Still out of scope:** public account registration, multiple roles/accounts,
password recovery email, external identity providers, and shared distributed
session/rate-limit storage.

---

## Phase 8 — Public repository documentation

- [x] Restructure the English README around public use, development, deployment,
  security, API access, and project status.
- [x] Add a complete Traditional Chinese README with matching operational
  guidance.
- [x] Synchronize AGENTS, PLAN, frontend, Dev Container, and scraper
  notes with Phase 7 behavior.
- [x] Add contribution and vulnerability-reporting guidance.
- [x] Select the permissive MIT license for public reuse and contribution.

---

## Phase 9 — Updater crash safety and observability

- [x] Keep video analysis metadata and replacement songs in one rollback-safe
  transaction; unexpected errors and cancellation never consume attempts.
- [x] Commit each backfill page together with its bounded reclassification,
  song cleanup, and cursor advance.
- [x] Persist YouTube cooldown state in the same transaction as the work that
  observed the block.
- [x] Serialize every background and administrator-triggered YouTube operation
  with a process-local lock plus a PostgreSQL advisory lock.
- [x] Run production yt-dlp calls in killable subprocesses with bounded network
  retries, whole-operation deadlines, and a finite shutdown grace period.
- [x] Persist cycle owner, outcome, last success, and heartbeat independently
  from scraper transactions; flag stale running cycles in the administrator UI.
- [x] Add crash, cancellation, timeout, advisory-lock, heartbeat, and
  PostgreSQL recovery regression tests.

---

## Post-Phase 9 — Bounded administrator bulk channel ingest

- [x] Accept 1–10 channel URLs with independent validation and per-item results.
- [x] Resolve channels sequentially under the cross-process YouTube lock.
- [x] Persist an administrator add cooldown across workers and restarts.
- [x] Coalesce each bulk request into one updater wake so backfill retains its
  normal per-cycle cadence.
- [x] Surface pacing guidance and outcomes in the administrator UI.
- [x] During the global YouTube block cooldown, accept normalized URLs into a
  durable deduplicated queue without an upstream request.
- [x] Resolve deferred URLs FIFO at the start of a healthy updater cycle; keep
  queue completion atomic with channel creation and preserve pending work after
  a block, cancellation, or crash.

---

## Post-Phase 9 — Production-derived classification and parser quality

- [x] Audit every stored video from title plus persisted duration/live metadata,
  then cover observed singing-stream variants (`Sing`, conjugated Japanese
  singing phrases, acoustic/a-cappella streams, Chinese singing titles, and
  bracketed 3D performances).
- [x] Recognize bracketed/parenthesized English `Original` and CJK original-song
  labels without treating generic original animations or long uploads as songs.
- [x] Ignore trailing creator-role `KARAOKE/Vsinger` boilerplate when the real
  title explicitly identifies a game, talk, or watchalong stream.
- [x] Accept an explicit two-song setlist while retaining the three-song
  threshold for unlabelled timestamp clusters.
- [x] Strip timestamp-adjacent numbering and leading wave-dash separators, and
  exclude standalone Start/開始/Ending chapter rows without dropping later
  songs genuinely titled `StaRt`.
- [x] Keep raw top-comment observations so analyzer-only upgrades can be
  dry-run and replayed without another YouTube request. Reclassification from
  persisted metadata resets newly recognized karaoke archives to the normal
  paced analysis queue; only records without stored comments require yt-dlp.

---

## Phase 10 — Setlist contributor attribution

- [x] Promote the selected source comment's public author handle, stable
  YouTube channel id, and comment id into explicit video columns with a
  migration backfill from saved yt-dlp JSON.
- [x] Project attribution into song search/detail responses and video metadata,
  with links to the public author channel and source comment in the UI.
- [x] Add a cached, paginated public contributor aggregate and a trilingual
  thank-you page showing indexed-song and setlist-video counts.
- [x] Document community-setlist provenance, public comment metadata retention,
  attribution limits, and correction/removal paths.

---

## Phase 11 — Whole-site UI/UX redesign

Detailed plan, route inventory, audit findings, and the live implementation
checklist are tracked in [docs/ui-ux-redesign.md](docs/ui-ux-redesign.md) and
[docs/ui-ux-redesign.zh-Hant.md](docs/ui-ux-redesign.zh-Hant.md). The design
source of truth is [design-system/setlist/MASTER.md](design-system/setlist/MASTER.md).

- [x] Audit every public and administrator route in code and production.
- [x] Generate and adapt a search-first music-catalog design system.
- [x] Replace the desktop sidebar with a responsive top navigation shell.
- [x] Redesign discovery, browse, detail, data, information, and administrator pages.
- [x] Enforce 44px targets, WCAG AA themes, reduced motion, and responsive behavior.
- [x] Complete browser, unit, E2E, build, Docker, and production validation.

### Phase 11 brand and responsive correction

- [x] Restore the confirmed pre-redesign red palette, favicon, and browser/PWA
      identity without reverting the redesigned information architecture.
- [x] Return 12 recent channels, make the search workspace full width, and hide
      redundant header search controls on the search route.
- [x] Right-align medium-width header actions and keep the mobile account trigger
      circular while preserving 44px touch targets.
- [x] Add regression coverage and complete responsive, accessibility, build,
      production-image, and repository release-gate validation.
- [ ] Publish the patch release and independently verify production.

---

## Release and homelab deployment automation

- [x] Track a portable application version outside CI and expose it in the
  frontend footer.
- [x] Keep the release version synchronized across `VERSION`, frontend package
  metadata, and the npm lockfile with a local release script.
- [x] Create annotated semantic version tags without automatically pushing
  repository changes.
- [x] Publish only matching semantic version tags that point to the protected
  canonical `main`; branch pushes and pull requests cannot release or deploy.
- [x] Isolate the self-hosted runner in a private deployment repository. Poll
  private GHCR labels every ten minutes, support exact-tag manual dispatch, and
  deploy only when all four images report one complete semantic release.
- [x] Pull immutable release tags, record `.deployed-release`, and verify the
  same-origin health endpoint plus durable updater heartbeat after deployment.
- [x] Create a retained custom-format PostgreSQL backup before each production
  rollout and document restore/off-host-copy expectations.

---

## Suggested order of PRs / commits

1. Phase 0 — finish `.env.example` + env-configurable interval (docs/compose mostly done)  
2. Phase 1 — analyzer fix + write repos + tests  
3. Phase 2 — `DataUpdater` pipeline + seed channel  
4. Phase 3 — CORS/logging + production API image + `.gitignore` ✅  
5. Phase 4 — search endpoints + title index ✅  
6. Phase 5 — extraction improvements / optional LLM ✅  
7. Phase 6 — search UI MVP ✅
8. Phase 7 — public homelab hardening ✅
9. Phase 8 — bilingual public documentation and policies ✅

---

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| YouTube / yt-dlp breakage | Pin version; rate-limit; classify failures explicitly; cap scrapes per cycle |
| YouTube access / bot limits | Tier B: cycle caps, inter-scrape jitter, skip/retry, block detect → abort cycle + cooldown (no proxies/cookies yet) |
| Event loop blocked / scraper wedged | Killable subprocesses with bounded yt-dlp retries and whole-operation deadlines |
| Concurrent workers / overlapping deploys | Process-local lock plus PostgreSQL advisory singleton lock |
| Silent updater death | Durable owner/outcome/heartbeat with stalled-cycle alert |
| Duplicate / stale songs | `replace_for_video` or unique constraint; track `last_analyzed_at` |
| Long first sync | Work caps + prioritize recent uploads |
| Schema drift (sqlacodegen) | Migrations first; regenerate models; don’t hand-edit generated files lightly |
| Guest abuse | Per-IP limits, stricter login limit, explicit trusted proxies; add a gateway limiter for replicas |
| Admin request forgery | Signed HttpOnly session + per-session CSRF on every mutation |
| Secret disclosure | Ignored env files, build-context exclusions, CI/history signature scan, documented rotation |
| License ambiguity | Top-level MIT license, matching README/UI notices, and preserved third-party terms |

---

## Success criteria

1. Seeded channel → automatic songs in DB within one update cycle.  
2. `GET /v1/songs/search?q=...` returns results with timestamp deep links (optional channel / type / date filters).  
3. `docker compose up` (or documented manual path) is reproducible on a clean machine.  
4. Updater failures are logged and do not crash the API process.  
5. Search UI can query the API and open YouTube deep links.
6. Guests cannot view updater status or invoke any mutation, including by
   calling the API directly.
7. Administrator sessions expire, mutations require CSRF, and password-hash or
   signing-secret rotation invalidates existing sessions.
8. The production stack exposes only the frontend proxy: loopback when the TLS
   proxy is local, or a firewalled private-LAN bind when it is remote. No real
   deployment secret is stored in Git.
