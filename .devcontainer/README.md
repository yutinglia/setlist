# Dev Container

Reopen this repo in a container (Cursor/VS Code: **Dev Containers: Reopen in Container**).

## Services

| Service | Role |
|---------|------|
| `app` | Python 3.12 + Node 22 workspace; your IDE attaches here |
| `db` | Postgres 18 (`vks_db` / `vks_db_user` / `vks_db_pwd`) |
| `flyway` | Applies `db/migrations` once, then exits |

Python packages are baked into the development image. On first create,
`npm ci` installs frontend packages into a Linux named volume. Keeping
`node_modules` outside the Windows bind mount prevents host/container package
and symlink conflicts.

The container does not start application processes in lifecycle hooks. This
keeps container startup deterministic and makes server output visible in the
terminal that owns each process.

## After attach

Start the API and UI in separate terminals:

```bash
# API (auto-reloads on Python changes)
cd data_updater && APP_ENV=dev BACKGROUND_UPDATER_ENABLED=false uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# UI
cd frontend && npm run dev
```

| URL | Purpose |
|-----|---------|
| http://localhost:8000/v1/health | Health |
| http://localhost:8000/docs | OpenAPI (`APP_ENV=dev`) |
| http://localhost:5173 | Search UI |

Set `BACKGROUND_UPDATER_ENABLED=true` only when you intentionally want the dev
server to scrape. Keeping it false avoids duplicate YouTube work during reloads.

## Database

| Use | URL |
|-----|-----|
| App (async) | `postgresql+asyncpg://vks_db_user:vks_db_pwd@db:5432/vks_db` |
| sqlacodegen (sync) | `postgresql://vks_db_user:vks_db_pwd@db:5432/vks_db` |

Host is `db` inside Compose (not published on the host). From the host:

```bash
docker compose -f .devcontainer/docker-compose.yml exec -T db \
  psql -U vks_db_user -d vks_db
```

## Database without the IDE

From the repo root:

```bash
docker compose -f docker-compose.dev.yml up -d db flyway
```

The `app` service gets Node through a Dev Container feature. Create that
workspace through Cursor/VS Code (or the Dev Container CLI), not through a raw
`docker compose build app`.

`docker-compose.dev.yml` is dedicated to the Dev Container. The root
`docker-compose.yml` is a separate production-oriented stack and does not start
the IDE workspace service.
