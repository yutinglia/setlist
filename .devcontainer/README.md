# Dev Container

Reopen this repo in a container (Cursor/VS Code: **Dev Containers: Reopen in Container**).

## Services

| Service | Role |
|---------|------|
| `app` | Python 3.12 workspace (`sleep infinity`); your IDE attaches here |
| `db` | Postgres 18 (`vks_db` / `vks_db_user` / `vks_db_pwd`) |
| `flyway` | Applies `db/migrations` once, then exits |

On create: installs Python deps and `frontend` npm packages. Node 22 is provided via the Dev Container Node feature.

API (`:8000`) and Vite (`:5173`) are started by the Compose **entrypoint** on every container start (not only `postStartCommand`). That avoids a known Dev Containers issue where background processes started from `postStartCommand` are killed when the `docker exec -t` session exits.

`postStartCommand` still runs the same ensure script as a backup (idempotent).

## After attach

API and search UI should already be up. To restart them yourself:

```bash
bash .devcontainer/ensure-dev-servers.sh
```

Or manually:

```bash
# API (auto-reloads on Python changes)
cd data_updater && APP_ENV=dev uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# UI
cd frontend && npm run dev
```

| URL | Purpose |
|-----|---------|
| http://localhost:8000/v1/health | Health |
| http://localhost:8000/docs | OpenAPI (`APP_ENV=dev`) |
| http://localhost:5173 | Search UI |

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

## Compose without the IDE

From the repo root:

```bash
docker compose -f .devcontainer/docker-compose.yml up -d db flyway
docker compose -f .devcontainer/docker-compose.yml up --build app
```

Root `docker-compose.yml` and `docker-compose.dev.yml` include this file.
