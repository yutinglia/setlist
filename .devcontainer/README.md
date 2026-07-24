# Dev Container

Reopen this repo in a container (Cursor/VS Code: **Dev Containers: Reopen in Container**).

## Services

| Service | Role |
|---------|------|
| `app` | Python 3.12 workspace (`sleep infinity`); your IDE attaches here |
| `db` | Postgres 18 (`vks_db` / `vks_db_user` / `vks_db_pwd`) |
| `flyway` | Applies `db/migrations` once, then exits |

On create, `pip install -r data_updater/requirements.txt` runs automatically.

## After attach

```bash
cd data_updater
uvicorn main:app --host 0.0.0.0 --port 8000
```

| URL | Purpose |
|-----|---------|
| http://localhost:8000/v1/health | Health |
| http://localhost:8000/docs | OpenAPI (`APP_ENV=dev`) |
| http://localhost:5173 | Search UI (`cd frontend && npm run dev`) |

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
