# Setlist backend

The backend is a FastAPI service that searches PostgreSQL catalog data and runs
the paced yt-dlp ingestion/analyzer pipeline. PostgreSQL is the source of truth.
Redis or Valkey can optionally cache public read responses, but is never
required for startup or correctness.

Run commands in this directory because imports intentionally use `backend/` as
their working-directory root.

## Local development

Start and migrate PostgreSQL from the repository root:

```bash
docker compose -f docker-compose.dev.yml up -d db flyway
```

Then install and run the API:

```bash
python -m pip install -r requirements-dev.txt
APP_ENV=dev BACKGROUND_UPDATER_ENABLED=false \
  uvicorn main:app --host 0.0.0.0 --port 8000
```

On PowerShell, set the variables before starting Uvicorn:

```powershell
$env:APP_ENV = "dev"
$env:BACKGROUND_UPDATER_ENABLED = "false"
uvicorn main:app --host 0.0.0.0 --port 8000
```

Use `GET /v1/health` for health and `/docs` for OpenAPI in development.
Administrator login remains fail-closed unless `ADMIN_PASSWORD_HASH` and
`SESSION_SECRET` are configured.

To execute one production-equivalent update path without the periodic loop:

```bash
python run_updater_once.py
```

## Architecture and dependency injection

`container.ApplicationContainer` is the composition root. It owns process-wide
resources and policies, while creating request-scoped services around one
SQLAlchemy session.

```text
FastAPI route
  -> dependency provider in deps.py
    -> query/use-case service
      -> repository or infrastructure port
        -> PostgreSQL / Redis-compatible cache / yt-dlp
```

The principal design boundaries are:

- app factory and composition root for resource lifetime and wiring;
- constructor injection for authentication, repositories, cache, scraper
  factories/executors, updater status, cooldown, and operation coordination;
- repository pattern for SQL access and mapping;
- application query/service layer so routers do not know cache serialization;
- factory and strategy patterns around synchronous yt-dlp components;
- cache-aside plus a null object for the optional response cache;
- explicit transaction ownership in `DataUpdater`, `ChannelCreator`, and
  `StoredDataReanalyzer`.

Concrete infrastructure selection belongs in `container.py`. Tests should
inject a fake through a constructor, an `ApplicationContainer`, or a narrow
FastAPI dependency override instead of changing process globals.

See [the architecture guide](../docs/architecture.md) for the detailed
dependency and replacement rules.

## Optional Redis or Valkey cache

Leave `CACHE_URL` empty (the default) to inject `NullCacheBackend`. This makes
no cache connection and sends every read to PostgreSQL.

To use the bundled Valkey service, run from the repository root:

```bash
CACHE_URL=redis://cache:6379/0 docker compose --profile cache up -d
```

PowerShell:

```powershell
$env:CACHE_URL = "redis://cache:6379/0"
docker compose --profile cache up -d
```

The cache service is internal-only and has persistence disabled because it
stores derived responses. The application:

- caches public catalog and summary query results;
- validates cached JSON back into Pydantic DTOs;
- invalidates catalog/report namespaces after successful mutations;
- continues against PostgreSQL if cache reads, writes, invalidation, or health
  checks fail;
- reports `disabled`, `ok`, or `unavailable` in `/v1/health`.

Relevant settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `CACHE_URL` | empty | Redis-compatible URL; empty disables caching |
| `CACHE_KEY_PREFIX` | `setlist` | Deployment-specific key namespace |
| `CACHE_DEFAULT_TTL_SECONDS` | `60` | Public response TTL |
| `CACHE_CONNECT_TIMEOUT_SECONDS` | `1` | Initial connection timeout |
| `CACHE_SOCKET_TIMEOUT_SECONDS` | `1` | Cache operation timeout |

Do not cache authenticated responses. They must remain `Cache-Control:
no-store`.

## Tests and checks

Unit tests use injected fakes and do not need Redis/Valkey:

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

PostgreSQL integration tests run when `TEST_DATABASE_URL` points to a migrated
test database. `services/yt_scraper/test.py` is a manual live-network smoke
script and is intentionally not part of pytest.

The cache test suite uses `MemoryCacheBackend` and failing fakes to cover hits,
canonical keys, invalidation, and fail-open behavior. A real Redis or Valkey
adapter can be supplied without changing the query services because both
implement the same injected `CacheBackend` port.

## Directory map

```text
backend/
├── main.py                 # app factory and background-worker lifespan
├── container.py            # composition root and dependency wiring
├── config.py               # validated environment settings snapshots
├── deps.py                 # FastAPI dependency providers
├── db/                     # engine/session factory and generated ORM
├── models/                 # Pydantic API/domain DTOs
├── repositories/           # SQL reads and writes; never commit
├── routers/v1/             # thin HTTP adapters
├── services/               # use cases, policies, ports, and adapters
├── tests/                  # pytest unit and PostgreSQL integration tests
├── run_updater_once.py     # one-shot updater entry point
└── reanalyze_stored_data.py
```

Database schema changes start in `../db/migrations/`; do not treat the generated
`db/models.py` as the schema source of truth.
