# Contributing

Thank you for helping improve Setlist. It is maintained as a personal homelab
project, and focused changes with clear tests are easier to review than broad
rewrites.

Start with [README.md](README.md) (or
[README.zh-Hant.md](README.zh-Hant.md)), then read [AGENTS.md](AGENTS.md) for
the architecture rules that keep the updater and database safe.

## Development setup

The preferred setup is the Dev Container:

1. Open the repository in VS Code or Cursor.
2. Run **Dev Containers: Reopen in Container**.
3. Wait for the database migrations and dependency installation.
4. Open <http://localhost:5173>.

The API and UI start automatically. Background scraping is disabled by default.
Manual setup instructions are in [README.md](README.md#local-development-without-a-dev-container).

## Before changing code

- Check [PLAN.md](PLAN.md) and open GitHub issues for current scope and design
  decisions.
- Keep the existing FastAPI, Flyway, SQLAlchemy, yt-dlp, and React/Vite
  architecture unless a rewrite has been discussed first.
- Treat `db/migrations/` as the schema source of truth. Add a new Flyway
  migration instead of rewriting applied migrations.
- Run backend commands with `backend/` as the working directory.
- Keep TypeScript on the latest compatible 6.x version. TypeScript 7 is
  intentionally deferred until the Vite, TanStack, and generated-code toolchain
  has a dedicated compatibility change and full validation.
- Keep blocking yt-dlp calls off the async event loop.
- Preserve updater-owned transactions and the existing pacing/cooldown rules.
- Do not weaken administrator authorization, CSRF, trusted-proxy handling,
  guest limits, or credentialed CORS.

## Tests

Backend:

```bash
cd backend
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

Credential scan:

```bash
python scripts/check_secrets.py
```

Run tests that are proportional to the change. Schema and repository changes
should be verified against PostgreSQL after all Flyway migrations.

## Pull requests

A useful pull request:

- explains the user-visible outcome and why it is needed;
- stays focused on one concern;
- includes tests for behavior changes;
- updates English, Traditional Chinese, and Japanese UI copy together;
- updates relevant Markdown and environment samples;
- calls out schema, configuration, or deployment changes;
- contains no generated caches, local databases, `.env`, or credentials.

Generated ORM models should match the migrations. Generated Paraglide and
TanStack Router output should match their source messages/routes.

## Security and privacy

Never commit API keys, database passwords, session secrets, administrator
password hashes used by a real deployment, cookies, or private user data.
Examples must use empty values or obvious placeholders.

Do not open a public issue containing an unpatched vulnerability or private
identity documents. Follow [SECURITY.md](SECURITY.md) instead.

## Copyright and removals

Corrections and removal requests are welcome. Include the affected public URL
and the requested change, but do not publish private verification material in
an issue. Setlist does not host the linked video or audio.

## License

The project is licensed under the [MIT License](LICENSE). By submitting a
contribution, you agree that it may be distributed under that license and
confirm that you have the right to contribute it.

Do not copy third-party code, fonts, media, or data into the repository unless
its license is compatible and all required notices are preserved.
