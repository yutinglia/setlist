# Setlist frontend

[Project README](../README.md) ·
[繁體中文 README](../README.zh-Hant.md)

Vite + React + TypeScript UI for public Setlist search/browse and protected
single-administrator operations.

## Stack

- React 19 + Vite + TypeScript 6
- TanStack Router + TanStack Query
- Zod (route search-param schemas)
- Zustand (locale, theme, and recent searches only)
- Paraglide (`en` / `zh-hant` / `ja`)
- Tailwind CSS v4 + shadcn/ui

TypeScript stays on the latest compatible 6.x release. Dependabot intentionally
ignores the TypeScript 7 semver-major update until Vite, TanStack Router, the
Paraglide generator, and the production build have been compatibility-tested
together.

## Run (dev)

Terminal 1 — API (from repo root):

```bash
cd backend
APP_ENV=dev BACKGROUND_UPDATER_ENABLED=false uvicorn main:app --host 0.0.0.0 --port 8000
```

The Vite proxy forwards `/v1`, so the browser uses same-origin API paths. Copy
the root `.env.example` to the ignored root `.env` and configure an
administrator password hash/session secret only when testing protected
features. Guest search and browse do not require authentication.

Terminal 2 — UI:

```bash
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>.

### API base URL

| Mode | Behavior |
|------|----------|
| `npm run dev` (default) | Leave `VITE_API_BASE_URL` unset; Vite proxies `/v1` → `http://127.0.0.1:8000` |
| Custom / preview | Set `VITE_API_BASE_URL=http://localhost:8000` (see `.env.example`) and add the UI's exact origin to backend `CORS_ORIGINS` |

`VITE_PUBLIC_SITE_URL` supplies the absolute Open Graph URL during a standalone
frontend build. Production Compose maps its required `PUBLIC_SITE_URL` value to
that build argument.

The footer version comes from `VITE_APP_VERSION`, an exact `v*` Git tag, the
tracked root `VERSION` file, or the synchronized package version, in that order.
These fallbacks keep standalone and Docker builds versioned without CI or a
`.git` directory. The footer source button uses `VITE_SOURCE_URL`.

Management controls are based on the authenticated session returned by the API,
not a frontend build flag. The backend always enforces administrator
authorization and CSRF protection. Guests can search and browse but cannot view
updater status or call mutation endpoints. The guest UI does not poll updater
status in the background.

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Vite dev server (port 5173); runs `generate:i18n` first via `predev` |
| `npm run build` | Typecheck + production build |
| `npm run lint` | Oxlint static checks |
| `npm run preview` | Preview production build |
| `npm run check:i18n` | Verify locale keys and message placeholders stay in sync |
| `npm run generate:i18n` | Recompile Paraglide from `messages/*.json` into `src/paraglide/` |
| `npx @tanstack/router-cli generate` | Regenerate `src/routeTree.gen.ts` if needed |

## Production container

`frontend/Dockerfile` is built from the repository root so the final
unprivileged nginx image includes the top-level MIT license. The container
proxies `/v1` to `backend:8000`, provides SPA route fallback, applies
browser security headers, and caches fingerprinted assets. The root production
Compose stack binds it to
`${FRONTEND_BIND_ADDRESS:-127.0.0.1}:${FRONTEND_PORT:-8080}`. Keep loopback
when the TLS reverse proxy is on the same host. For a proxy on another machine,
bind only the server's private LAN interface and restrict that port to the
proxy.

## Routes

| Path | API |
|------|-----|
| `/` | Submit-only `GET /v1/songs/search`; 500 ms debounced `GET /v1/songs/suggestions` while typing (both support optional channel/type/date filters) |
| `/songs/$songId` | `GET /v1/songs/{id}` |
| `/channels` | `GET /v1/channels` |
| `/channels/new` | Administrator-only `POST /v1/channels` |
| `/channels/$channelId` | `GET /v1/channels/{id}/videos`; administrator refresh control |
| `/videos/$videoId` | `GET /v1/videos/{id}` + `/songs`; administrator reload control |
| `/admin/login` | `GET /v1/auth/session`; `POST /v1/auth/login` |
| `/status` | Administrator-only `GET /v1/updater/status` |
| `/summary` | `GET /v1/report/summary` |
| `/how-to-use` | Public search, browsing, timestamp, and channel-request guide |
| `/about` | Project purpose and source link |
| `/terms` | Terms of service |
| `/privacy` | Privacy notice |
| `/copyright` | Copyright and removal requests |

Administrator controls within channel and video routes call:

- `POST /v1/channels`
- `POST /v1/channels/{id}/videos/refresh`
- `POST /v1/videos/{id}/songs/reload`
- `POST /v1/auth/logout`

Mutation requests use the CSRF token returned by the authenticated session.

## Localization

Source messages live in `messages/en.json`, `messages/zh-hant.json`, and
`messages/ja.json`. `npm run generate:i18n` compiles them into
`src/paraglide/`. Update all source files whenever user-visible copy changes.

## Public metadata

- `VITE_SOURCE_URL` sets the project source/contact base.
- `VITE_CHANNEL_REQUEST_URL` sets the host-specific guest contact link for
  channel requests. It accepts `http(s)`, `mailto:`, or a same-origin path and
  falls back to `VITE_SOURCE_URL/issues/new`.
- `VITE_PUBLIC_SITE_URL` sets the canonical Open Graph origin.
- `VITE_APP_VERSION` optionally overrides the footer build version.
- `public/og.png` is the social preview image.

Production Compose maps its required `PUBLIC_SITE_URL` to the frontend build.
The production build derives canonical URLs, structured data, `robots.txt`,
`sitemap.xml`, and the web app manifest from that origin. Public routes update
their title, description, and social metadata in the browser; search/filter
views and administrator-only routes are marked `noindex`.
Do not put secrets in any `VITE_*` variable; Vite embeds them in public browser
assets.
