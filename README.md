# Setlist — VTuber Karaoke Search

[English](README.md) · [繁體中文](README.zh-Hant.md)

![Setlist social preview](frontend/public/og.png)

Setlist is a self-hosted search index for songs performed in VTuber karaoke
streams. It discovers public YouTube archives, finds timestamped setlist
comments, extracts song titles, and turns them into searchable links that jump
to the right moment in the original video.

Setlist is maintained as a personal homelab project and is designed for a small
public deployment. Focused contributions are welcome. Guests can search and
browse. A single administrator can sign in to manage channels, refresh
metadata, reload a video's song list, and view live updater status.

> Automated metadata can be incomplete or wrong. Setlist is an independent
> index, does not host video or audio, and is not affiliated with YouTube,
> Google, any VTuber agency, channel, or performer.

## What you get

- Fast, paginated song search with channel, content type, and date filters
- YouTube deep links that open directly at each song's timestamp
- Channel, video, song-detail, and database-summary browsing
- English, Traditional Chinese, and Japanese UI
- Pinned/uploader-aware setlist extraction with parsed-song scoring, mixed
  setlist/chapter boundaries, and several timestamp formats
- Durable full-channel backfill and conservative ongoing discovery
- Tier B YouTube pacing: bounded work, jitter, retry limits, block detection,
  and a persisted cooldown
- Optional OpenAI-compatible cleanup after the regex extractor
- Single-administrator authentication with signed HttpOnly sessions and CSRF
- Per-IP guest API limits and stricter login limits
- Public How to Use, About, Terms, Privacy, and Copyright/removal pages
- Production containers for the React frontend, FastAPI service, PostgreSQL,
  and Flyway

## Access model

| Capability | Guest | Administrator |
|------------|:-----:|:-------------:|
| Search and browse public index data | Yes | Yes |
| View summary report | Yes | Yes |
| Poll live updater status | No | Yes |
| Add channels or refresh channel metadata | No | Yes |
| Reload a video's song list | No | Yes |

Authorization is enforced by the API. Hiding a frontend control is never
treated as a security boundary.

