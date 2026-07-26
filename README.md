# Setlist — VTuber Karaoke Search

[English](README.md) · [繁體中文](README.zh-Hant.md)

![Setlist social preview](frontend/public/og.png)

Setlist is a self-hosted search index for songs performed in VTuber karaoke
streams. It discovers public YouTube archives, finds timestamped setlist
comments, extracts song titles, and turns them into searchable links that jump
to the right moment in the original video.

The project is under rapid development and is designed for a small public
homelab deployment. Guests can search and browse. A single administrator can
sign in to manage channels, refresh metadata, reload a video's song list, and
view live updater status.

> Automated metadata can be incomplete or wrong. Setlist is an independent
> index, does not host video or audio, and is not affiliated with YouTube,
> Google, any VTuber agency, channel, or performer.

## What you get

- Fast, paginated song search with channel, content type, and date filters
- YouTube deep links that open directly at each song's timestamp
- Channel, video, song-detail, and database-summary browsing
- English and Traditional Chinese UI
- Pinned/uploader-aware setlist extraction with several timestamp formats
- Durable full-channel backfill and conservative ongoing discovery
- Tier B YouTube pacing: bounded work, jitter, retry limits, block detection,
  and a persisted cooldown
- Optional OpenAI-compatible cleanup after the regex extractor
- Single-administrator authentication with signed HttpOnly sessions and CSRF
- Per-IP guest API limits and stricter login limits
- Public About, Terms, Privacy, and Copyright/removal pages
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
`127.0.0.1:${FRONTEND_PORT:-8080}`. FastAPI and PostgreSQL stay on the private
Compose network.

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

### 2. Generate the administrator password hash

Install the runtime dependencies, then use the interactive helper:

```bash
cd data_updater
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

Point the HTTPS reverse proxy at `http://127.0.0.1:8080`. Keep
`AUTH_COOKIE_SECURE=true`. The bundled frontend serves the SPA, applies browser
security headers, and proxies `/v1` to FastAPI.

Compose refuses to start without `PUBLIC_SITE_URL`, `DB_PASSWORD`,
`ADMIN_PASSWORD_HASH`, and `SESSION_SECRET`.

### Automated homelab deployment

The deployment workflow follows the local-image pattern used by the homelab
entry-site repository. A Linux x64 self-hosted runner builds the two application
images, reruns Flyway, starts the production Compose stack, and verifies the
proxied health endpoint.

On the runner, keep the production configuration at:

```text
~/services/vtuber-karaoke-search/.env
```

Only pushes to `main` and semantic release tags such as `v0.1.0` trigger the
workflow. Pull requests and manual workflow dispatches cannot deploy. The job
also refuses to run outside `yutinglia/vtuber-karaoke-search`. Configure branch
protection, protected release tags, and protection rules on the `production`
GitHub Environment before relying on it for an internet-facing service.

### Versions and releases

The version shown in the site footer is resolved in this order:

1. the deployment/build override;
2. an exact `v*` Git tag at the checked-out commit;
3. the tracked [`VERSION`](VERSION) file;
4. the synchronized frontend package version.

The last fallback keeps a source archive or ordinary
`docker compose up --build -d` deployment versioned even when Git metadata and
CI are unavailable.

Create a release from a clean, up-to-date `main` branch:

```bash
node scripts/bump-version.mjs patch
# Review the generated commit and annotated tag, then use the exact tag printed:
git push --atomic origin main v0.0.1
```

The argument may be `major`, `minor`, `patch`, or an explicit higher
`MAJOR.MINOR.PATCH`. The script synchronizes `VERSION`, the frontend package
metadata, and the lockfile, then creates the release commit and tag. It never
pushes on the user's behalf. A main build displays the base version plus its
short commit SHA; a release-tag build displays the clean release version.

### Deployment security checklist

- Keep `.env` outside Git and restrict who can read it.
- Expose only the TLS reverse proxy; do not publish PostgreSQL or FastAPI.
- Use a unique random database password and a session secret of at least 32
  bytes.
- Trust `X-Forwarded-For` only from the exact networks in
  `TRUSTED_PROXY_CIDRS`.
- Keep the UI and API on one origin when possible. If they must be separate,
  list only the UI's exact origin in `CORS_ORIGINS`.
- Back up the `vks-pgdata` volume before host or database maintenance.
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
cd data_updater
python -m pip install -r requirements-dev.txt
APP_ENV=dev BACKGROUND_UPDATER_ENABLED=false \
  uvicorn main:app --host 0.0.0.0 --port 8000
