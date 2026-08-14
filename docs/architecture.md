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

Administrator channel ingest has a durable cooldown fallback. `ChannelCreator`
continues to resolve healthy requests synchronously, but persists normalized
URLs in `channel_ingest_queue` when the shared or database cooldown is active;
that transaction makes no YouTube call and does not invalidate public caches.
At the start of a later updater cycle, `DataUpdater` resolves pending rows FIFO
under the existing process/PostgreSQL YouTube lock and administrator pacing.
Creating the channel and completing its queue row share one transaction. A
block records the attempt and global cooldown while leaving the row pending;
cancellation or a crash rolls the whole item back for retry.

## Optional Redis or Valkey

Set `CACHE_URL` to any compatible Redis URL. Redis and Valkey use the same
adapter because Valkey accepts existing Redis client libraries. With no URL,
the container injects a no-op backend and opens no cache connection.

Public search, catalog, and summary reads are serialized as validated Pydantic JSON.
Cache keys contain a schema version and a hash of canonical parameters.
Commits that can change public data invalidate all three namespaces; no-op
channel and cooldown-only commits do not. Search, catalog, and report entries use
15-minute, 1-hour, and 5-minute stale-data safety bounds. Read, write,
invalidation, and health-check failures are fail-open: PostgreSQL serves the
request, a short failure backoff avoids repeated cache timeouts, and failure
logging is rate-limited. A namespace whose invalidation failed stays bypassed
until cleanup succeeds, so a longer TTL cannot revive a response made stale by
a committed mutation. API startup also performs fail-open namespace cleanup to
cover cache entries left by an earlier process.

| Namespace | Public GET endpoints | Default TTL |
| --- | --- | --- |
| `search` | `/v1/songs/search`, `/v1/songs/suggestions` | 15 minutes |
| `catalog` | Song, contributor, channel, video, and video-song browse/detail routes | 1 hour |
| `report` | `/v1/report/summary` | 5 minutes |

`/v1/health` remains live, authentication and updater-status responses are
`no-store`, and mutations are never response-cached. Authenticated API
responses also receive `Cache-Control: no-store` from middleware. The frontend
proxy does not add an HTTP response cache for `/v1`; Valkey is the shared
server-side cache, while TanStack Query owns the per-browser server-state
cache.

For the bundled optional service:

```bash
CACHE_URL=redis://cache:6379/0 docker compose --profile cache up -d
```

The cache is not published to the host and persistence is disabled because it
contains derived response data only. The bundled 128 MiB container configures
an 80 MiB Valkey `maxmemory`, `allkeys-lru` eviction, and a 5% aggregate client
memory limit so the process evicts replaceable keys before reaching its
container limit without relying on swap.

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

The hero and compact header searches share `SearchForm`'s suggestion combobox,
including debounce, keyboard navigation, and ARIA state. The home route omits
the compact header search so it exposes only the hero search control.
