# Calorie Track AI Bot - System Architecture

## Overview

The Calorie Track AI Bot is a comprehensive Telegram Mini App that uses AI-powered computer vision to analyze food photos and provide detailed nutritional information. The system features a modern, mobile-first design with automatic theme detection, multi-language support, and enterprise-grade observability. The architecture prioritizes scalability, performance, and developer experience.

## High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        U[Telegram Users]
        TG[Telegram Mini App]
        WEB[Web Interface]
    end

    subgraph "Frontend Layer (Vercel)"
        FE[React App]
        TGPROV[TelegramProvider<br/>Theme / Language / Safe Areas]
        QUERY[TanStack Query<br/>Orval-generated hooks]
    end

    subgraph "Backend Layer (Fly.io)"
        API[FastAPI API]
        WORKER[Background Worker<br/>in-process when ENABLE_WORKER=true]
        MIDDLEWARE[Middleware Stack]
        MONITOR[Performance Monitor]
    end

    subgraph "Database Layer (Neon PostgreSQL)"
        DB[PostgreSQL Database<br/>psycopg_pool]
    end

    subgraph "External Services"
        REDIS[Upstash Redis]
        S3[Tigris Storage]
        OPENAI[OpenAI API]
        BOT_API[Telegram Bot API]
    end

    subgraph "AI Processing"
        QUEUE[Redis Job Queues<br/>estimate_jobs / inline_jobs]
        ESTIMATOR[Nutrition Estimator<br/>OpenAI vision]
    end

    subgraph "Observability"
        LOGS[Structured Logging]
        METRICS[Performance Metrics]
        HEALTH[Health Checks]
    end

    %% User interactions
    U --> TG
    U --> WEB
    U --> BOT_API
    TG --> FE
    WEB --> FE

    %% Frontend services
    FE --> TGPROV
    FE --> QUERY

    %% Frontend to backend
    QUERY --> API

    %% Telegram webhook
    BOT_API -->|webhook POST /bot| API

    %% Backend services
    API --> MIDDLEWARE
    API --> MONITOR
    API --> WORKER

    %% Database connections
    API --> DB
    WORKER --> DB

    %% External service connections
    API --> S3
    API --> BOT_API
    WORKER --> S3
    WORKER --> BOT_API

    %% AI processing
    API --> QUEUE
    QUEUE --> WORKER
    WORKER --> ESTIMATOR
    ESTIMATOR --> OPENAI
    QUEUE --- REDIS

    %% Observability
    API --> LOGS
    WORKER --> LOGS
    API --> METRICS
    WORKER --> METRICS
    API --> HEALTH

    %% Styling
    classDef client fill:#e3f2fd
    classDef frontend fill:#e1f5fe
    classDef backend fill:#f3e5f5
    classDef database fill:#e8f5e8
    classDef external fill:#fff8e1
    classDef ai fill:#fce4ec
    classDef observability fill:#f1f8e9

    class U,TG,WEB client
    class FE,TGPROV,QUERY frontend
    class API,WORKER,MIDDLEWARE,MONITOR backend
    class DB database
    class REDIS,S3,OPENAI,BOT_API external
    class ESTIMATOR,QUEUE ai
    class LOGS,METRICS,HEALTH observability
```

## Inline Mode Pipeline

Inline photo analysis introduces an additional fast-path inside the existing architecture. The diagram below highlights the components that participate in the inline acknowledgement (≤3 s) and result delivery (≤10 s) SLAs while maintaining the 24 hour retention boundary for transient artifacts.

```mermaid
sequenceDiagram
    participant TG as Telegram Bot API
    participant API as FastAPI /bot (webhook)
    participant RQ as Upstash Redis Queue (inline_jobs)
    participant WK as Inline Worker (process_inline_jobs)
    participant OA as OpenAI Vision
    participant ST as Tigris Storage
    participant SA as Neon PostgreSQL Analytics

    TG->>API: Inline update (query / reply / tagged photo)
    API->>API: Validate + hash identifiers<br/>record request metadata
    API->>TG: Placeholder acknowledgement (≤3 s)
    API->>RQ: Enqueue InlineInteractionJob
    RQ->>WK: Pop job
    WK->>TG: Download photo file
    WK->>ST: Upload transient copy (expires ≤24 h)
    WK->>OA: Request calorie/macronutrient analysis
    OA-->>WK: Analysis payload
    WK->>TG: Edit inline message / threaded reply
    WK->>SA: Upsert InlineAnalyticsDaily aggregates
    WK->>API: Emit structured logs + metrics (trigger_type, latency, permission status)