```

PowerShell:

```powershell
Set-Location data_updater
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
   `data_updater/generate_admin_password_hash.py`.
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
cd data_updater
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

### Administrator-only endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/auth/logout` | End the current administrator session |
| `GET` | `/v1/updater/status` | Process-local updater and cooldown status |
| `POST` | `/v1/channels` | Validate and add a YouTube channel |
| `POST` | `/v1/channels/{id}/videos/refresh` | Refresh metadata without deleting setlists |
| `POST` | `/v1/videos/{id}/songs/reload` | Re-fetch comments and rerun extraction |

Browser mutations require both the signed administrator cookie and the
session's `X-CSRF-Token`.

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
| `TRUSTED_PROXY_CIDRS` | empty | Proxies allowed to provide client IPs |
| `CORS_ORIGINS` | empty | Exact credentialed cross-origin UI origins |
| `DATA_UPDATE_INTERVAL` | `300` | Worker heartbeat; only due work calls YouTube |
| `UPDATE_STEADY_SCAN_INTERVAL` | `21600` | Normal per-channel discovery interval |
| `UPDATE_MAX_COMMENT_SCRAPES` | `3` | Comment scrapes per update cycle |
| `UPDATE_YOUTUBE_COOLDOWN_SECONDS` | `21600` | Persisted cooldown after a likely block |
| `LLM_CLEANING_ENABLED` | `false` | Optional post-regex cleanup |

The complete list and explanatory comments live in [`.env.example`](.env.example).

## How the pipeline behaves

1. A tracked channel is discovered through bounded Streams and Videos playlist
   pages.
2. Flat-list snapshots preserve stable metadata and approximate dates without
   a per-video request fan-out.
3. Karaoke candidates enter a separate, paced comment-analysis queue.
4. The analyzer prefers pinned and uploader comments, extracts timestamp/title
   pairs, and replaces a video's song list only after a successful analysis.
5. Exact metadata can upgrade approximate values; later sparse observations
   never erase richer snapshots or a previous successful setlist.
6. Suspected YouTube blocking aborts remaining calls and persists a cooldown so
   a restart cannot bypass it.

Detailed design decisions are recorded in [PLAN.md](PLAN.md) and scraper payload
notes in [data_updater/NOTE.md](data_updater/NOTE.md).

## Tests and CI

Backend:

```bash
cd data_updater
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
PostgreSQL 18 after all Flyway migrations, both production image builds,
frontend lint, and the production frontend build. The separate deployment
workflow is limited to canonical-repository `main` and version-tag pushes.

## Project layout

```text
vtuber-karaoke-search/
├── .devcontainer/          # Python 3.12 + Node 22 editor environment
├── .github/workflows/      # CI and gated homelab deployment
├── data_updater/           # FastAPI API, auth, updater, scrapers, tests
├── db/migrations/          # Flyway V1–V9 schema history (source of truth)
├── frontend/               # React UI and production nginx proxy
├── scripts/                # Repository security checks
├── CONTRIBUTING.md         # Contribution workflow
├── SECURITY.md             # Private vulnerability-reporting guidance
├── LICENSE                 # MIT license for project-authored code
├── docker-compose.dev.yml  # Development database and Dev Container
└── docker-compose.yml      # Production homelab stack
```

## Contributing and project status

Phases 0–8 are implemented: pipeline, extraction, search API/UI, scheduler
hardening, authentication, guest limits, public-service pages, deployment
hardening, and public documentation. Rapid development continues, so database
and API compatibility are not guaranteed yet.

Before opening a pull request, read [CONTRIBUTING.md](CONTRIBUTING.md),
[AGENTS.md](AGENTS.md), and [PLAN.md](PLAN.md).

## Legal and removal requests

Setlist stores factual metadata and links to public YouTube pages; it does not
host the linked performances. Rights to videos, audio, thumbnails, names, and
other creative material remain with their respective owners.

Rights holders and channel operators can request a correction, channel
exclusion, or removal through
[GitHub Issues](https://github.com/yutinglia/vtuber-karaoke-search/issues).
Do not post private identity documents in a public issue.

## License

Setlist is released under the [MIT License](LICENSE). You may use, modify,
redistribute, sublicense, or sell copies of the project as long as the
copyright and license notice is retained.

Third-party packages, fonts, service APIs, linked media, and extracted metadata
remain subject to their own licenses and terms.
