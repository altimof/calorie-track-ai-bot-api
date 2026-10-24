# Integration Testing Guide

## Overview

This guide provides comprehensive instructions for testing the integration between the frontend and backend components of the Calorie Track AI Bot system. It covers contract testing, API integration, E2E testing, and mobile device testing for the Telegram Mini App. No performance/load-testing setup exists in the repo.

## Integration Test Architecture

```mermaid
graph TB
    subgraph "Test Environment"
        subgraph "Frontend Tests"
            UNIT_FE[Unit Tests<br/>Vitest]
            CONTRACT_FE[Contract Tests<br/>API Validation]
            COMPONENT_FE[Component Tests<br/>React Testing]
            E2E_FE[E2E Tests<br/>Playwright]
        end

        subgraph "Backend Tests"
            UNIT_BE[Unit Tests<br/>Pytest]
            CONTRACT_BE[Contract Tests<br/>API Specs]
            INTEGRATION_BE[Integration Tests<br/>Mocked DB, Queue & Bot]
        end

        subgraph "Full Stack Tests"
            CONNECTIVITY[Connectivity Tests<br/>Health Checks]
            WORKFLOW[Workflow Tests<br/>User Journeys]
            MOBILE[Mobile Tests<br/>Device Simulation]
            THEME_LANG[Theme & Language<br/>Detection Tests]
        end

        subgraph "Test Infrastructure"
            VITEST[Vitest + Testing Library]
            PLAYWRIGHT[Playwright Multi-Device]
            PYTEST[Pytest + FastAPI TestClient]
            MOCK[Mock Services & Fixtures<br/>unittest.mock / MSW]
        end
    end

    %% Frontend test connections
    UNIT_FE --> VITEST
    CONTRACT_FE --> VITEST
    COMPONENT_FE --> VITEST
    E2E_FE --> PLAYWRIGHT

    %% Backend test connections
    UNIT_BE --> PYTEST
    CONTRACT_BE --> PYTEST
    INTEGRATION_BE --> PYTEST

    %% Full stack test connections
    CONNECTIVITY --> MOCK
    WORKFLOW --> PLAYWRIGHT
    MOBILE --> PLAYWRIGHT
    THEME_LANG --> PLAYWRIGHT

    %% Infrastructure connections
    INTEGRATION_BE --> MOCK
    CONTRACT_BE --> MOCK
```

## Local Testing Setup

### Prerequisites

```mermaid
graph LR
    subgraph "Required Tools"
        BUN[Bun]
        PYTHON[Python 3.12 + uv]
        DOCKER[Docker]
        POSTGRES[Neon PostgreSQL]
        REDIS[Redis]
    end

    subgraph "Environment Files"
        ENV_FE[frontend env vars]
        ENV_BE[backend/.env]
        ENV_TEST[backend/pytest.ini env]
    end

    BUN --> ENV_FE
    PYTHON --> ENV_BE
    PYTHON --> ENV_TEST
```

### Environment Configuration

#### Frontend Environment
The frontend reads only two variables (`frontend/src/api/client.ts`, `frontend/src/config.ts`):
```bash
# API base URL (defaults to http://localhost:8000)
VITE_API_BASE_URL=http://localhost:8000

# Fallback x-user-id in dev when not running inside Telegram (defaults to 59357664);
# the backend must run with ALLOW_INSECURE_USER_ID_HEADER=true to accept it
VITE_DEV_USER_ID=123456789
```

#### Backend Environment (backend/.env)
See `backend/.env.example` and `backend/env.template` for the full list. Minimal set:
```bash
# Database Configuration (Neon PostgreSQL)
DATABASE_URL=postgresql://user:password@host/neondb?sslmode=require

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Storage Configuration (Mock for testing)
AWS_ENDPOINT_URL_S3=http://localhost:9000
AWS_ACCESS_KEY_ID=test_key
AWS_SECRET_ACCESS_KEY=test_secret
BUCKET_NAME=test-bucket

# Telegram Configuration
TELEGRAM_BOT_TOKEN=test_token
USE_WEBHOOK=false

# AI estimation
OPENAI_API_KEY=test-openai-key

# Logging
LOG_LEVEL=DEBUG
APP_ENV=development
```

## Testing Workflows

### 1. Connectivity Testing

```mermaid
sequenceDiagram
    participant DEV as Developer
    participant FE as Frontend
    participant API as Backend API
    participant DB as Database

    DEV->>FE: Start frontend dev server
    DEV->>API: Start backend server
    FE->>API: GET /health/connectivity
    API-->>FE: Health status (includes DB ping)
    FE->>API: Test API endpoint
    API->>DB: Database query
    DB-->>API: Query result
    API-->>FE: API response
    FE-->>DEV: Test results
```