```

**Throughput target**: the inline queue is dimensioned for 60 jobs per minute with bursts up to 5 RPS across active groups (`INLINE_THROUGHPUT_PER_MIN` / `INLINE_BURST_RPS`). `enqueue_inline_job` enforces these limits with Redis counters and raises `InlineQueueThrottleError` when exceeded. There is no autoscaling logic in the codebase; in production both workers run as asyncio tasks inside the API process.

**Privacy boundary**: chat and user identifiers are salted (`INLINE_HASH_SALT`) + hashed before they are enqueued, and only aggregate analytics (success/failure counts, latency, accuracy within tolerance, permission block counts) reach PostgreSQL (`inline_analytics_daily`). Transient photos are uploaded to Tigris under the `inline/` prefix. `storage.purge_transient_media()` deletes objects older than 24 hours, but nothing in the codebase schedules it yet.

## Component Architecture

### Frontend Architecture

```mermaid
graph TD
    subgraph "React Frontend Application"
        MAIN[main.tsx<br/>Telegram WebApp init]
        APP[app.tsx<br/>QueryClient + Router]
        ROUTER[React Router<br/>createBrowserRouter]
        TG_PROVIDER[TelegramProvider<br/>providers/telegram.tsx]
        LAYOUT[AppLayout<br/>ErrorBoundary + Suspense]

        subgraph "Pages (lazy-loaded)"
            MEALS[Meals Page<br/>/]
            STATS[Stats Page<br/>/stats]
            GOALS[Goals Page<br/>/goals]
            FEEDBACK[Feedback Page<br/>/feedback]
        end

        subgraph "UI Components"
            NAV[Navigation]
            ERROR[ErrorBoundary]
            MEAL_UI[MealCard / MealEditor<br/>PhotoCarousel / CalendarPicker]
            STATS_UI[StatsCharts / PeriodSelector]
            PRIMITIVES[Skeleton / Modal]
        end

        subgraph "Telegram Sensing"
            THEME_DETECT[Theme Detection<br/>Telegram / system]
            LANG_DETECT[Language Detection<br/>EN / RU]
            SAFE_DETECT[Safe Areas<br/>safe-area CSS vars]
        end

        subgraph "API Layer"
            QUERIES[TanStack Query hooks<br/>api/queries, Orval]
            MODELS[Types<br/>api/model, Orval]
            CLIENT[customFetch<br/>api/client.ts]
        end

        subgraph "Styling & i18n"
            TAILWIND[Tailwind CSS v4<br/>app.css @theme]
            TG_VARS[Telegram CSS vars<br/>tg-* variables]
            I18N[i18next<br/>en.ts / ru.ts]
        end
    end

    %% Main app flow
    MAIN --> APP
    APP --> TG_PROVIDER
    TG_PROVIDER --> ROUTER
    ROUTER --> LAYOUT
    LAYOUT --> NAV
    LAYOUT --> ERROR

    %% Router connections
    LAYOUT --> MEALS
    LAYOUT --> STATS
    LAYOUT --> GOALS
    LAYOUT --> FEEDBACK

    %% Component usage
    MEALS --> MEAL_UI
    STATS --> STATS_UI
    MEALS --> PRIMITIVES

    %% Telegram sensing
    TG_PROVIDER --> THEME_DETECT
    TG_PROVIDER --> LANG_DETECT
    TG_PROVIDER --> SAFE_DETECT

    %% Data fetching
    MEALS --> QUERIES
    STATS --> QUERIES
    GOALS --> QUERIES
    FEEDBACK --> QUERIES
    QUERIES --> MODELS
    QUERIES --> CLIENT

    %% Styling connections
    THEME_DETECT --> TG_VARS
    TG_VARS --> TAILWIND
    LANG_DETECT --> I18N

    %% Styling
    classDef core fill:#e1f5fe
    classDef components fill:#f3e5f5
    classDef services fill:#e8f5e8
    classDef state fill:#fff3e0
    classDef styling fill:#fce4ec

    class MAIN,APP,ROUTER,TG_PROVIDER,LAYOUT,MEALS,STATS,GOALS,FEEDBACK core
    class NAV,ERROR,MEAL_UI,STATS_UI,PRIMITIVES components
    class THEME_DETECT,LANG_DETECT,SAFE_DETECT services
    class QUERIES,MODELS,CLIENT state
    class TAILWIND,TG_VARS,I18N styling