Guests who want another channel indexed should contact the deployment
operator. On the official Setlist site, open a
[GitHub issue](https://github.com/yutinglia/setlist/issues/new); on any other
hosted instance, contact that site's owner or administrator.

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
unset, the frontend falls back to `VITE_SOURCE_URL/issues/new`.

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
checks out or executes pull-request code from the source repository. It polls
the four private GHCR image labels every ten minutes and deploys only a complete,
matching semantic release; exact tags can also be dispatched manually. Before
replacement it creates a custom-format PostgreSQL backup, and after startup it
requires both the same-origin health endpoint and a fresh durable updater
heartbeat. A fork can use any deployment system or the local Compose
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
[frontend/README.md](frontend/README.md) for frontend-specific commands.

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
| `GET` | `/v1/songs/search?q=` | Search songs; optional channel/type/date filters |
| `GET` | `/v1/songs/suggestions?q=` | Up to 10 distinct title suggestions; optional channel/type/date filters |
| `GET` | `/v1/songs/{id}` | Song detail and timestamped YouTube link |
| `GET` | `/v1/channels` | Tracked channels |
| `GET` | `/v1/channels/{id}/videos` | Videos for one channel |
| `GET` | `/v1/videos/{id}` | Video metadata |
| `GET` | `/v1/videos/{id}/songs` | Extracted songs for one video |
| `GET` | `/v1/report/summary` | Aggregate database and pipeline counts |
| `GET` | `/v1/auth/session` | Current guest/admin session state |
| `POST` | `/v1/auth/login` | Rate-limited administrator sign-in |

Example:

```bash
curl 'http://localhost:8000/v1/songs/search?q=Stellar&type=karaoke'
```

Search results include a `video_url` such as
`https://www.youtube.com/watch?v=...&t=300s`.

The search UI waits 500 ms after at least two characters before requesting up
to eight lightweight suggestions. Full search runs only after the visitor
submits the form or selects a suggestion.

### Administrator-only endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/auth/logout` | End the current administrator session |
| `GET` | `/v1/updater/status` | Live detail plus durable outcome, heartbeat, last success, and cooldown |
| `POST` | `/v1/channels` | Validate and add a YouTube channel |
| `POST` | `/v1/channels/bulk` | Add 1–10 channels sequentially with per-item results |
| `POST` | `/v1/channels/{id}/videos/refresh` | Refresh metadata without deleting setlists |
| `POST` | `/v1/videos/{id}/songs/reload` | Re-fetch comments and rerun extraction |

Browser mutations require both the signed administrator cookie and the
session's `X-CSRF-Token`.

Bulk channel add validates each URL independently, resolves valid channels one
at a time, and applies the persisted administrator add cooldown between YouTube
lookups. The whole batch queues one updater wake-up—not one wake-up per
channel—so pending backfills continue under the normal per-cycle limits and
configured worker interval (five minutes by default). A separate
`POST /v1/channels` during the cooldown returns `429` with `Retry-After`.

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
| `UPDATE_YOUTUBE_COOLDOWN_SECONDS` | `21600` | Persisted cooldown after a likely block |
| `YTDLP_OPERATION_TIMEOUT_SECONDS` | `300` | Hard deadline for one blocking yt-dlp operation |
| `UPDATER_SHUTDOWN_GRACE_SECONDS` | `20` | Time allowed for cancellation and rollback |
| `UPDATER_HEARTBEAT_INTERVAL_SECONDS` | `30` | Durable heartbeat write interval during a cycle |
| `UPDATER_HEARTBEAT_STALE_SECONDS` | `120` | Worker heartbeat age that triggers a stalled alert |
| `LLM_CLEANING_ENABLED` | `false` | Optional post-regex cleanup |

The complete list and explanatory comments live in [`.env.example`](.env.example).

## How the pipeline behaves

1. Administrators may add up to ten channels in one paced batch. Channel
   metadata lookups are serialized with a durable cooldown, and the batch
   produces one updater wake-up.
2. A tracked channel is discovered through bounded Streams and Videos playlist
   pages.
3. Flat-list snapshots preserve stable metadata and approximate dates without
   a per-video request fan-out.
4. Karaoke candidates enter a separate, paced comment-analysis queue.
5. The analyzer prefers pinned and uploader comments, then parsed-song count and
   likes. It isolates explicit setlist sections, stops before unrelated chapters
   or large timestamp regressions, preserves encore sections, and replaces a
   video's song list only after a successful analysis.
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
python -m pytest
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run build
```

Repository credential scan:

```bash
python scripts/check_secrets.py
```

GitHub Actions CI runs the credential scan, Ruff, backend tests against
PostgreSQL 18 after all Flyway migrations, production image builds, third-party
notice verification, frontend lint, and the production frontend build. The
release workflow runs only for a matching semantic version tag on the current
protected `main` commit; production deployment is isolated in a private
repository.

## Project layout

```text
setlist/
├── .devcontainer/          # Python 3.14 + Node 26 editor environment
├── .github/workflows/      # CI and release image publication
├── backend/                # FastAPI API, auth, updater, scrapers, tests
├── db/migrations/          # Flyway V1–V10 schema history (source of truth)
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

Phases 0–9 are implemented: pipeline, extraction, search API/UI, scheduler
hardening, authentication, guest limits, public-service pages, deployment
hardening, public documentation, and updater crash safety/observability. Until
version 1.0.0, database and API compatibility may change between releases.

Before opening a pull request, read [CONTRIBUTING.md](CONTRIBUTING.md),
[AGENTS.md](AGENTS.md), and [PLAN.md](PLAN.md).

## Legal and removal requests

Setlist stores factual metadata and links to public YouTube pages; it does not
host the linked performances. Rights to videos, audio, thumbnails, names, and
other creative material remain with their respective owners.

Rights holders and channel operators can request a correction, channel
exclusion, or removal through
[GitHub Issues](https://github.com/yutinglia/setlist/issues).
Do not post private identity documents in a public issue.

## License

Setlist is released under the [MIT License](LICENSE). You may use, modify,
redistribute, sublicense, or sell copies of the project as long as the
copyright and license notice is retained.

Third-party packages, fonts, service APIs, linked media, and extracted metadata
remain subject to their own licenses and terms. Notices for production frontend
packages redistributed by the compiled site are recorded in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
