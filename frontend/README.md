# Calorie Track AI - Telegram Mini App

A modern, mobile-first Telegram Mini App for calorie tracking with AI-powered food recognition. Built with React 19, TypeScript 5.9, Vite 7, Tailwind CSS v4, and TanStack Query (with an Orval-generated API client), featuring meal tracking, goal setting, and statistics.

## 🚀 Quick Start

### Prerequisites
- [Bun](https://bun.sh) (package manager and runtime)
- Backend API running on `http://localhost:8000` (see main project README)

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd calorie-track-ai-bot-api/frontend

# Install dependencies
bun install

# Start development server
bun run dev
```

The app will be available at `http://localhost:3000`

## 📱 Features

### Core Functionality
- **Meals** (`/`): Today's meals with daily calorie/macro summary and goal
- **Meal Editing**: Edit description and macros of AI-estimated meals (calories recalculated), delete with confirmation
- **Statistics** (`/stats`): Data visualization with Recharts
  - Summary cards (average daily calories, total meals)
  - Calorie trend line chart (last 7/30/90 days)
  - Macronutrient distribution pie chart
- **Goals** (`/goals`): Set and track a daily calorie target
- **Feedback** (`/feedback`): Free-text feedback form (up to 5000 characters); the backend forwards submissions to an admin chat via the Telegram bot. Not linked from the bottom navigation
- **Internationalization**: English and Russian (177 translation keys)

### User Experience
- **Mobile-First**: Optimized for Telegram's mobile interface
- **Dark Mode**: Automatic theme detection from Telegram (falls back to system `prefers-color-scheme`)
- **Accessibility**: ARIA labels/roles on navigation, dialogs, and controls; axe-core checks in E2E tests
- **Performance**: Lazy-loaded routes, skeleton screens, and an error boundary

## 🛠️ Development

### Available Scripts
```bash
# Development
bun run dev              # Start Vite dev server on 0.0.0.0:3000 with hot reload

# Building
bun run build            # Type-check (tsc -b) and build for production
bun run preview          # Preview production build locally (port 3000)

# Testing
bun run test             # Run unit tests (Vitest)
bun run test:watch       # Run tests in watch mode
bun run test:coverage    # Run unit tests with coverage
bun run test:e2e         # Run Playwright end-to-end tests
bun run test:e2e:headed  # Run E2E tests in headed browsers

# Code Quality
bun run check            # Type-check + lint + format check
bun run lint             # Run ESLint
bun run lint:fix         # Fix ESLint issues
bun run type-check       # Run TypeScript type checking
bun run format           # Format code with Prettier
bun run format:check     # Check formatting
bun run i18n:validate    # Validate translation key consistency (EN/RU)

# Utilities
bun run clean            # Clean build artifacts
bun run api:gen          # Generate API types and TanStack Query hooks from openapi.json (Orval)
bun run api:gen:watch    # Regenerate on spec changes
```

A `Makefile` wraps the common ones (`make dev`, `make test`, `make lint`, `make format`, `make check`, `make clean`).

### Project Structure
```
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts        # Custom fetch client (Orval mutator)
│   │   ├── model/           # Generated TypeScript types (Orval)
│   │   └── queries/         # Generated TanStack Query hooks (Orval)
│   ├── components/
│   │   ├── layout/          # AppLayout, Navigation, ErrorBoundary
│   │   ├── meal/            # MealCard, MealEditor, PhotoCarousel, CalendarPicker
│   │   ├── stats/           # StatsCharts, PeriodSelector
│   │   └── ui/              # Modal, Skeleton
│   ├── pages/               # Route components (lazy-loaded)
│   │   ├── meals/
│   │   ├── stats/
│   │   ├── goals/
│   │   └── feedback/
│   ├── providers/
│   │   └── telegram.tsx     # TelegramProvider (theme, language, safe areas, user)
│   ├── i18n/
│   │   ├── index.ts         # i18next setup
│   │   ├── en.ts / ru.ts    # Translations
│   │   └── validate-keys.mjs # Translation validator
│   ├── test/                # Vitest setup, render utils, MSW handlers
│   ├── tests/               # API contract tests, i18n tests
│   ├── utils/               # Date helpers
│   ├── app.tsx              # Router and providers
│   ├── app.css              # Tailwind CSS v4 + @theme tokens
│   ├── main.tsx             # App entry point
│   └── config.ts            # Configuration
├── tests/
│   └── e2e/                 # Playwright end-to-end tests
├── docs/                    # Documentation
├── openapi.json             # OpenAPI spec snapshot used by Orval
├── orval.config.ts
├── playwright.config.ts
├── vite.config.ts
└── vitest.config.ts
```

### Configuration

#### Environment Variables
```bash
# .env.local
VITE_API_BASE_URL=http://localhost:8000   # defaults to http://localhost:8000
VITE_DEV_USER_ID=123456                   # dev only: x-user-id when not running inside Telegram (backend needs ALLOW_INSECURE_USER_ID_HEADER=true)
```

#### Telegram WebApp Integration
The app automatically detects and integrates with Telegram's WebApp API:
- `ready()`, `expand()`, closing confirmation, header/background colors (in `src/main.tsx`, only when `initData` is present)
- Theme detection (light/dark mode) and language (`en`/`ru`) from Telegram, with system/browser fallbacks
- Signed `initData` sent to the API as `Authorization: tma <initData>`; the backend verifies it and takes the user ID from it

## 🧪 Testing

### Unit Tests
```bash
bun run test
```
Tests (Vitest + React Testing Library) cover:
- Component and page rendering and behavior (`__tests__/` next to source)
- API client and API contracts (`src/api/__tests__/`, `src/tests/contracts/`)
- Internationalization (`src/tests/i18n.test.ts`)
- Telegram provider

### End-to-End Tests
```bash
bun run test:e2e
```
Playwright E2E tests (`tests/e2e/`, config in `playwright.config.ts`) cover:
- Meal workflows (editing, deletion, card expansion, history, calendar filtering)
- Goals, stats, feedback
- Theme switching, language detection, safe areas, mobile devices
- Accessibility (axe-core)

### Test Data
API mocks for unit tests are MSW handlers in `src/test/handlers.ts`.

## 🎨 Styling

### CSS Architecture
- **Tailwind CSS v4**: CSS-first configuration in `src/app.css` (no `tailwind.config.js`), via `@tailwindcss/vite`
- **CSS Variables**: Telegram theme integration
- **Mobile-First**: Responsive design patterns
- **Dark Mode**: `data-theme` attribute on `<html>`, set by `TelegramProvider`

### Theme Integration
```css
@import "tailwindcss";

@theme {
  --color-tg-bg: var(--tg-bg-color, #ffffff);
  --color-tg-text: var(--tg-text-color, #000000);
  --color-tg-button: var(--tg-button-color, #0066cc);
  --color-tg-button-text: var(--tg-button-text-color, #ffffff);
}
```
Use the resulting utilities (`bg-tg-bg`, `text-tg-text`, ...) instead of hardcoded colors.

## 🌐 Internationalization

### Supported Languages
- English (en)
- Russian (ru)

### Adding Translations
Add the key to both `src/i18n/en.ts` and `src/i18n/ru.ts` (nested objects), then run:
```bash
bun run i18n:validate
```

### Usage
```typescript
import { useTranslation } from 'react-i18next';

const MyComponent = () => {
  const { t } = useTranslation();
  return <h1>{t('common.title')}</h1>;
};
```

## 🚀 Deployment

### Vercel
Production deploys run from GitHub Actions (`.github/workflows/frontend-deploy.yml`) after `Frontend CI` succeeds on `main` (or on `v*` tags / manual dispatch): `bun run build`, then `vercel --prod`. To deploy manually:
```bash
bun install --global vercel
vercel --prod
```

### Docker
`Dockerfile` has a `development` stage (Vite dev server on port 3000) and a production build served by nginx (`nginx.conf`).

### Manual Deployment
```bash
# Build the app
bun run build

# Upload dist/ folder to your hosting provider
```

### Environment Configuration
Set these environment variables in your deployment platform:

```bash
VITE_API_BASE_URL=https://your-api-domain.com
```

### Performance Optimization
- **Code Splitting**: Route-based splitting with `React.lazy()`
- **Vendor Chunks**: `react-vendor`, `chart-vendor`, `i18n-vendor` (`manualChunks` in `vite.config.ts`)
- **Tree Shaking**: Unused code elimination

## 📊 Performance

### Lighthouse Scores (Target)
- **Performance**: 90+
- **Accessibility**: 100
- **Best Practices**: 90+
- **SEO**: 90+

### Core Web Vitals
- **FCP**: < 1.8s
- **LCP**: < 2.5s
- **FID**: < 100ms
- **CLS**: < 0.1

### Bundle Size (Target)
- **JavaScript**: < 250KB gzipped
- **CSS**: < 50KB gzipped

## 🔧 Troubleshooting

### Common Issues

#### Telegram WebApp Not Loading
```bash
# Check if running in Telegram environment
console.log(window.Telegram?.WebApp);
```

#### API Connection Issues
```bash
# Verify API URL configuration
echo $VITE_API_BASE_URL
```

#### Build Failures
```bash
# Clear cache and reinstall
bun run clean
rm -rf node_modules
bun install
```

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run quality checks
5. Submit a pull request

### Code Standards
- TypeScript strict mode
- ESLint + Prettier configuration (`bun run check`)
- Conventional commits

### Pull Request Checklist
- [ ] Tests pass
- [ ] No linting errors
- [ ] TypeScript compilation succeeds
- [ ] Performance impact assessed
- [ ] Accessibility verified

## 📚 Documentation

- [Performance & Accessibility Guide](docs/performance-accessibility.md)
- [E2E Testing Guide](docs/e2e-testing-guide.md)
- [Components](docs/components.md)
- [API Specification](openapi.json)

## 📄 License

This project is part of the Calorie Track AI Bot system. See the main project README for license information.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review existing GitHub issues
3. Create a new issue with detailed information

---

Built with ❤️ for healthy living and accurate calorie tracking.
