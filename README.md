# Calorie Track AI Bot

[![Backend CI](https://github.com/gofrolist/calorie-track-ai-bot-api/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/gofrolist/calorie-track-ai-bot-api/actions/workflows/backend-ci.yml)
[![Deploy](https://github.com/gofrolist/calorie-track-ai-bot-api/actions/workflows/deploy.yml/badge.svg)](https://github.com/gofrolist/calorie-track-ai-bot-api/actions/workflows/deploy.yml)
[![Frontend CI](https://github.com/gofrolist/calorie-track-ai-bot-api/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/gofrolist/calorie-track-ai-bot-api/actions/workflows/frontend-ci.yml)

A full-stack application for tracking calories using AI-powered photo analysis with multi-photo support and enhanced meal history features.

## Features

### Multi-Photo Meal Tracking
- Upload up to 5 photos per meal for better calorie estimation
- AI-powered calorie and macronutrient analysis using OpenAI `gpt-5-mini` (configurable via `OPENAI_MODEL`)
- Automatic macronutrient breakdown (protein, carbs, fats)
- Instagram-style photo carousel with thumbnails

### Enhanced Meal History
- Calendar-based meal navigation with date range filtering
- Inline meal card expansion
- Meal editing and deletion with confirmation
- Responsive design for mobile devices

### Telegram Integration
- Telegram Bot for photo submission, with media group support for multi-photo uploads
- Telegram Mini App for meal management
- Background AI estimation processing

### Technical Features
- FastAPI backend with automatic OpenAPI documentation
- React frontend with TypeScript
- Neon PostgreSQL database
- Tigris S3-compatible storage
- Redis (Upstash) for background job queuing

## Repository Structure

This repository is organized into backend and frontend components:

- `backend/` - FastAPI application with Telegram bot functionality
- `frontend/` - React-based Telegram Mini App with meal tracking interface

## Quick Start

### Backend Development

See [backend/README.md](backend/README.md) for detailed backend setup instructions.

```bash
# Install dependencies
cd backend && uv sync

# Start development server (port 8000)
cd backend && make dev
```

### Frontend Development

See [frontend/README.md](frontend/README.md) for detailed frontend setup instructions.

```bash
# Install dependencies
cd frontend && bun install

# Start development server (port 3000)
cd frontend && bun run dev
```

## Available Commands

```bash
# From the repository root
make dev                # Start backend (port 8000) and frontend (port 3000)
make test               # Run backend and frontend tests
make lint               # Lint + typecheck backend and frontend
make format             # Format backend and frontend
make docker-dev         # Start the full stack via Docker Compose

# Backend development (run from backend folder)
cd backend
make dev                # Start dev server with hot reload
make worker             # Start background estimate worker
make test               # Run all tests
make test-unit          # Run tests excluding tests/integration/
make check              # Lint (ruff) + typecheck (pyright)
make format             # Format code with ruff
make openapi-export     # Export OpenAPI spec to frontend/openapi.json

# Or run commands directly with uv
cd backend
uv sync --all-extras    # Install dependencies
uv run uvicorn calorie_track_ai_bot.main:app --reload  # Start dev server
uv run pytest           # Run all tests
uv run ruff check       # Run linting
uv run pyright          # Run type checking

# Frontend development (run from frontend folder)
cd frontend
bun run dev             # Start Vite dev server
bun run test            # Run unit tests (Vitest)
bun run check           # Type-check + lint + format check
bun run api:gen         # Regenerate API client (Orval) from openapi.json

# Deployment (requires flyctl; normally done by CI)
cd backend
flyctl deploy           # Deploy to Fly.io
```

## Architecture

- **Backend**: FastAPI on Fly.io
- **Database**: Neon PostgreSQL
- **Queue**: Redis (Upstash)
- **Storage**: Tigris (S3-compatible)
- **AI**: OpenAI GPT-5-mini for image analysis
- **Frontend**: React Telegram Mini App on Vercel

## CI/CD Workflows

This repository uses optimized GitHub Actions workflows that only run when relevant files change:

### Workflow Strategy

- **`backend-ci.yml`** - Backend CI (ruff lint, ruff format check, pyright, pytest)
  - Triggers: Pull requests and pushes to `main` that touch `backend/**` or the workflow file
  - Skips: Frontend-only changes

- **`frontend-ci.yml`** - Frontend CI (Bun: verify generated API client is up to date, Vitest, build)
  - Triggers: Pull requests and pushes to `main` that touch `frontend/**` or the workflow file; manual dispatch

- **`release-please.yml`** - Release PR from Conventional Commits
  - Triggers: Pushes to `main`; manual dispatch
  - Merging the release PR bumps the versions, updates `CHANGELOG.md`, and publishes a `vX.Y.Z` release

- **`deploy.yml`** - Production deploy (Fly.io backend, Vercel frontend)
  - Triggers: A published release; manual dispatch with an existing tag (redeploy or rollback)
  - Waits for CI to pass on the release commit, then builds and pushes `ghcr.io/<repo>:vX.Y.Z` and deploys it

- **`dependabot-auto-merge.yml`** - Squash-merges Dependabot uv/bun patch and minor bumps after every other workflow on the PR passes
  - Majors and GitHub Actions bumps wait for review

### Benefits

✅ **Efficient**: No unnecessary backend builds for frontend changes
✅ **Fast**: Parallel execution of backend and frontend CI when both change
✅ **Cost-effective**: Reduced GitHub Actions minutes usage
✅ **Simple**: Clear, focused workflows without duplication
✅ **Scalable**: Easy to add more workflows as the project grows

## Documentation

- [Backend Documentation](backend/README.md)
- [Frontend Documentation](frontend/README.md)
- [GitHub Secrets Setup](docs/GITHUB_SECRETS.md)
