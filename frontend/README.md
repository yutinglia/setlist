# Frontend (Phase 6)

Vite + React + TypeScript search UI for the FastAPI v1 API.

## Stack

- React 19 + Vite
- TanStack Router + TanStack Query
- Zod (route search-param schemas)
- Zustand (locale + recent searches only)
- Paraglide (`en` / `zh-hant`)
- Tailwind CSS v4 + shadcn/ui

## Run (dev)

Terminal 1 — API (from repo root):

```bash
cd data_updater
APP_ENV=dev uvicorn main:app --host 0.0.0.0 --port 8000
```

`APP_ENV=dev` enables loose CORS. The Vite proxy also forwards `/v1` so the browser can call same-origin paths.

Terminal 2 — UI:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### API base URL

| Mode | Behavior |
|------|----------|
| `npm run dev` (default) | Leave `VITE_API_BASE_URL` unset; Vite proxies `/v1` → `http://127.0.0.1:8000` |
| Custom / preview | Set `VITE_API_BASE_URL=http://localhost:8000` (see `.env.example`) and ensure `CORS_ORIGINS` includes the UI origin when not in `APP_ENV=dev` |

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Vite dev server (port 5173) |
| `npm run build` | Typecheck + production build |
| `npm run preview` | Preview production build |
| `npx @tanstack/router-cli generate` | Regenerate `src/routeTree.gen.ts` if needed |

## Routes

| Path | API |
|------|-----|
| `/` | `GET /v1/songs/search` |
| `/songs/$songId` | `GET /v1/songs/{id}` |
| `/channels` | `GET /v1/channels` |
| `/channels/$channelId` | `GET /v1/channels/{id}/videos` |
| `/videos/$videoId` | `GET /v1/videos/{id}/songs` |
