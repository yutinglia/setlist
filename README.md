# Setlist — VTuber Karaoke Search

[English](README.md) · [繁體中文](README.zh-Hant.md)

![Setlist social preview](frontend/public/og.png)

Setlist is a self-hosted index of songs performed in VTuber karaoke streams.
It processes public YouTube archives, extracts song titles from timestamped
setlist comments, and links each search result to its saved timestamp in the
original video. Each indexed song credits the public YouTube commenter whose
selected setlist supplied its title and timestamp.

Setlist is maintained as a personal homelab project and is designed for a small
public deployment. Focused contributions are welcome. Guests can search and
browse. A single administrator can sign in to manage channels, refresh
metadata, reload a video's song list, and view live updater status.

> Automated metadata can be incomplete or wrong. Setlist is an independent
> index, does not host video or audio, and is not affiliated with YouTube,
> Google, any VTuber agency, channel, or performer.

## Features

- Search-focused home page with title suggestions and a dedicated results page
- Paginated grid results with one or more channel, content type, and date filters
- YouTube deep links that open directly at each song's timestamp
- Source-comment attribution on songs plus a public thank-you page that
  recognizes setlist contributors
- Searchable channel browsing plus a recent-updates page for the latest 10
  channel refreshes and 100 indexed songs
- Grid-based video, song-detail, and database-summary browsing
- English, Traditional Chinese, and Japanese UI
- Pinned/uploader-aware setlist extraction with parsed-song scoring, mixed
  setlist/chapter boundaries, and several timestamp formats
- Durable full-channel backfill and conservative ongoing discovery
- Tier B YouTube pacing: bounded work, jitter, retry limits, block detection,
  and a persisted cooldown
- Optional OpenAI-compatible cleanup after the regex extractor
- Single-administrator authentication with signed HttpOnly sessions and CSRF
- Per-IP guest API limits and stricter login limits
- Public How to Use, About, contributor Thanks, Terms, Privacy, and
  Copyright/removal pages
- Production containers for the React frontend, FastAPI service, PostgreSQL,
  and Flyway

## Access model

| Capability | Guest | Administrator |
|------------|:-----:|:-------------:|
| Search and browse public index data | Yes | Yes |
| View setlist contributor acknowledgements | Yes | Yes |
| View summary report | Yes | Yes |
| Poll live updater status | No | Yes |
| Add channels or refresh channel metadata | No | Yes |
| Reload a video's song list | No | Yes |

Authorization is enforced by the API. Hiding a frontend control is never
treated as a security boundary.

