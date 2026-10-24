# CLAUDE.md

Telegram Mini App for AI-powered food photo analysis and calorie tracking. Monorepo:

- **`backend/`** — Python 3.12, FastAPI, Neon PostgreSQL, deployed on Fly.io
- **`frontend/`** — React 19, TypeScript 5.9, Vite 8, Bun, Orval + TanStack Query, Tailwind CSS v4, deployed on Vercel

See `backend/CLAUDE.md` and `frontend/CLAUDE.md` for detailed commands, architecture, and code style.

## Root Commands

```bash
make dev              # Start both backend (port 8000) and frontend (port 3000)
make test             # Run all tests (backend + frontend)
make lint             # Lint + typecheck both (runs each side's `make check`)
make format           # Format both
make docker-dev       # Full stack via Docker Compose
```

## CI/CD

GitHub Actions. Merging to `main` does not deploy:
- `backend-ci.yml`, `frontend-ci.yml` — path-filtered CI on PRs and pushes to `main`
- `release-please.yml` — keeps a release PR open from Conventional Commits (`feat:`, `fix:`; `chore:` is left out of the changelog); merging it bumps `backend/pyproject.toml`, `backend/uv.lock`, `frontend/package.json` and `CHANGELOG.md` and publishes `vX.Y.Z`
- `deploy.yml` — on a published release (or manual dispatch with an existing tag, for rollback): waits for CI on the release commit, builds `ghcr.io/<repo>:vX.Y.Z`, deploys it to Fly.io and the frontend to Vercel (`frontend/vercel.json` turns off Vercel's own Git deploys of `main`; PR previews still run)
- `dependabot-auto-merge.yml` — squash-merges Dependabot uv/bun patch and minor bumps once every other workflow on the PR passed; majors and GitHub Actions bumps wait for a human

## Database

Neon PostgreSQL. Schema in `backend/infra/schema.sql`. Set `DATABASE_URL` env var.