### 2. Authentication Flow Testing

There is no session/token endpoint. The frontend's `customFetch` (`frontend/src/api/client.ts`) sends `window.Telegram.WebApp.initData` as `Authorization: tma <initData>`. Outside Telegram, dev builds send `VITE_DEV_USER_ID` as `x-user-id` instead. The backend (`api/v1/deps.py`) verifies the `initData` signature and returns 401 when it is invalid, expired or missing; `x-user-id` is accepted only with `ALLOW_INSECURE_USER_ID_HEADER=true`. The Telegram user ID is then resolved to an internal user ID.

```mermaid
sequenceDiagram
    participant TEST as Test Suite
    participant FE as Frontend
    participant API as Backend API
    participant DB as Database

    TEST->>FE: Initialize app (mock window.Telegram.WebApp)
    FE->>API: Request with Authorization: tma initData
    API->>API: Verify initData signature
    API->>DB: Resolve telegram user ID to user
    DB-->>API: User ID
    API-->>FE: Protected resource
    FE-->>TEST: Test passed
```

### 3. Photo Upload Testing

```mermaid
sequenceDiagram
    participant TEST as Test Suite
    participant FE as Frontend
    participant API as Backend API
    participant STORAGE as Storage Service
    participant QUEUE as Queue Service
    participant WORKER as Worker

    TEST->>FE: Upload test photo
    FE->>API: POST /api/v1/photos
    API->>STORAGE: Generate presigned URL
    STORAGE-->>API: Upload URL
    API-->>FE: Photo ID + URL
    FE->>STORAGE: Upload file
    FE->>API: POST /api/v1/photos/{id}/estimate
    API->>QUEUE: Queue estimation
    QUEUE->>WORKER: Process job
    WORKER-->>QUEUE: Job complete
    FE->>API: GET /api/v1/estimates/{id}
    API-->>FE: Estimate results
    FE-->>TEST: Upload test passed
```

### 4. Inline Mode Scenarios

Use these manual and automated checks when validating inline mode end-to-end. Each checklist item maps to automated coverage in `backend/tests/api/v1/test_bot_inline.py`, `backend/tests/integration/test_inline_flows.py`, or `backend/tests/api/v1/test_inline_analytics_endpoint.py`.

- [ ] **Inline query acknowledgement** — Trigger an inline query (`@CalorieTrackAI_bot`) in a private chat and confirm the placeholder message appears within 3 seconds while the JSON response echoes the same `job_id`.
- [ ] **Private inline summary** — Select the inline result and verify the final message includes calories, macronutrients, confidence, and the privacy disclosure from the quickstart guide.
- [ ] **Group reply mention** — Reply to a group photo with `@CalorieTrackAI_bot` and check that both the acknowledgement and result stay threaded via `reply_to_message_id`.
- [ ] **Tagged caption flow** — Post a group photo tagging the bot in the caption; expect the bot to reply inline or DM a fallback with admin guidance if permissions block posting, incrementing `permission_block_count`.
- [ ] **Analytics snapshot** — Query `/api/v1/analytics/inline-summary` and confirm the appropriate `trigger_counts` bucket increments for `inline_query`, `reply_mention`, or `tagged_photo`.
- [ ] **Telemetry verification** — Inspect structured logs/metrics to ensure `trigger_type`, acknowledgement latency, and result latency events were emitted for each exercised flow.

## Test Commands

### Frontend Testing

```bash
# Install dependencies
cd frontend
bun install

# Run unit, component, and contract tests (Vitest)
bun run test

# Run E2E tests (Playwright)
bun run test:e2e

# Start development server
bun run dev

# Build for production
bun run build
```

### Backend Testing

```bash
# Install dependencies
cd backend
uv sync

# Run all tests
uv run pytest tests/

# Run unit tests only (excludes tests/integration/)
make test-unit

# Run integration tests
uv run pytest tests/integration/

# Run API tests
uv run pytest tests/api/

# Start development server
make dev   # uv run uvicorn calorie_track_ai_bot.main:app --host 0.0.0.0 --port 8000 --reload

# Run linting
uv run ruff check
uv run pyright
```

### Full Stack Testing

From the repo root:
```bash
# Start backend (port 8000) and frontend (port 3000)
make dev

# Run backend pytest + frontend vitest
make test

# Full stack via Docker Compose (redis, minio, backend, worker, frontend, nginx)
make docker-dev

# Stop Docker containers
make docker-stop
```

