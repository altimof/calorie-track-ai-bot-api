# Development Setup Guide

This guide will help you set up and run the Calorie Track AI Bot application locally for development and testing.

## Prerequisites

Make sure you have the following installed:
- **Bun** (frontend package manager and runtime) - [Install](https://bun.sh/)
- **Python 3.12** - [Download](https://python.org/)
- **uv** (Python package manager) - [Install](https://docs.astral.sh/uv/getting-started/installation/)
- **Docker** (optional, for Redis/MinIO or the full Docker stack)

## Quick Start

### 1. Clone and Setup
```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd calorie-track-ai-bot-api

# Install dependencies
(cd backend && uv sync)
(cd frontend && bun install)
```

### 2. Configure Environment

#### Backend Configuration
Create a `.env` file in the `backend/` directory with your service credentials:

```bash
# Copy the example (backend/env.template is a more detailed alternative)
cp backend/.env.example backend/.env

# Or create manually
nano backend/.env
```

Required environment variables for backend:
```env
# Application
APP_ENV=dev
LOG_LEVEL=INFO

# OpenAI
OPENAI_API_KEY=sk-your-openai-key
OPENAI_MODEL=gpt-5-mini

# Database (Neon PostgreSQL)
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require

# Redis
REDIS_URL=redis://localhost:6379

# Tigris/S3
AWS_ENDPOINT_URL_S3=https://fly.storage.tigris.dev
AWS_ACCESS_KEY_ID=tid_xxxxxx
AWS_SECRET_ACCESS_KEY=tsec_xxxxxx
BUCKET_NAME=your-bucket-name

# Telegram
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
USE_WEBHOOK=false
WEBHOOK_URL=https://your-public-url/bot

# Inline Mode
INLINE_MODE_ENABLED=false
INLINE_HASH_SALT=change-me-inline-hash-salt
INLINE_THROUGHPUT_PER_MIN=60
INLINE_BURST_RPS=5

# Run the estimate/inline workers inside the API process (otherwise run `make -C backend worker`)
ENABLE_WORKER=false
```

The backend loads `backend/.env` automatically (`services/config.py`). The full list of variables is in `backend/src/calorie_track_ai_bot/services/config.py`; feedback notifications additionally read `ADMIN_NOTIFICATION_CHAT_ID` and `FEEDBACK_NOTIFICATIONS_ENABLED`, and dev endpoints read `DEV_ENDPOINTS_ENABLED`.

> Inline mode prerequisites: inline handling is always on (`INLINE_MODE_ENABLED` is defined in config but not read anywhere). Provide a high-entropy `INLINE_HASH_SALT`, and keep `INLINE_THROUGHPUT_PER_MIN` / `INLINE_BURST_RPS` aligned with the 60 requests-per-minute (≈5 rps burst) capacity.

#### Frontend Configuration
Create a `.env.local` file in the `frontend/` directory:

```bash
cd frontend
nano .env.local
```

Frontend environment variables (the only ones read by `frontend/src`):
```env
# API Configuration (defaults to http://localhost:8000)
VITE_API_BASE_URL=http://localhost:8000

# Telegram user ID sent as x-user-id when running outside Telegram (dev only);
# the backend must run with ALLOW_INSECURE_USER_ID_HEADER=true to accept it
VITE_DEV_USER_ID=123456789
```

### 3. Set Up the Database Schema

A fresh Neon (or any Postgres) database starts empty — there is no migration tool, so the schema must be applied manually before first use. This needs `psql` (or paste the file into the Neon console SQL editor instead). `psql` does not read `backend/.env`, so export the same `DATABASE_URL` in your shell first:

```bash
export DATABASE_URL='postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require'
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/infra/schema.sql
```

Skipping this step leaves tables like `users` and `photos` missing, which surfaces as `psycopg.errors.UndefinedTable: relation "users" does not exist` the first time the bot processes a message. `schema.sql` is only safe on an empty database or one already at the current schema — it does not upgrade an older database, so after pulling schema changes apply them by hand as described in [database-schema-changes.md](database-schema-changes.md).

### 4. Start Development Servers

```bash
# Start both backend and frontend
make dev
```

This will start:
- **Backend API**: http://localhost:8000
- **Frontend App**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs

`make dev` does not start the background worker. Either set `ENABLE_WORKER=true` in `backend/.env` or run `make -C backend worker` in another terminal. A Redis instance is required for the queue (for example `docker compose up redis`).

## Development Commands

### Essential Commands (root)
```bash
make dev            # Start backend and frontend dev servers
make test           # Run all tests (backend + frontend)
make lint           # Lint + typecheck both (runs `check` in each)
make format         # Format backend and frontend
make clean          # Clean up temporary files
make docker-dev     # Start all services via Docker Compose
make docker-stop    # Stop Docker containers
make help           # Show all available commands
```

### Backend Commands (`make -C backend <target>` or from `backend/`)
```bash
make dev            # Start only the backend server (port 8000, hot reload)
make worker         # Start the background estimate worker
make test           # Run backend tests
make test-unit      # Unit tests only (ignores tests/integration/)
make check          # Ruff lint + pyright
make openapi-export # Export OpenAPI spec to frontend/openapi.json
```

### Frontend Commands (`make -C frontend <target>` or `bun run` from `frontend/`)
```bash
make dev            # Start only the frontend server (port 3000)
make test           # Run frontend unit tests (vitest)
make check          # Type-check + lint + format check
bun run build       # Build frontend for production
bun run api:gen     # Regenerate API client from openapi.json (Orval)
```

## Testing

### Backend Testing
```bash
# Run all backend tests
make -C backend test

# Run specific test categories
cd backend
uv run pytest tests/services/ -v
uv run pytest tests/api/v1/ -v
uv run pytest tests/integration/ -v
```

### Frontend Testing
```bash
# Run frontend unit tests
make -C frontend test

# Run end-to-end tests (Playwright)
cd frontend && bun run test:e2e
```

## Telegram Bot Setup

### 1. Create a Telegram Bot
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` command
3. Follow the prompts to create your bot
4. Save the bot token you receive

### 2. Configure Webhook (Development)
The bot only receives updates via webhook (there is no polling mode), so the backend must be reachable from the internet (for example through a tunnel). Set `USE_WEBHOOK=true` and `WEBHOOK_URL=https://<public-host>/bot` in `backend/.env`; the webhook is registered on startup, or manually:
```bash
# Start your backend first
make dev-backend

# In another terminal, register the webhook
curl -X POST http://localhost:8000/bot/setup
```

### 3. Test Your Bot
1. Find your bot on Telegram
2. Send `/start` command
3. Send a photo of food to test calorie estimation

## API Testing

### Using the API Documentation
1. Start the backend: `make dev-backend`
2. Open http://localhost:8000/docs
3. Use the interactive Swagger UI to test endpoints

### Using curl
```bash
# Health check
curl http://localhost:8000/health/live

# Database connectivity
curl http://localhost:8000/health/connectivity

# Get webhook info
curl http://localhost:8000/bot/webhook-info

# Test photo upload (example)
curl -X POST http://localhost:8000/api/v1/photos \
  -H "Content-Type: application/json" \
  -d '{"content_type": "image/jpeg"}'
```

## Frontend Development

### Running the Frontend
```bash
# Start frontend development server
make dev-frontend

# Or navigate to frontend directory
cd frontend
bun run dev
```

### Frontend Features
- **Meals** (`/`): Daily meal list with calendar, photo carousel, edit and delete
- **Stats** (`/stats`): Daily calorie and macro charts over a selectable period
- **Goals** (`/goals`): Set and track daily calorie goals
- **Feedback** (`/feedback`): Send feedback to the admins
- **Telegram Integration**: Full WebApp SDK integration

### Frontend Architecture
- **React 19** with TypeScript
- **Vite** for fast development
- **React Router** for navigation
- **TanStack Query** with hooks generated by **Orval** for API communication
- **Tailwind CSS v4** for styling
- **i18next** for internationalization (EN/RU)
- **Telegram WebApp SDK** for bot integration

See `frontend/CLAUDE.md` for details.

## Troubleshooting

### Common Issues

#### Backend Issues
```bash
# Check if backend is running
curl http://localhost:8000/health/live

# Check database connectivity
curl http://localhost:8000/health/connectivity

# Restart backend: stop `make dev-backend` (Ctrl+C) and start it again
```

#### Frontend Issues
```bash
# Clear frontend cache
make -C frontend clean

# Reinstall frontend dependencies
cd frontend
rm -rf node_modules
bun install
```

#### Environment Issues
```bash
# Verify tools are installed
uv --version && bun --version

# Check environment files exist
ls -la backend/.env
ls -la frontend/.env.local
```

### Port Conflicts
If you have port conflicts:
- **Backend**: Change port in `backend/Makefile` (line with `--port 8000`)
- **Frontend**: Change port in `frontend/package.json` (`dev` script, `--port 3000`) and `frontend/vite.config.ts`

### Database Issues
- Ensure your Neon PostgreSQL project is active
- Check that DATABASE_URL is set correctly
- Verify the database schema is up to date (see `backend/infra/schema.sql` and [database-schema-changes.md](database-schema-changes.md))

## Production Deployment

Deployments normally happen from GitHub Actions when the release-please PR is merged: the published `vX.Y.Z` release runs `deploy.yml`, which waits for CI on the release commit and deploys both apps. Run `deploy.yml` manually with an existing tag to redeploy or roll back. Manual deploys:

> **New Neon project?** Apply the schema before the first release is deployed — no workflow runs it: `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/infra/schema.sql` (see [step 3](#3-set-up-the-database-schema)). Without it, the deployed backend starts and passes health checks, but any message the bot processes fails with `relation "users" does not exist`.

> **Deploying your own fork?** Set the `CORS_ORIGINS` secret on your backend to your frontend's actual URL (e.g. `fly secrets set CORS_ORIGINS=https://your-frontend.vercel.app,https://t.me`). Without it the backend falls back to built-in origins that cannot match your frontend: with `APP_ENV=production`, this repo's own Vercel domain plus `https://t.me`; otherwise (`APP_ENV` defaults to `dev`, and `backend/fly.toml` does not set it) only localhost origins. Your Mini App will load, but every API call is blocked by CORS, so pages like meals/goals/statistics appear empty. The effective list is logged once at startup as `Configuring CORS with origins: [...]`; see `get_cors_origins()` in `backend/src/calorie_track_ai_bot/services/config.py`. Also change `app` and `WEBHOOK_URL` in `backend/fly.toml` (they point at this repo's `calorie-track-ai-bot.fly.dev`), and with `APP_ENV=production` on a custom domain add it to `TRUSTED_HOSTS` (the default only allows `*.fly.dev` and localhost).

### Backend (Fly.io)
```bash
cd backend
flyctl deploy
```

### Frontend (Vercel)
```bash
# The CI workflow runs this from the repository root
vercel --prod
```

### Authentication settings

The backend authenticates Mini App requests with Telegram `initData`, so production needs `TELEGRAM_BOT_TOKEN` set to the token of the bot that opens the Mini App. A different token makes every API request fail with 401 "Invalid Telegram initData".

`ALLOW_INSECURE_USER_ID_HEADER` must be unset or `false` in production. When it is `true`, the backend also accepts the unsigned `x-user-id` header, and anyone can act as any user.

#### Rolling out initData authentication

Frontends built before initData authentication send only `x-user-id`; a backend with initData authentication rejects them unless the flag is on. `deploy.yml` deploys the backend before the frontend, and Mini Apps that are already open keep running the old frontend, so turn the flag on for the release that ships this change:

1. Before publishing the release, turn the flag on: `flyctl secrets set ALLOW_INSECURE_USER_ID_HEADER=true -a calorie-track-ai-bot`.
2. Merge the change, then merge the release PR to publish the release.
3. After `deploy.yml` finishes, open the Mini App from Telegram and check in the browser dev tools that requests carry `Authorization: tma ...` and succeed.
4. Turn the flag off: `flyctl secrets unset ALLOW_INSECURE_USER_ID_HEADER -a calorie-track-ai-bot`, then fully close and reopen the Mini App and check that it still loads your data.

## Contributing

1. Make your changes
2. Run tests: `make test`
3. Run linting: `make lint`
4. Commit your changes
5. Create a pull request

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the backend README.md
3. Check the API documentation at http://localhost:8000/docs
4. Create an issue in the repository