```

Server state is managed entirely by TanStack Query; there is no global client-side store. `api/client.ts` attaches `X-Correlation-ID` and `Authorization: tma <initData>` (or `x-user-id` in dev builds outside Telegram) to every request.

### Backend Architecture

```mermaid
graph TD
    subgraph "FastAPI Backend Application"
        MAIN[main.py<br/>Application Entry]
        LIFESPAN[Lifespan Manager<br/>Startup/Shutdown]

        subgraph "Middleware Stack"
            CORS_MW[CORS Middleware<br/>Cross-Origin]
            TRUSTED_MW[Trusted Host Middleware<br/>production only]
            CORRELATION_MW[Correlation ID Middleware<br/>Tracing]
            LOGGING_MW[Request Logging Middleware<br/>Observability]
        end

        subgraph "API Routes v1"
            HEALTH[Health & Connectivity<br/>/health/*, /healthz]
            CONFIG_ROUTE[Configuration<br/>/api/v1/config/*]
            LOGS_ROUTE[Logging<br/>/api/v1/logs]
            DEV_ROUTE[Development<br/>/api/v1/dev/*]
            PHOTOS_ROUTE[Photo Management<br/>/api/v1/photos]
            ESTIMATES_ROUTE[AI Estimates<br/>/api/v1/photos/:id/estimate, /api/v1/estimates/*]
            MEALS_ROUTE[Meal Tracking<br/>/api/v1/meals/*]
            SUMMARY_ROUTE[Summaries<br/>/api/v1/daily-summary/*, weekly-, monthly-summary, today/*]
            GOALS_ROUTE[User Goals<br/>/api/v1/goals]
            STATS_ROUTE[Statistics<br/>/api/v1/statistics/*]
            FEEDBACK_ROUTE[Feedback<br/>/api/v1/feedback/*]
            ANALYTICS_ROUTE[Inline Analytics<br/>/api/v1/analytics/inline-summary]
            BOT_ROUTE[Telegram Bot Webhook<br/>/bot, /bot/*]
        end

        subgraph "Core Services"
            CONFIG_SVC[Configuration Service<br/>Settings & Features]
            DB_SVC[Database Service<br/>Neon PostgreSQL]
            STORAGE_SVC[Storage Service<br/>Tigris S3]
            TELEGRAM_SVC[Telegram Service<br/>Bot API]
            ESTIMATOR_SVC[AI Estimator Service<br/>OpenAI Integration]
            QUEUE_SVC[Queue Service<br/>Redis Lists]
            MONITORING_SVC[Monitoring Service<br/>Performance Metrics]
        end

        subgraph "Background Workers"
            ESTIMATE_WORKER[Estimate Worker<br/>estimate_jobs + inline_jobs]
        end
    end

    %% Main application flow
    MAIN --> LIFESPAN
    MAIN --> CORS_MW
    MAIN --> TRUSTED_MW
    MAIN --> CORRELATION_MW
    MAIN --> LOGGING_MW

    %% Middleware to routes
    CORS_MW --> HEALTH
    CORS_MW --> CONFIG_ROUTE
    CORS_MW --> LOGS_ROUTE
    CORS_MW --> DEV_ROUTE
    CORS_MW --> PHOTOS_ROUTE
    CORS_MW --> ESTIMATES_ROUTE
    CORS_MW --> MEALS_ROUTE
    CORS_MW --> SUMMARY_ROUTE
    CORS_MW --> GOALS_ROUTE
    CORS_MW --> STATS_ROUTE
    CORS_MW --> FEEDBACK_ROUTE
    CORS_MW --> ANALYTICS_ROUTE
    CORS_MW --> BOT_ROUTE

    %% Route to service connections
    CONFIG_ROUTE --> CONFIG_SVC
    LOGS_ROUTE --> MONITORING_SVC
    DEV_ROUTE --> CONFIG_SVC
    PHOTOS_ROUTE --> STORAGE_SVC
    PHOTOS_ROUTE --> DB_SVC
    ESTIMATES_ROUTE --> QUEUE_SVC
    ESTIMATES_ROUTE --> DB_SVC
    MEALS_ROUTE --> DB_SVC
    SUMMARY_ROUTE --> DB_SVC
    GOALS_ROUTE --> DB_SVC
    STATS_ROUTE --> DB_SVC
    FEEDBACK_ROUTE --> DB_SVC
    FEEDBACK_ROUTE --> TELEGRAM_SVC
    ANALYTICS_ROUTE --> DB_SVC
    BOT_ROUTE --> TELEGRAM_SVC
    BOT_ROUTE --> STORAGE_SVC
    BOT_ROUTE --> QUEUE_SVC

    %% Service interconnections
    CONFIG_ROUTE --> DB_SVC
    QUEUE_SVC --> ESTIMATE_WORKER
    ESTIMATE_WORKER --> DB_SVC
    ESTIMATE_WORKER --> ESTIMATOR_SVC
    ESTIMATE_WORKER --> STORAGE_SVC
    ESTIMATE_WORKER --> TELEGRAM_SVC

    %% Monitoring connections
    LOGGING_MW --> MONITORING_SVC
    CORRELATION_MW --> MONITORING_SVC

    %% Styling
    classDef main fill:#e1f5fe
    classDef middleware fill:#f3e5f5
    classDef routes fill:#e8f5e8
    classDef services fill:#fff3e0
    classDef workers fill:#fce4ec

    class MAIN,LIFESPAN main
    class CORS_MW,TRUSTED_MW,CORRELATION_MW,LOGGING_MW middleware
    class HEALTH,CONFIG_ROUTE,LOGS_ROUTE,DEV_ROUTE,PHOTOS_ROUTE,ESTIMATES_ROUTE,MEALS_ROUTE,SUMMARY_ROUTE,GOALS_ROUTE,STATS_ROUTE,FEEDBACK_ROUTE,ANALYTICS_ROUTE,BOT_ROUTE routes
    class CONFIG_SVC,DB_SVC,STORAGE_SVC,TELEGRAM_SVC,ESTIMATOR_SVC,QUEUE_SVC,MONITORING_SVC services
    class ESTIMATE_WORKER workers
```

## Data Flow Architecture

### Photo Upload and Processing Flow

Photos enter through the Telegram bot, not the Mini App. The Mini App only reads and edits the resulting meals. (`POST /api/v1/photos` and `POST /api/v1/photos/{id}/estimate` exist for presigned-upload clients but the frontend does not call them.)

```mermaid
sequenceDiagram
    participant U as User
    participant TG as Telegram Bot API
    participant API as Backend API (/bot)
    participant S3 as Tigris Storage
    participant Q as Redis Queue (estimate_jobs)
    participant W as Worker
    participant ML as OpenAI Vision
    participant DB as Neon PostgreSQL
    participant FE as Mini App

    U->>TG: Send photo(s) to bot
    TG->>API: Webhook update
    API->>DB: Get or create user
    API->>TG: Download photo file
    API->>S3: Upload via presigned PUT
    API->>DB: Insert photos row(s)
    API->>Q: Enqueue estimate job
    Q->>W: BRPOP job
    W->>S3: Presigned GET URL
    W->>ML: Analyze photo(s)
    ML-->>W: Calorie + macro estimate
    W->>DB: Insert estimate, create meal, link photos
    W->>TG: Send estimate message to user
    FE->>API: GET /api/v1/meals (Authorization: tma initData)
    API-->>FE: Meals with photos and macros
```

### Authentication Flow

There is no session or token exchange. On every request the Mini App sends Telegram's signed launch data (`initData`) as `Authorization: tma <initData>`. The backend verifies its HMAC signature with `TELEGRAM_BOT_TOKEN`, rejects data older than 24 hours, and takes the Telegram user ID from it.

```mermaid
sequenceDiagram
    participant U as User
    participant WA as Telegram WebApp
    participant FE as Frontend
    participant API as Backend API
    participant DB as Database

    U->>WA: Open mini-app
    WA->>FE: initData (signed by Telegram)
    FE->>API: Request with Authorization: tma initData
    API->>API: get_telegram_user_id verifies signature (api/v1/deps.py)
    API->>DB: Resolve telegram_id to users.id (5-min TTL cache)
    DB-->>API: Internal user UUID (404 if user never used the bot)
    API-->>FE: Response
    FE-->>WA: Render data
    WA-->>U: Show app interface
```

## Deployment Architecture

### Development Environment

```mermaid
graph LR
    subgraph "Local Development"
        DEV_FE[Frontend Dev Server<br/>localhost:3000]
        DEV_API[Backend API<br/>localhost:8000]
        DEV_WORKER[Worker<br/>make worker / worker container]
        DEV_DB[Neon PostgreSQL<br/>DATABASE_URL]
        DEV_REDIS[Redis<br/>local or Docker]
        DEV_S3[MinIO in Docker<br/>or Tigris]
    end

    DEV_FE --> DEV_API
    DEV_API --> DEV_DB
    DEV_API --> DEV_REDIS
    DEV_API --> DEV_S3
    DEV_WORKER --> DEV_REDIS
    DEV_WORKER --> DEV_DB
```

### Production Environment

```mermaid
graph TB
    subgraph "Vercel"
        FE_PROD[Static React Build]
        FE_CDN[Edge CDN]
    end

    subgraph "Fly.io (app: calorie-track-ai-bot)"
        API_PROD[Backend Container<br/>uvicorn :8080]
        WORKER_PROD[Worker asyncio tasks<br/>same process, ENABLE_WORKER=true]
    end

    subgraph "External Services"
        NEON[(Neon PostgreSQL)]
        REDIS_PROD[(Upstash Redis)]
        TIGRIS[(Tigris Storage)]
        OPENAI_PROD[OpenAI API]
        TG_PROD[Telegram Bot API]
    end

    subgraph "Monitoring"
        LOGS[Structured Logging]
        METRICS[Performance Metrics]
    end

    FE_PROD --> FE_CDN
    FE_CDN --> API_PROD
    TG_PROD -->|webhook /bot| API_PROD
    API_PROD --> WORKER_PROD
    API_PROD --> NEON
    API_PROD --> REDIS_PROD
    API_PROD --> TIGRIS
    WORKER_PROD --> NEON
    WORKER_PROD --> REDIS_PROD
    WORKER_PROD --> OPENAI_PROD
    WORKER_PROD --> TG_PROD
    API_PROD --> LOGS
    WORKER_PROD --> LOGS
    LOGS --> METRICS
```

The backend image is built by `backend-build.yml` (Dockerfile `runtime` stage), pushed to GHCR, and deployed with `flyctl deploy --image` by `backend-deploy.yml`. The frontend is built and deployed with the Vercel CLI by `frontend-deploy.yml`.

## Environment Configuration

### Development vs Production

```mermaid
graph LR
    subgraph "Development Environment"
        DEV_FE[Frontend Dev Server<br/>localhost:3000]
        DEV_API[Backend API<br/>localhost:8000]
        DEV_DB[Neon PostgreSQL]
        DEV_REDIS[Local Redis]
        DEV_S3[MinIO]
    end

    subgraph "Production Environment"
        PROD_FE[Frontend<br/>Vercel]
        PROD_API[Backend Container<br/>Fly.io]
        PROD_DB[Neon PostgreSQL]
        PROD_REDIS[Upstash Redis]
        PROD_S3[Tigris Storage]
    end

    DEV_FE --> DEV_API
    DEV_API --> DEV_DB
    DEV_API --> DEV_REDIS
    DEV_API --> DEV_S3

    PROD_FE --> PROD_API
    PROD_API --> PROD_DB
    PROD_API --> PROD_REDIS
    PROD_API --> PROD_S3
```

## Integration Points

### Frontend-Backend Integration

```mermaid
graph LR
    subgraph "Frontend"
        CONFIG[config.ts<br/>VITE_API_BASE_URL]
        QUERIES[TanStack Query hooks]
        API_CLIENT[customFetch]
        ERROR_HANDLER[ApiError + ErrorBoundary]
    end

    subgraph "Backend"
        CORS[CORS Middleware]
        CORRELATION[Correlation ID Middleware]
        AUTH_DEP[initData Auth Dependency]
        API_ROUTES[API Routes]
        ERROR_DECORATOR[handle_api_errors decorator]
    end

    CONFIG --> API_CLIENT
    QUERIES --> API_CLIENT
    API_CLIENT --> ERROR_HANDLER
    API_CLIENT --> CORS
    CORS --> CORRELATION
    CORRELATION --> API_ROUTES
    API_ROUTES --> AUTH_DEP
    API_ROUTES --> ERROR_DECORATOR
```

The frontend API client is generated by Orval from `frontend/openapi.json`, which is exported from the FastAPI app with `make -C backend openapi-export`.

## Technology Stack

### Frontend Technologies
- **React 19**: Function components with hooks, lazy-loaded pages
- **TypeScript 5.9**: Type-safe development with strict mode
- **Vite 7**: Build tool and dev server
- **Bun**: Package manager and script runner
- **React Router 7**: Client-side routing
- **TanStack Query**: Server state, using hooks generated by **Orval** from the OpenAPI spec
- **Custom fetch client**: Adds correlation ID and Telegram `initData` (`x-user-id` in dev outside Telegram) headers
- **Tailwind CSS v4**: CSS-first theming bound to Telegram `--tg-*` variables
- **Telegram WebApp API**: Native Telegram Mini App integration
- **i18next**: Internationalization (English/Russian)
- **Recharts / react-day-picker**: Stats charts and meal calendar

### Backend Technologies
- **FastAPI**: Modern Python web framework (OpenAPI 3.1)
- **Python 3.12**: Latest Python with type hints
- **Neon PostgreSQL**: Serverless PostgreSQL database (via psycopg3 + psycopg_pool, raw SQL)
- **Upstash Redis**: Serverless Redis for job queues and inline rate limiting
- **Tigris**: S3-compatible object storage (boto3)
- **OpenAI API**: GPT-5-mini (`OPENAI_MODEL`) for nutrition analysis
- **Telegram Bot API**: Bot functionality and webhooks (httpx client)
- **Structlog**: Structured logging with correlation IDs
- **Pydantic v2**: Data validation and serialization
- **psutil**: System monitoring and performance metrics

### Infrastructure Technologies
- **Fly.io**: Container deployment platform for backend
- **Vercel**: Edge deployment for frontend
- **Docker**: Containerization with multi-stage builds
- **Neon**: Serverless PostgreSQL with branching
- **GitHub Actions**: CI/CD pipeline
- **Performance Monitoring**: Real-time metrics collection
- **Health Checks**: `/health/live`, `/health/ready`, `/health/connectivity`, `/healthz` (Fly check)
- **Correlation IDs**: Request tracing via `x-correlation-id`

## Security Architecture

```mermaid
graph TD
    subgraph "Security Layers"
        TELEGRAM_ID[Telegram initData<br/>HMAC-verified]
        TRUSTED_HOSTS[Trusted Hosts<br/>production only]
        CORS_POLICY[CORS Policy]
        RATE_LIMIT[Inline Queue Throttling]
        INPUT_VALIDATION[Pydantic Input Validation]
        HASHING[Salted ID Hashing<br/>inline analytics]
    end

    TRUSTED_HOSTS --> CORS_POLICY
    CORS_POLICY --> TELEGRAM_ID
    TELEGRAM_ID --> INPUT_VALIDATION
    RATE_LIMIT --> HASHING
```

Note: the unsigned `x-user-id` header is accepted only when no `initData` is sent and the backend runs with `ALLOW_INSECURE_USER_ID_HEADER=true` (local development). Never enable it in production: anyone could then act as any user.

## Performance Architecture

### Caching Strategy

```mermaid
graph LR
    subgraph "Caching Layers"
        BROWSER[Browser Cache]
        CDN[Vercel CDN<br/>static assets]
        QUERY_CACHE[TanStack Query Cache<br/>client]
        USER_CACHE[User ID TTL Cache<br/>in-process, 5 min]
    end

    BROWSER --> CDN
    QUERY_CACHE --> USER_CACHE
```

### Optimization Strategies
- **Frontend**: Code splitting, lazy loading, image optimization
- **Backend**: Database indexing, query optimization, connection pooling
- **Infrastructure**: CDN distribution, container optimization
- **Monitoring**: Performance metrics, resource usage tracking

## Monitoring and Observability

```mermaid
graph TD
    subgraph "Observability Stack"
        LOGS[Structured Logs<br/>structlog]
        CORRELATION[Correlation IDs]
        METRICS[Performance Metrics<br/>services/monitoring.py]
        INLINE_TELEMETRY[Inline Telemetry<br/>latency, failures]
        HEALTH[Health Endpoints]
    end

    CORRELATION --> LOGS
    METRICS --> LOGS
    INLINE_TELEMETRY --> LOGS
    HEALTH --> METRICS
```

## Development Workflow

```mermaid
graph LR
    subgraph "Development Process"
        SPEC[Specification]
        PLAN[Planning]
        IMPL[Implementation]
        TEST[Testing]
        DEPLOY[Deployment]
        MONITOR[Monitoring]
    end

    SPEC --> PLAN
    PLAN --> IMPL
    IMPL --> TEST
    TEST --> DEPLOY
    DEPLOY --> MONITOR
    MONITOR --> SPEC
```

This architecture documentation provides a comprehensive view of the Calorie Track AI Bot system, showing how all components interact and work together to deliver a robust, scalable, and maintainable application.
