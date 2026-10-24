# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See also the root-level `../CLAUDE.md` for monorepo-wide commands and full architecture overview.

## Commands (run from `backend/`)

```bash
make dev              # FastAPI with hot reload on port 8000
make worker           # Background estimate worker
make test             # All tests (pytest)
make test-unit        # Unit tests only (ignores tests/integration/)
make lint             # ruff check
make check            # lint (ruff) + typecheck (pyright)
make format           # ruff format
make openapi-export   # Export OpenAPI spec JSON to ../frontend/openapi.json

# Single test
uv run pytest tests/path/to/test_file.py -v
uv run pytest tests/path/to/test_file.py::test_name
uv run pytest tests/integration/ -v   # Integration tests only
```

## Source Layout

```
src/calorie_track_ai_bot/
├── main.py              # FastAPI app, middleware stack, router registration
├── schemas.py           # Pydantic models (edit directly, source of truth for API schema)
├── api/v1/              # Route handlers (one file per resource); deps.py = auth dependencies
├── services/            # Business logic and external integrations
│   ├── config.py        # All env var loading, feature flags
│   ├── database.py      # Async connection pool (psycopg_pool) lifecycle
│   ├── db/              # Database operations (per-domain modules)
│   │   ├── _base.py     # resolve_user_id with 5-min TTL cache (max 1000 entries)
│   │   ├── users.py, photos.py, estimates.py, meals.py, goals.py
│   │   ├── summaries.py, ui_config.py, inline_analytics.py
│   │   └── __init__.py  # Re-exports all public functions
│   ├── estimator.py     # OpenAI vision API for calorie estimation (OPENAI_MODEL, default gpt-5-mini)
│   ├── queue.py         # Redis job queue (`r` client)
│   ├── storage.py       # Tigris S3 presigned URLs
│   ├── telegram.py      # Telegram bot client
│   ├── feedback_service.py, statistics_service.py, monitoring.py
│   └── inline_notifications.py, inline_renderer.py  # Telegram inline mode
├── utils/
│   └── error_handling.py  # @handle_api_errors decorator
└── workers/
    └── estimate_worker.py  # Background photo estimation processor
```

## Key Patterns

**Auth:** No JWT/session auth. The Mini App sends Telegram `initData` as `Authorization: tma <initData>`; `get_telegram_user_id` verifies it (`services/telegram_auth.py`, HMAC with `TELEGRAM_BOT_TOKEN`, 24h max age) and takes the Telegram user ID from it. The unsigned `x-user-id` header is accepted only when no `initData` is sent and `ALLOW_INSECURE_USER_ID_HEADER=true` (local dev; tests enable it in `conftest.py`, and `tests/api/v1/test_deps.py` covers the signed path). Use `Depends(get_telegram_user_id)` or `Depends(get_authenticated_user_id)` from `api/v1/deps.py`. The `db/_base.py` module resolves telegram_id to internal UUID user with a 5-minute TTL cache (max 1000 entries).

**Dates and time zones:** The Mini App sends the browser's IANA zone in an `x-timezone` header; `get_user_timezone` in `api/v1/deps.py` reads it (falls back to UTC). Meal-day filters and grouping use `LOCAL_MEAL_DATE_SQL` (`created_at AT TIME ZONE tz`), not the `meal_date` column. Bot-side daily totals still use UTC.

**Error handling:** Route handlers use `@handle_api_errors("context_name")` decorator. It re-raises `HTTPException` as-is and wraps unexpected exceptions into generic 500s (no internal details leaked).

**Schemas:** `schemas.py` is the source of truth for API request/response models. Edit it directly. FastAPI auto-generates the OpenAPI spec from these models at runtime (`/docs`, `/openapi.json`). Use `make openapi-export` to dump the spec to a file.

**Middleware order** (in `main.py`): registered as TrustedHost (only when `APP_ENV=production`) → request logging → correlation ID → CORS. Starlette makes the last-registered outermost, so requests flow CORS → correlation ID → request logging. The correlation ID middleware binds `x-correlation-id` to structlog context vars.

**Testing:** All external services (Database, Redis, OpenAI, S3, Telegram) are mocked at module level in `tests/conftest.py` via `unittest.mock.patch`. Test env vars are set via `os.environ` at the top of `tests/conftest.py` (`pytest.ini` uses a `[tool:pytest]` header, so pytest ignores its `env` block). Use fixtures like `api_client`, `authenticated_headers`, `mock_db_pool`, `mock_redis_client`, `mock_openai_client`, `mock_s3_client`, `mock_telegram_bot` from conftest. The `mock_db_pool` fixture patches `get_pool()` and returns `(mock_pool, mock_conn)` — pool uses `Mock()` (synchronous `pool.connection()`), connection uses `AsyncMock()`.

**Database:** Schema defined in `infra/schema.sql` (idempotent; mirrors the live Neon schema). Tables: `users`, `photos`, `estimates`, `meals`, `goals`, `feedback_submissions`, `ui_configurations`, `inline_analytics_daily`, plus the `query_daily_statistics()` function. All PKs are UUID via `gen_random_uuid()`. Users are keyed by `telegram_id` (bigint, unique); `feedback_submissions.user_id` and `ui_configurations.user_id` hold the Telegram ID as text. No migration tool: apply changes to Neon by hand and update `schema.sql` in the same PR.

## Deployment

Do NOT offer to deploy to Fly.io unless explicitly asked. Pushes to main do not deploy: `deploy.yml` deploys when release-please publishes a `vX.Y.Z` release (after CI passes on the release commit), or by manual dispatch with an existing tag.

## Code Style

- **Package manager:** `uv` (not pip) — use `uv run` to execute commands
- **Ruff:** line length 100, double quotes, LF, rules E/F/I/B/UP/RUF (E501 ignored)
- **Pyright:** basic mode, excludes tests directory
- **Python:** 3.12, Pydantic v2, async FastAPI handlers
- **Before committing:** run `uv run ruff format .` to auto-format all changed files. Pre-commit hooks enforce formatting and will reject unformatted code.
