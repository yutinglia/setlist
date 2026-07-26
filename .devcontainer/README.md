# Dev Container

[Project README](../README.md) ·
[繁體中文 README](../README.zh-Hant.md)

The Dev Container provides a reproducible Python 3.14, Node 26, PostgreSQL 18,
and Flyway development environment.

## Open the workspace

1. Open the repository in VS Code or Cursor.
2. Run **Dev Containers: Reopen in Container**.
3. Wait for `postCreateCommand` to run `npm ci` and verify the Python runtime.
4. Open <http://localhost:5173>.

`postStartCommand` launches FastAPI and Vite in the background with hot reload.
Ports 8000 and 5173 are forwarded to the host.

| Service | Role |
|---------|------|
| `app` | Editor workspace with Python 3.14 and Node 26 |
| `db` | PostgreSQL 18 development database |
| `flyway` | Applies every migration in `db/migrations/`, then exits |

Frontend `node_modules` uses a Linux named volume so the Windows bind mount
does not introduce platform or symlink conflicts.

## URLs and logs

| URL | Purpose |
|-----|---------|
| <http://localhost:5173> | Search UI |
| <http://localhost:5173/admin/login> | Administrator sign-in |
| <http://localhost:8000/v1/health> | API and database health |
| <http://localhost:8000/docs> | OpenAPI in `APP_ENV=dev` |

Follow service logs inside the container:

```bash
tail -f /tmp/vtuber-karaoke-search-dev/backend.log
tail -f /tmp/vtuber-karaoke-search-dev/frontend.log
```

The lifecycle script records PIDs beside those logs and avoids starting a
duplicate process after an editor reconnect.

## Scraping policy

`docker-compose.dev.yml` sets `BACKGROUND_UPDATER_ENABLED=false`. The API and UI
start automatically, but opening the workspace does not automatically scrape
YouTube.

Use the one-shot production-equivalent path when testing updater behavior:

```bash
cd /workspace/backend
python run_updater_once.py
```

Set `BACKGROUND_UPDATER_ENABLED=true` and rebuild the container only when a
long-running development scraper is intentional. Avoid running multiple
reload-enabled scraper processes against the same database.

## Administrator login

Development mode does not bypass authentication. Without an administrator hash
and session secret, guest search/browse works and login fails closed.

To test admin features:

1. From `backend/`, run `python generate_admin_password_hash.py`.
2. Create an ignored `/workspace/.env` with `ADMIN_USERNAME`,
   `ADMIN_PASSWORD_HASH`, and a random `SESSION_SECRET` of at least 32 bytes.
3. Keep `AUTH_COOKIE_SECURE=false` for local HTTP only.
4. Rebuild/reopen the Dev Container so Compose reads the new values.

Put an Argon2 hash in single quotes in `.env` because it contains `$`.

## Database

| Caller | Connection |
|--------|------------|
| App inside Compose | `postgresql+asyncpg://vks_db_user:vks_db_pwd@db:5432/vks_db` |
| sqlacodegen inside Compose | `postgresql://vks_db_user:vks_db_pwd@db:5432/vks_db` |
| Host development tools | `postgresql://vks_db_user:vks_db_pwd@127.0.0.1:5432/vks_db` |

The development database is published on host loopback only. Connect through
Docker from the repository root:

```bash
docker compose -f docker-compose.dev.yml exec -T db \
  psql -U vks_db_user -d vks_db
```

These credentials are local-development defaults. The production Compose stack
requires a separate password and never publishes PostgreSQL.

## Database without the editor

From the repository root:

```bash
docker compose -f docker-compose.dev.yml up -d db flyway
```

The `app` service receives Node through a Dev Container feature. Create the
workspace through VS Code/Cursor or the Dev Container CLI rather than treating
`docker-compose.dev.yml` as a standalone production application.

The root `docker-compose.yml` is a separate production stack with the static
frontend proxy, private FastAPI service, Flyway, and PostgreSQL.