Guests who want another channel indexed should contact the deployment
operator. On the official Setlist site, open a
[channel request](https://github.com/yutinglia/setlist/issues/new?template=channel-request.yml);
on any other hosted instance, contact that site's owner or administrator.

## Quick start with a Dev Container

This is the easiest path for development on Windows, macOS, or Linux.

1. Clone the repository and open it in VS Code or Cursor.
2. Run **Dev Containers: Reopen in Container**.
3. Wait for PostgreSQL, Flyway, Python dependencies, and `npm ci` to finish.
4. Open <http://localhost:5173>.

The API and UI start automatically with hot reload. Background scraping is
disabled by default in development, so opening the repository does not
immediately call YouTube.

| URL | Purpose |
|-----|---------|
| <http://localhost:5173> | Search UI |
| <http://localhost:5173/admin/login> | Administrator sign-in |
| <http://localhost:5173/status> | Administrator-only updater status |
| <http://localhost:8000/v1/health> | API and database health |
| <http://localhost:8000/docs> | OpenAPI documentation in `APP_ENV=dev` |

Inside the container, logs are written to:

```text
/tmp/vtuber-karaoke-search-dev/backend.log
/tmp/vtuber-karaoke-search-dev/frontend.log
```

See [.devcontainer/README.md](.devcontainer/README.md) for database access,
admin setup, and lifecycle details.

## Public homelab deployment

### Requirements

- Docker Engine with Compose v2
- A public hostname
- An HTTPS reverse proxy such as Caddy, Traefik, or nginx
- Enough storage for PostgreSQL

The production stack binds only the frontend proxy to
`${FRONTEND_BIND_ADDRESS:-127.0.0.1}:${FRONTEND_PORT:-8080}`. Keep the loopback
default when the TLS reverse proxy runs on the same host. If the proxy runs on
another machine, set `FRONTEND_BIND_ADDRESS` to this server's private LAN
address and firewall the port so only the proxy can reach it. FastAPI and
PostgreSQL stay on the private Compose network.

### 1. Create local production configuration

```bash
cp .env.production.example .env
```

On PowerShell:

```powershell
Copy-Item .env.production.example .env
```

Set `PUBLIC_SITE_URL` to the final HTTPS origin and replace every required
blank in `.env`.

Self-hosters should also set `VITE_CHANNEL_REQUEST_URL` to their own support
form, issue tracker, `mailto:` address, or same-origin contact page. When it is
unset, the frontend falls back to the `channel-request.yml` issue form under
`VITE_SOURCE_URL`.

### 2. Generate the administrator password hash

Install the runtime dependencies, then use the interactive helper:

```bash
cd backend
python -m pip install -r requirements.txt
python generate_admin_password_hash.py
cd ..
```

Store the output in `.env` inside **single quotes** because Argon2 hashes
contain `$`:

```dotenv
ADMIN_PASSWORD_HASH='$argon2id$...'
```

The plaintext password is never stored by the application.

### 3. Generate a separate session-signing secret

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the result in `SESSION_SECRET`. Do not reuse the administrator password or
database password.

### 4. Start the stack

```bash
docker compose up --build -d
docker compose ps
```

Verify the local proxy before exposing it:

```bash
curl http://127.0.0.1:8080/v1/health
```

The example uses the default loopback bind. When `FRONTEND_BIND_ADDRESS` is a
private LAN address, verify that configured address instead.

Point the HTTPS reverse proxy at
`http://${FRONTEND_BIND_ADDRESS:-127.0.0.1}:${FRONTEND_PORT:-8080}`. Keep
`AUTH_COOKIE_SECURE=true`. The bundled frontend serves the SPA, applies browser
security headers, and proxies `/v1` to FastAPI.

Compose refuses to start without `PUBLIC_SITE_URL`, `DB_PASSWORD`,
`ADMIN_PASSWORD_HASH`, and `SESSION_SECRET`.

### Automated homelab deployment

The source repository does not contain production host paths, secrets, or a
self-hosted deployment job. A semantic release tag such as `v0.1.0` runs the
[`Build release images`](.github/workflows/release.yml) workflow on a
GitHub-hosted runner. It verifies that the tag matches [`VERSION`](VERSION) and
the current protected `main` commit, publishes versioned frontend, backend,
Flyway, and PostgreSQL images to GHCR, attaches SBOM/provenance metadata, and
only then creates a GitHub Release. BuildKit SBOM and provenance metadata are
always stored with each image in GHCR; GitHub's additional signed attestation
is enabled when the source repository is public.

Production deployment is intentionally controlled by a separate private
repository. Its self-hosted runner consumes published release images; it never
checks out or executes pull-request code from the source repository. After the
GitHub Release exists, the release workflow uses a narrowly scoped GitHub App
installation token to notify that control plane of the exact tag. The deployment
independently verifies all four private GHCR images before using them; an hourly
poll remains as a fallback, and exact tags can also be dispatched manually.
Before replacement it creates a custom-format PostgreSQL backup, and after
startup it requires both the same-origin health endpoint and a fresh durable
updater heartbeat. A fork can use any deployment system or the local Compose
instructions above without needing the private control plane.

Production Compose also applies explicit resource ceilings: 128 MiB / 0.25 CPU
for nginx, 768 MiB / 1 CPU for the API and scraper, 512 MiB / 0.75 CPU for
PostgreSQL, and 256 MiB / 0.5 CPU for the one-shot Flyway migration. Adjust
these values only after observing sustained usage on the target host.

### Versions and releases

The version shown in the site footer is resolved in this order:

1. the deployment/build override;
2. an exact `v*` Git tag at the checked-out commit;
3. the tracked [`VERSION`](VERSION) file;
4. the synchronized frontend package version.

The last fallback keeps a source archive or ordinary
`docker compose up --build -d` deployment versioned even when Git metadata and
CI are unavailable.

Prepare a release pull request from a clean, up-to-date `main` branch:

```bash
git switch main
git pull --ff-only
node scripts/bump-version.mjs patch
# Follow the printed commands to push release/vX.Y.Z and open its pull request.
```

The argument may be `major`, `minor`, `patch`, or an explicit higher
`MAJOR.MINOR.PATCH`. The script synchronizes `VERSION`, the frontend package
metadata, and the lockfile, then creates the release commit on a
`release/vX.Y.Z` branch. It never pushes on the user's behalf.

After the protected pull request is approved and merged, tag the resulting
current `main` commit:

```bash
git switch main
git pull --ff-only
node scripts/bump-version.mjs tag
# Review the annotated tag, then use the exact tag printed:
git push origin vX.Y.Z
```

Merged Dependabot pull requests use the same protected release contract through
[`Prepare dependency release`](.github/workflows/dependency-release.yml).
After the tested `main` revision contains one or more verified Dependabot
updates newer than the current release tag, the workflow creates or refreshes a
Patch release pull request that changes only the three synchronized version
files. It dispatches CI explicitly and enables squash auto-merge, but the
release pull request still requires an independent maintainer approval. After
that approved pull request merges, the workflow creates the annotated tag and
dispatches the normal release-image workflow. The private production control
plane is then notified through a short-lived, single-repository GitHub App token
and deploys the complete matching image set. The dependency and release pull
request automation uses the repository `GITHUB_TOKEN`; cross-repository
notification uses a release-environment App credential instead of a maintainer
personal access token.

Ordinary source builds display the tracked version (and add a short commit SHA
when Git metadata is available). Release images display the clean semantic
version. Branch pushes and pull requests run CI but cannot publish a release or
deploy production.

See [Release verification](docs/RELEASE_VERIFICATION.md) for the repeatable
pre-tag, image attestation, and post-release verification checklist.

### Deployment security checklist

- Keep `.env` outside Git and restrict who can read it.
- Expose only the TLS reverse proxy; do not publish PostgreSQL or FastAPI.
- Use a unique random database password and a session secret of at least 32
  bytes.
- Trust `X-Forwarded-For` only from the exact networks in
  `TRUSTED_PROXY_CIDRS`.
- Keep the UI and API on one origin when possible. If they must be separate,
  list only the UI's exact origin in `CORS_ORIGINS`.
- Create and test a `pg_dump` backup before every migration, host change, or
  database maintenance window; keep an encrypted copy off-host.
- Review logs and dependency updates regularly.

Guest limits are in memory and apply per API process. The default deployment
uses one API worker; add an external gateway limiter before scaling to multiple
replicas.

More security and private-reporting guidance is in
[SECURITY.md](SECURITY.md).

## Local development without a Dev Container

Start PostgreSQL and apply all Flyway migrations:

```bash
docker compose -f docker-compose.dev.yml up -d db flyway
```

Run the API from its required working directory:

```bash
cd backend
python -m pip install -r requirements-dev.txt
APP_ENV=dev BACKGROUND_UPDATER_ENABLED=false \
  uvicorn main:app --host 0.0.0.0 --port 8000
```

PowerShell:

```powershell
Set-Location backend
python -m pip install -r requirements-dev.txt
$env:APP_ENV = "dev"
$env:BACKGROUND_UPDATER_ENABLED = "false"
uvicorn main:app --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/v1` to `http://127.0.0.1:8000`. See
[backend/README.md](backend/README.md) and
[frontend/README.md](frontend/README.md) contain component-specific commands
and architecture notes.

## Administrator setup in development

Administrator features remain protected in `APP_ENV=dev`. To test them:

1. Generate an Argon2id hash with
   `backend/generate_admin_password_hash.py`.
2. Set `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, and a 32-byte-or-longer
   `SESSION_SECRET` in the ignored root `.env`.
3. Keep `AUTH_COOKIE_SECURE=false` only while using local HTTP.
4. Restart or rebuild the development environment.

If those settings are absent, guest search and browse continue to work, while
administrator login fails closed.

## Seed channels and run one update

After the development database is running:

```bash
docker compose -f docker-compose.dev.yml exec -T db \
  psql -U vks_db_user -d vks_db < db/devscript/seed_channels.sql
```

To exercise the same bounded updater path once without leaving a scheduler
running:

```bash
cd backend
python run_updater_once.py
```

After a classifier or regex-analyzer upgrade, preview its effect on existing
metadata and saved top comments without contacting YouTube:

```bash
python reanalyze_stored_data.py
```

The default is an atomic dry run and always rolls back. It reclassifies all
stored videos but only recovers setlists for unresolved videos; existing
successful setlists are not rewritten. After reviewing the counts and taking a
database backup, apply that recovery pass and reset remaining failures for the
normal paced queue:

```bash
python reanalyze_stored_data.py --apply --requeue-unresolved
```

The command shares the updater's cross-process lock, reclassifies every stored
video, queues newly recognized karaoke archives, and immediately recovers a
failed setlist when its saved raw comment is now parseable. The optional requeue
resets only unresolved karaoke rows; the background updater still performs all
YouTube work under its normal caps and delays. Use `--include-successful` only
after separately reviewing its dry-run deltas when an intentional rewrite of
existing successful setlists is required. LLM-cleaned setlists remain protected.

Enable the long-running worker only when you intend to scrape:

```dotenv
BACKGROUND_UPDATER_ENABLED=true
```

## API overview

List endpoints accept `limit` (1–100, default 20) and `offset`
(0–1,000,000, default 0).

### Public guest endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/health` | API and database health |
| `GET` | `/v1/songs/search?q=` | Search songs; optional repeated channel/type/date filters |
| `GET` | `/v1/songs/suggestions?q=` | Up to 10 distinct title suggestions; optional repeated channel/type/date filters |
| `GET` | `/v1/songs/{id}` | Song detail and timestamped YouTube link |
| `GET` | `/v1/contributors` | Paginated setlist-comment authors with song and video counts |
| `GET` | `/v1/channels` | Tracked channels; optional literal `q` search by name or channel ID |
| `GET` | `/v1/updates/recent` | Latest 10 updated channels and 100 indexed songs |
| `GET` | `/v1/channels/{id}` | Public metadata for one tracked channel |
| `GET` | `/v1/channels/{id}/videos` | Videos for one channel |
| `GET` | `/v1/videos/{id}` | Video metadata |
| `GET` | `/v1/videos/{id}/songs` | Extracted songs for one video |
| `GET` | `/v1/report/summary` | Aggregate database and pipeline counts |
| `GET` | `/v1/auth/session` | Current guest/admin session state |
| `POST` | `/v1/auth/login` | Rate-limited administrator sign-in |

Example:

```bash
curl 'http://localhost:8000/v1/songs/search?q=Stellar&channel_id=UC_FIRST&channel_id=UC_SECOND&type=karaoke'
```

Search results include a `video_url` such as
`https://www.youtube.com/watch?v=...&t=300s`, along with
`setlist_comment_author`, `setlist_comment_author_id`, and
`setlist_comment_id` attribution fields when a source comment is available.

The search UI waits 500 ms after at least two characters before requesting up
to eight lightweight suggestions. Visitors can select up to 25 channels; the
client sends each selection as a repeated `channel_id` parameter. Full search
runs only after the visitor submits the form or selects a suggestion.

Channel browse search also runs on form submission and stores its literal `q`
value in the URL. `%` and `_` are treated as channel-name text, not SQL
wildcards.

### Administrator-only endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/auth/logout` | End the current administrator session |
| `GET` | `/v1/updater/status` | Live detail plus durable outcome, heartbeat, last success, and cooldown |
| `POST` | `/v1/channels` | Validate and add a channel, or return `202 queued` during YouTube cooldown |
| `POST` | `/v1/channels/bulk` | Add or queue 1–10 channels with per-item results |
| `POST` | `/v1/channels/{id}/videos/refresh` | Refresh metadata without deleting setlists |
| `POST` | `/v1/videos/{id}/songs/reload` | Re-fetch comments and rerun extraction |

Browser mutations require both the signed administrator cookie and the
session's `X-CSRF-Token`.

Bulk channel add validates each URL independently. With normal YouTube access,
it resolves valid channels one at a time and applies the persisted 10-second
administrator add cooldown between lookups. During the separate global block
cooldown (six hours by default), valid unresolved URLs are stored in
`channel_ingest_queue` without contacting YouTube and reported as `queued`.
The updater resolves them FIFO after cooldown under the same lock and pacing.
Each request produces at most one updater wake-up.

## Configuration

Copy [`.env.example`](.env.example) for development or
[`.env.production.example`](.env.production.example) for Compose production.
The sample files contain placeholders only.

Important settings:

| Setting | Default | Meaning |
|---------|---------|---------|
| `APP_ENV` | `prod` | `dev` enables API docs and local development origins |
| `BACKGROUND_UPDATER_ENABLED` | `false` | Explicitly enables periodic scraping |
| `MANAGEMENT_API_ENABLED` | `true` | Emergency kill switch; never bypasses auth |
| `ADMIN_USERNAME` | `admin` | The single administrator name |
| `ADMIN_PASSWORD_HASH` | empty | Argon2id hash; never plaintext |
| `SESSION_SECRET` | empty | Session-signing secret, minimum 32 bytes |
| `AUTH_SESSION_TTL_SECONDS` | `43200` | Administrator session lifetime |
| `AUTH_COOKIE_SECURE` | true in prod | Must remain true on public HTTPS |
| `GUEST_RATE_LIMIT_REQUESTS/WINDOW_SECONDS` | `60/60` | Guest requests per resolved IP/window |
| `LOGIN_RATE_LIMIT_REQUESTS/WINDOW_SECONDS` | `5/300` | Login attempts per resolved IP/window |
| `CHANNEL_ADD_COOLDOWN_SECONDS` | `10` | Persisted pause between administrator channel lookups and bulk items |
| `TRUSTED_PROXY_CIDRS` | empty | Proxies allowed to provide client IPs |
| `CORS_ORIGINS` | empty | Exact credentialed cross-origin UI origins |
| `DATA_UPDATE_INTERVAL` | `300` | Worker heartbeat; only due work calls YouTube |
| `UPDATE_STEADY_SCAN_INTERVAL` | `21600` | Normal per-channel discovery interval |
| `UPDATE_MAX_COMMENT_SCRAPES` | `3` | Comment scrapes per update cycle |
| `UPDATE_MAX_COMMENTS_PER_VIDEO` | `50` | Top comments fetched on the first analysis |
| `UPDATE_MAX_RECHECK_COMMENTS_PER_VIDEO` | `200` | Deeper top-comment window on later attempts |
| `UPDATE_MAX_ANALYZE_ATTEMPTS` | `5` | Maximum paced attempts for an unresolved karaoke archive |
| `UPDATE_YOUTUBE_COOLDOWN_SECONDS` | `21600` | Persisted cooldown after a likely block |
| `YTDLP_OPERATION_TIMEOUT_SECONDS` | `300` | Hard deadline for one blocking yt-dlp operation |
| `UPDATER_SHUTDOWN_GRACE_SECONDS` | `20` | Time allowed for cancellation and rollback |
| `UPDATER_HEARTBEAT_INTERVAL_SECONDS` | `30` | Durable heartbeat write interval during a cycle |
| `UPDATER_HEARTBEAT_STALE_SECONDS` | `120` | Worker heartbeat age that triggers a stalled alert |
| `CACHE_URL` | empty | Optional Redis/Valkey URL; empty selects the no-op cache adapter |
| `CACHE_SEARCH_TTL_SECONDS` | `900` | Search/suggestion cache lifetime |
| `CACHE_CATALOG_TTL_SECONDS` | `3600` | Stable browse/detail cache lifetime |
| `CACHE_REPORT_TTL_SECONDS` | `300` | Summary-report cache lifetime |
| `CACHE_MAXMEMORY` | `80mb` | Bundled Valkey limit inside its 128 MiB container |
| `LLM_CLEANING_ENABLED` | `false` | Optional post-regex cleanup |

The complete list and explanatory comments live in [`.env.example`](.env.example).

The backend uses an explicit application composition root. FastAPI routes
receive query/use-case services, and those services receive repositories,
authentication, scraper strategies, updater state, and cache ports through
dependency injection. PostgreSQL remains the source of truth. The optional
cache uses a cache-aside adapter, fails open when unavailable, and is
invalidated after committed public-data mutations. The bundled service uses
bounded memory with LRU eviction, and cache failures temporarily bypass the
adapter rather than adding repeated network timeouts. Start the bundled Valkey
profile with:

```bash
CACHE_URL=redis://cache:6379/0 docker compose --profile cache up -d
```

Leave `CACHE_URL` empty to run without Redis or Valkey. See
[`docs/architecture.md`](docs/architecture.md) for the dependency boundaries.

## How the pipeline behaves

1. Administrators may submit up to ten channels in one batch. Healthy requests
   resolve immediately with durable pacing; URLs submitted during a global
   YouTube cooldown are persisted and resolved FIFO afterward. The batch
   produces one updater wake-up.
2. A tracked channel is discovered through bounded Streams and Videos playlist
   pages.
3. Flat-list snapshots preserve stable metadata and approximate dates without
   a per-video request fan-out.
4. Karaoke candidates enter a separate, paced comment-analysis queue.
5. The analyzer prefers pinned and uploader comments, then parsed-song count and
   likes. It isolates explicit setlist sections, stops before unrelated chapters
   or large timestamp regressions, preserves encore sections, and replaces a
   video's song list only after a successful analysis. The selected comment's
   public author handle, stable YouTube channel id, and comment id are promoted
   into explicit attribution fields.
6. Exact metadata can upgrade approximate values; later sparse observations
   never erase richer snapshots or a previous successful setlist.
7. Suspected YouTube blocking aborts remaining calls and persists a cooldown so
   a restart cannot bypass it.
8. A process-local lock plus PostgreSQL advisory lock serializes background and
   administrator-triggered YouTube work across workers and overlapping deploys.
9. Production yt-dlp calls run in killable child processes with bounded
   network retries and whole-operation deadlines. Independently committed
   lifecycle heartbeats expose a crashed or wedged cycle as stalled without
   committing scraper data.

Detailed design decisions are recorded in [PLAN.md](PLAN.md) and scraper payload
notes in [backend/NOTE.md](backend/NOTE.md).

## Tests and CI

Backend:

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest --cov --cov-report=term-missing:skip-covered
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run test:coverage
npx playwright install chromium
npm run test:e2e
npm run build
```

Repository checks:

```bash
python scripts/check_secrets.py
python scripts/check_code_quality.py
```

GitHub Actions CI runs the credential and source-size checks, Ruff, backend
tests against PostgreSQL 18 after all Flyway migrations, frontend tests, production image
builds, third-party notice verification, frontend lint, and the production
frontend build. Backend combined statement/branch coverage and every frontend
coverage metric must be at least 80%. HTML, XML, JSON-summary, and LCOV reports
are retained as CI artifacts for analysis. Playwright also verifies the
critical public-search and administrator-authentication journeys in Chromium;
failure traces, screenshots, and video are retained. See
[Coverage policy](docs/COVERAGE.md) for scope, exclusions, and local commands.
The release workflow accepts only a matching semantic version tag on the
current protected `main` commit with a successful coverage-gated CI run;
production deployment is isolated in a private repository.

## Project layout

```text
setlist/
├── .devcontainer/          # Python 3.14 + Node 26 editor environment
├── .github/workflows/      # CI and release image publication
├── backend/                # FastAPI API, auth, updater, scrapers, tests
├── db/migrations/          # Flyway V1–V12 schema history (source of truth)
├── frontend/               # React UI and production nginx proxy
├── scripts/                # Repository security checks
├── CONTRIBUTING.md         # Contribution workflow
├── SECURITY.md             # Private vulnerability-reporting guidance
├── LICENSE                 # MIT license for project-authored code
├── THIRD_PARTY_NOTICES.md  # Generated frontend dependency notices
├── docker-compose.dev.yml  # Development database and Dev Container
└── docker-compose.yml      # Production homelab stack
```

## Contributing and project status

Phases 0–10 are implemented: pipeline, extraction, search API/UI, scheduler
hardening, authentication, guest limits, public-service pages, deployment
hardening, public documentation, updater crash safety/observability, and
setlist-contributor attribution. Until version 1.0.0, database and API
compatibility may change between releases.

Before opening a pull request, read [CONTRIBUTING.md](CONTRIBUTING.md),
[AGENTS.md](AGENTS.md), and [PLAN.md](PLAN.md).

## Legal and removal requests

Setlist stores factual metadata and links to public YouTube pages; it does not
host the linked performances. Rights to videos, audio, thumbnails, names, and
other creative material remain with their respective owners.

The song index depends on timestamped setlists contributed by commenters on
YouTube. Setlist credits the public account attached to each selected source
comment and links back where possible. Attribution does not imply endorsement
or affiliation. Public comment handles, channel ids, comment ids, and selected
comment text may remain indexed until the source is refreshed or a correction
or removal is requested.

Rights holders and channel operators can request a correction, channel
exclusion, or removal through
[the correction or removal form](https://github.com/yutinglia/setlist/issues/new?template=correction-or-removal.yml).
Do not post private identity documents in a public issue.

## License

Setlist is released under the [MIT License](LICENSE). You may use, modify,
redistribute, sublicense, or sell copies of the project as long as the
copyright and license notice is retained.

Third-party packages, fonts, service APIs, linked media, and extracted metadata
remain subject to their own licenses and terms. Notices for production frontend
packages redistributed by the compiled site are recorded in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