## Test Scenarios

There is no `frontend/tests/integration/` directory and no `test:integration` script. Frontend-to-backend integration is covered by these Vitest suites (all run by `bun run test`):

- `frontend/src/api/__tests__/client.test.ts` - `customFetch` sends `initData` as `Authorization` (or `x-user-id` in dev without Telegram) and `X-Correlation-ID` and throws `ApiError` on non-OK responses
- `frontend/src/tests/contracts/*.test.ts` - Response-shape checks for meals, estimates, photos, and photo display
- `frontend/src/test/handlers.ts` - MSW handlers mocking `http://localhost:8000` endpoints (`/health/live`, `/api/v1/goals`, `/api/v1/meals`, ...) used by component and page tests

### 1. API Client Test (excerpt)

```typescript
// frontend/src/api/__tests__/client.test.ts
it("sends Telegram initData as Authorization and no x-user-id", async () => {
  const spy = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

  await customFetch({ url: "/health/live", method: "GET" });

  const [, init] = spy.mock.calls[0];
  const headers = init?.headers as Record<string, string>;
  expect(headers["Authorization"]).toBe("tma mock_init_data");
  expect(headers["x-user-id"]).toBeUndefined();
});
```

Health endpoints are `GET /health/live`, `GET /health/ready`, and `GET /health/connectivity` (there is no `/api/v1/health`).

## Performance Testing

Not implemented. There is no `tests/performance/` directory and no K6, Artillery, or JMeter configuration. `frontend/playwright.config.ts` defines a `Performance` project matching `**/performance-*.spec.ts`, but no such spec files exist.

## Debugging Integration Issues

### Common Issues and Solutions

```mermaid
graph TD
    subgraph "Common Integration Issues"
        CORS_ERROR[CORS Errors]
        AUTH_ERROR[Authentication Errors]
        TIMEOUT_ERROR[Timeout Errors]
        NETWORK_ERROR[Network Errors]
    end

    subgraph "Debugging Tools"
        BROWSER_DEV[Browser DevTools]
        NETWORK_TAB[Network Tab]
        CONSOLE_LOG[Console Logging]
        API_LOGS[API Logs]
    end

    CORS_ERROR --> BROWSER_DEV
    AUTH_ERROR --> CONSOLE_LOG
    TIMEOUT_ERROR --> NETWORK_TAB
    NETWORK_ERROR --> API_LOGS
```

### Debugging Checklist

1. **Check CORS Configuration**
   - Verify allowed origins in backend
   - Check preflight requests
   - Validate headers

2. **Verify Authentication**
   - Inside Telegram, check `Authorization: tma <initData>` is sent; outside Telegram in dev, check `x-user-id` (`VITE_DEV_USER_ID`) is sent
   - 401 "Invalid Telegram initData": signature or age check failed (wrong `TELEGRAM_BOT_TOKEN` on the backend, or data older than 24 hours)
   - 401 "Missing Telegram initData": no `initData`, and `x-user-id` is missing or `ALLOW_INSECURE_USER_ID_HEADER` is off

3. **Monitor Network Requests**
   - Check request/response headers
   - Verify API endpoints
   - Monitor response times

4. **Check Error Handling**
   - Test error scenarios
   - Verify error messages
   - Check fallback behavior

## Continuous Integration

### CI/CD Pipeline

There is no dedicated integration-test workflow. CI workflows trigger on path-based changes; deploys run only from a published release:

```mermaid
graph LR
    BCI[backend-ci.yml<br/>ruff, pyright, pytest -q]
    FCI[frontend-ci.yml<br/>Orval drift check, vitest, build]
    RP[release-please.yml<br/>release PR, vX.Y.Z]
    DEPLOY[deploy.yml<br/>GHCR, Fly.io, Vercel]

    RP --> DEPLOY
    BCI -. gate .-> DEPLOY
    FCI -. gate .-> DEPLOY
```

- `backend-ci.yml` runs `uv run pytest -q` over all of `backend/tests/` (including `tests/integration/`) with dummy env vars; no Postgres or Redis service containers are started (tests mock the DB pool, queue, and bot).
- `frontend-ci.yml` runs `bun run test` (Vitest) and `bun run build`.
- Playwright E2E tests are not run in CI; run `bun run test:e2e` locally.

This comprehensive integration testing guide provides all the tools and procedures needed to ensure reliable communication between your frontend and backend components.
