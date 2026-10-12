# End-to-End Testing Guide

## Overview

This guide describes E2E testing for the Calorie Track AI Bot Mini App: the Playwright setup, manual happy-path scenarios, and how the existing specs in `tests/e2e/` are structured.

> **Status:** Many specs in `tests/e2e/` predate the current UI (e.g. they expect a "Today" heading, a `/meal/:id` detail route, expandable meal cards, or `data-testid`s that components no longer render). In addition, Playwright projects only pick up files matching their `testMatch` patterns (see [Projects](#projects)), so only 9 of the 22 spec files are run by `bun run test:e2e`. E2E tests are not run in CI.

## Test Environment Setup

### Prerequisites
- [Bun](https://bun.sh) installed
- Backend API running on `http://localhost:8000` (or API calls mocked with `page.route()`)

### Installation
```bash
cd frontend
bun install
bunx playwright install
```
`@playwright/test`, `playwright`, and `@axe-core/playwright` are already in `devDependencies`.

### Configuration
`frontend/playwright.config.ts` (abridged):

```typescript
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30 * 1000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['html', { open: 'never' }], ['json', ...], ['junit', ...], ...],
  outputDir: 'test-results/',
  webServer: [
    {
      command: 'npm run dev',          // Vite dev server
      url: 'http://localhost:3000',
      reuseExistingServer: !process.env.CI,
    },
    // On CI only: `cd ../backend && make dev`, waiting for /health/live
  ],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'en-US',
  },
  projects: [ /* see below */ ],
});
```

### Projects

Each project only runs files matching its `testMatch`:

| Project | Device | `testMatch` |
|---|---|---|
| Desktop Chrome | Desktop Chrome 1280x720 | `*.desktop.spec.ts`, `basic-*.spec.ts` |
| iPhone 14 Pro | iPhone 14 Pro | `*.mobile.spec.ts`, `safe-areas.spec.ts`, `theme-*.spec.ts` |
| iPhone 14 Pro Dark | iPhone 14 Pro, dark | `theme-switching.spec.ts` |
| iPhone SE, Samsung Galaxy S23, iPad Pro | respective devices | `*.mobile.spec.ts` / `*.tablet.spec.ts`, `safe-areas.spec.ts` |
| Russian Language | iPhone 14 Pro, `ru-RU` | `language-detection.spec.ts` |
| Performance | iPhone 14 Pro | `performance-*.spec.ts` (no matching files) |
| Accessibility | iPhone 14 Pro, reduced motion | `accessibility.spec.ts` |
| UI-UX Validation | iPhone 14 Pro | `ui-ux-validation.spec.ts` |

Spec files that match no project and are therefore never run: `calendar-filtering.spec.ts`, `feedback-submission.spec.ts`, `goals.spec.ts`, `infinite-loop-detection.spec.ts`, `meal-card-expansion.spec.ts`, `meal-deletion-flow.spec.ts`, `meal-detail.spec.ts`, `meal-editing-flow.spec.ts`, `meals-history.spec.ts`, `mobile-devices.spec.ts`, `photo-carousel.spec.ts`, `stats-responsive.spec.ts`, `today.spec.ts`. Run `bunx playwright test --list` to see what is collected.

## Happy Path Test Scenarios

These scenarios describe the current UI and can be run manually (in Telegram or at `http://localhost:3000`).

### Scenario 1: First-Time User

#### Test Steps
1. **Launch Mini App**
   - Open Telegram bot
   - Send `/start` command
   - Tap "Open Mini App" button
   - **Expected**: App loads on the Meals page (`/`)

2. **View Meals Screen**
   - **Expected**: Heading "Meals"
   - **Expected**: Empty state "No meals logged for this date"
   - **Expected**: Bottom navigation shows Meals (active), Stats, Goals

3. **Set Daily Goal**
   - Navigate to Goals tab
   - Tap "Edit Goal"
   - Enter "2000" calories
   - Tap "Save"
   - **Expected**: Modal closes and the goal shows "2000 kcal"
   - **Expected**: Today's progress bar reflects consumed calories

### Scenario 2: Adding and Editing a Meal

#### Test Steps
1. **Add Meal via Bot**
   - Send food photo to bot
   - Wait for AI analysis
   - **Expected**: Bot responds with calorie estimate

2. **View Meal in Mini App**
   - Reopen or refresh the Mini App
   - **Expected**: Meal card appears in the list with thumbnail, time, kcal, and P/C/F
   - **Expected**: Daily summary updates with total kcal and macros

3. **Edit Meal Details**
   - Tap "Edit" on the meal card
   - **Expected**: Edit modal opens with description and protein/carbs/fat inputs
   - Change a macro value
   - **Expected**: Calories recalculate (`protein*4 + carbs*4 + fat*9`)
   - Tap "Save"
   - **Expected**: Modal closes and the list/summary update

4. **Delete Meal**
   - Tap "Delete" on the meal card
   - **Expected**: Confirmation modal "Are you sure you want to delete this meal?"
   - Tap "Confirm Delete"
   - **Expected**: Meal is removed and the summary updates

### Scenario 3: Viewing Statistics

#### Test Steps
1. **Navigate to Stats**
   - Tap "Stats" in navigation
   - **Expected**: Heading "Nutrition Statistics"
   - **Expected**: Period buttons "Last 7 Days" (selected), "Last 30 Days", "Last 90 Days"

2. **View Data**
   - **Expected**: Summary cards (average daily calories, total meals)
   - **Expected**: Calories-over-time line chart and macro distribution pie chart
   - **Expected**: "No Data Yet" empty state when there are no meals in the period

3. **Change Period**
   - Tap "Last 30 Days"
   - **Expected**: Button becomes selected (`aria-pressed="true"`) and charts reload

### Scenario 4: Feedback

#### Test Steps
1. Open `/feedback` (not linked from the bottom navigation)
2. Enter a message (max 5000 characters; remaining count is shown)
3. Tap "Send Feedback"
   - **Expected**: "Thank you! We received your feedback."

### Scenario 5: Error Handling

#### Test Steps
1. **Invalid Goal**
   - Go to Goals, tap "Edit Goal"
   - Enter "100" and tap "Save"
   - **Expected**: "Daily calorie goal must be between 500 and 10,000"

2. **Failed Mutation**
   - Stop the backend and try to save or delete a meal
   - **Expected**: Error banner on the Meals page

3. **Render Error**
   - **Expected**: `ErrorBoundary` shows "Something went wrong" with a reload button

## Test Implementation

### Telegram WebApp Mocking
There is no shared base fixture; specs import `test`/`expect` from `@playwright/test` directly. Specs that need Telegram data inject it with `page.addInitScript()`:

```typescript
await page.addInitScript(() => {
  (window as any).Telegram = {
    WebApp: {
      ready: () => {},
      expand: () => {},
      initData: 'test_init_data',
      initDataUnsafe: { user: { id: 12345, first_name: 'Test', language_code: 'en' } },
      colorScheme: 'light',
      themeParams: {},
    },
  };
});
```

Without `initData`, `src/main.tsx` skips WebApp initialization and the API client sends `VITE_DEV_USER_ID` (or a default dev ID) as `x-user-id` in dev mode, which the backend accepts only with `ALLOW_INSECURE_USER_ID_HEADER=true`. With `initData` present, it sends `Authorization: tma <initData>` instead.

### API Mocking
API calls are mocked per test with `page.route()` / `context.route()`:

```typescript
await page.route('**/api/v1/meals**', async (route) => {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ meals: [], total: 0 }),
  });
});
await page.goto('/');
```

Response shapes must match the Orval-generated types in `src/api/model/` (e.g. `MealsListResponse`, `DailySummary`, `GoalResponse`).

### Selectors
Prefer role/text selectors that match the real UI, for example:

```typescript
await expect(page.getByRole('heading', { name: 'Meals' })).toBeVisible();
await page.getByRole('button', { name: 'Edit Goal' }).click();
await expect(page.getByRole('dialog')).toBeVisible();
```

Components render almost no `data-testid`s (only `modal-backdrop` in `Modal`).

## Running Tests

### Local Development
```bash
# Run all collected E2E tests (starts the dev server if not running)
bun run test:e2e

# Headed mode
bun run test:e2e:headed

# Run specific test file
bunx playwright test tests/e2e/accessibility.spec.ts

# Run one project
bunx playwright test --project="UI-UX Validation"

# Run with UI mode
bunx playwright test --ui

# List collected tests
bunx playwright test --list

# Open the HTML report
bunx playwright show-report
```

### CI/CD Pipeline
E2E tests are not part of CI. `.github/workflows/frontend-ci.yml` runs `bun install --frozen-lockfile`, verifies generated API code (`bun run api:gen` + `bun run format`), then `bun run test` (Vitest) and `bun run build`.

## Test Data Management

### Mock Data
There is no shared E2E fixtures directory; mock data is defined inline in each spec. For unit tests, MSW handlers live in `src/test/handlers.ts`.

### Artifacts
Screenshots (on failure), videos (retained on failure), and traces (on first retry) go to `test-results/`; the HTML report goes to `playwright-report/`. Both are gitignored.

## Performance Testing

`tests/e2e/ui-ux-validation.spec.ts` contains performance checks (FPS during chart animations, page load under 2 seconds, JavaScript bundle under 250KB). The `Performance` project in `playwright.config.ts` matches `performance-*.spec.ts`, but no such files exist.

## Accessibility Testing

`tests/e2e/accessibility.spec.ts` (Accessibility project) uses `@axe-core/playwright`:

```typescript
import AxeBuilder from '@axe-core/playwright';

const results = await new AxeBuilder({ page })
  .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
  .analyze();
expect(results.violations).toHaveLength(0);
```

Keyboard navigation tests (tab order, focus in modals) are in `tests/e2e/ui-ux-validation.spec.ts`.

## Maintenance

### Regular Updates
- Update specs when UI text, routes, or components change (many current specs are stale)
- Keep file names in sync with project `testMatch` patterns, or the spec will not run
- Review and update test scenarios based on feature changes
- Monitor test execution time and optimize as needed

### Documentation Updates
- Keep test scenarios current with UI changes
- Maintain mock data consistency with `src/api/model/`
- Document any new test patterns or utilities
