# Backend and frontend dependency architecture

## Backend composition

`backend/container.py` is the composition root. It owns process-scoped
resources (database engine/pool, optional cache client, authentication service,
updater status/trigger, YouTube operation coordinator, cooldown, scraper
factory, scrape executor, and optional LLM cleaner) and constructs
request-scoped use-cases around one SQLAlchemy session.

FastAPI dependencies in `backend/deps.py` resolve the app container from
`app.state`, open a session, and provide query or command services. Routers do
not create repositories, Redis clients, or scraper implementations.

The boundaries intentionally use:

- constructor injection for service collaborators;
- a composition root for concrete infrastructure selection;
- repository pattern for database access;
- application/query services for HTTP use-cases;
- strategy/factory adapters for blocking scraper execution;
- cache-aside for optional public-query caching;
- null object (`NullCacheBackend`) when caching is disabled.

`DataUpdater`, `ChannelCreator`, and `StoredDataReanalyzer` retain transaction
ownership. Cache invalidation runs only after their commits. Repositories still
never commit.

## Optional Redis or Valkey

Set `CACHE_URL` to any compatible Redis URL. Redis and Valkey use the same
adapter because Valkey accepts existing Redis client libraries. With no URL,
the container injects a no-op backend and opens no cache connection.

Public catalog and summary reads are serialized as validated Pydantic JSON.
Cache keys contain a schema version and a hash of canonical parameters.
Mutations invalidate catalog and report namespaces. Read, write, invalidation,
and health-check failures are fail-open: PostgreSQL serves the request and the
failure is rate-limited in logs.

For the bundled optional service:

```bash
CACHE_URL=redis://cache:6379/0 docker compose --profile cache up -d
```

The cache is not published to the host and persistence is disabled because it
contains derived response data only.

## Testing and replacement

Build an `ApplicationContainer` with replaced immutable settings and injected
fakes, or override the narrow FastAPI provider for a route test. Unit tests use
`MemoryCacheBackend`, injected scraper factories/executors, and service fakes;
they do not patch production module globals.

## Frontend

`createApiClient` accepts a base URL and `fetch` implementation. `main.tsx`
creates the production instance and injects it through `ApiProvider` and the
TanStack Router context. React hooks use the provider; route guards use router
context. This is sufficient DI for the current frontend: TanStack Query owns
server state, Zustand owns UI preferences, and components receive ordinary
props.
