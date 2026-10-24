# Frontend Components Documentation

This document describes the React components used in the Calorie Track AI Bot frontend application. All components are function components (except `ErrorBoundary`) styled with Tailwind CSS v4 utility classes that map to Telegram theme tokens (`bg-tg-bg`, `text-tg-text`, etc., defined in `src/app.css`). All user-facing text goes through `useTranslation()`.

## Meal Components (`src/components/meal/`)

### MealCard
**Location**: `src/components/meal/MealCard.tsx`

Displays a single meal in the meals list.

**Props**:
- `meal`: `MealWithPhotos` (Orval-generated type)
- `onEdit`: `(id: string) => void`, called with the meal ID when Edit is clicked
- `onDelete`: `(id: string) => void`, called with the meal ID when Delete is clicked

**Features**:
- Shows the first photo's thumbnail (if any), description, creation time, calories, and P/C/F macros
- Edit and delete buttons with translated `aria-label`s

### PhotoCarousel
**Location**: `src/components/meal/PhotoCarousel.tsx`

Displays meal photos. Currently not used by any page (covered by unit tests only).

**Props**:
- `photos`: `MealPhotoInfo[]`

**Features**:
- Renders nothing for an empty array, a single full-width image for one photo
- For multiple photos, a horizontally scrollable row sorted by `displayOrder` (plain CSS overflow, no carousel library)

### CalendarPicker
**Location**: `src/components/meal/CalendarPicker.tsx`

Single-date picker built on `react-day-picker`. Currently not used by any page (covered by unit tests only).

**Props**:
- `selected`: `Date`
- `onSelect`: `(date: Date) => void`
- `calendarData?`: `MealCalendarDay[]`; days with `meal_count > 0` are highlighted

### MealEditor
**Location**: `src/components/meal/MealEditor.tsx`

Form for editing a meal's description and macronutrients. Rendered inside a `Modal` by the Meals page.

**Props**:
- `meal`: `MealFormData` (`{ description, calories, protein, carbs, fats }`, exported type)
- `onSave`: `(data: MealFormData) => void`
- `onCancel`: `() => void`
- `saving?`: `boolean`, disables the submit button and shows a saving label

**Features**:
- Recalculates calories (`protein*4 + carbs*4 + fats*9`) when a macro changes
- Numeric inputs with `min={0}`

## Stats Components (`src/components/stats/`)

### StatsCharts
**Location**: `src/components/stats/StatsCharts.tsx`

**Props**:
- `dailyStats`: `DailyStatisticsResponse`
- `macroStats`: `MacroStatisticsResponse | null`

**Features**:
- Empty state when there is no daily data
- Summary cards (average daily calories, total meals)
- Recharts line chart of calories over time and pie chart of macro distribution

### PeriodSelector
**Location**: `src/components/stats/PeriodSelector.tsx`

**Props**:
- `selected`: `Period` (`7 | 30 | 90`, exported type)
- `onChange`: `(period: Period) => void`

Button group (`role="group"`, `aria-pressed`) for 7/30/90-day periods.

## Page Components

Pages live in `src/pages/<name>/index.tsx` (default exports, lazy-loaded in `src/app.tsx`):

### Meals
**Location**: `src/pages/meals/index.tsx` (route `/`)

**Features**:
- Today's meal list (date is fixed to the current day; no calendar filtering in the UI)
- Daily summary (kcal total, macros) and daily goal
- Edit via `MealEditor` in a `Modal`; delete with a confirmation `Modal`
- Error banner on failed mutations

**State Management**:
- Orval-generated TanStack Query hooks: `useGetMealsApiV1MealsGet`, `useGetDailySummaryApiV1DailySummaryDateGet`, `useGetGoalApiV1GoalsGet`, `useUpdateMealApiV1MealsMealIdPatch`, `useDeleteMealApiV1MealsMealIdDelete`
- Invalidates meal and daily-summary queries after mutations
- Local state for UI interactions (editing/deleting meal, error message)

### Stats, Goals, Feedback
- `src/pages/stats/index.tsx` (`/stats`): `PeriodSelector` + `StatsCharts`, using the statistics daily/macros query hooks
- `src/pages/goals/index.tsx` (`/goals`): view and create/update the daily calorie goal (edited in a `Modal`)
- `src/pages/feedback/index.tsx` (`/feedback`): free-text feedback form (max 5000 chars). Not linked from `Navigation`; reachable by URL only

## Layout Components (`src/components/layout/`)

### AppLayout
**Location**: `src/components/layout/AppLayout.tsx`

Layout route element. Wraps the routed page (`<Outlet />`) in `ErrorBoundary` and `Suspense` (spinner fallback), applies top safe-area padding via `--safe-area-top`, and renders `Navigation`.

### Navigation
**Location**: `src/components/layout/Navigation.tsx`

Fixed bottom tab bar with three items: Meals (`/`), Stats (`/stats`), Goals (`/goals`). Active item gets `aria-current="page"`; bottom padding uses `--safe-area-bottom`.

### ErrorBoundary
**Location**: `src/components/layout/ErrorBoundary.tsx`

Class component error boundary.

**Props**:
- `children`: React children to wrap
- `fallback?`: Custom fallback node

**Features**:
- Catches render errors and logs them with `console.error`
- Default fallback shows a translated message, the error text in dev mode, and a reload button

## UI Primitives (`src/components/ui/`)

### Modal
**Location**: `src/components/ui/Modal.tsx`

**Props**:
- `open`: `boolean`
- `onClose`: `() => void`
- `title?`: `string` (used as the dialog's `aria-label`)
- `children`: content

**Features**:
- `role="dialog"`, `aria-modal="true"`
- Closes on Escape and on backdrop click
- Bottom sheet on mobile, centered on `sm` and up

### Skeleton
**Location**: `src/components/ui/Skeleton.tsx`

**Props**:
- `className?`: sizing classes

Pulsing placeholder with `role="status"`, `aria-busy="true"`, `aria-label="Loading"`.

## Hooks

There are no hand-written data hooks. Server state uses the Orval-generated TanStack Query hooks in `src/api/queries/` (regenerate with `bun run api:gen`). Telegram context is available via `useTelegram()` from `src/providers/telegram.tsx`.

## Styling

### Tailwind CSS v4
No CSS modules. Styling is Tailwind utility classes; theme tokens are declared CSS-first with `@theme` in `src/app.css` (no `tailwind.config.js`).

### Theme Integration
Components integrate with Telegram Mini App theming:
- Colors map to Telegram CSS variables (`--tg-*`) via `tg-*` tokens
- `TelegramProvider` sets `data-theme` on `<html>` for light/dark overrides
- Safe-area insets via `--safe-area-*` CSS variables

## Testing

### Component Tests
Each component has a Vitest + React Testing Library test in a sibling `__tests__/` directory, e.g.:
- `src/components/meal/__tests__/MealCard.test.tsx`
- `src/components/meal/__tests__/PhotoCarousel.test.tsx`
- `src/components/meal/__tests__/CalendarPicker.test.tsx`
- `src/components/meal/__tests__/MealEditor.test.tsx`
- `src/components/layout/__tests__/`, `src/components/stats/__tests__/`, `src/components/ui/__tests__/`

### E2E Tests
Playwright specs in `tests/e2e/` cover user workflows, e.g.:
- `meal-editing-flow.spec.ts`
- `meal-deletion-flow.spec.ts`
- `calendar-filtering.spec.ts`

## Performance Considerations

### Image Optimization
- `MealCard` uses the photo `thumbnailUrl`; `PhotoCarousel` uses `fullUrl`

### State Management
- TanStack Query caching (`staleTime` 50 minutes, `refetchOnWindowFocus: false`, configured in `src/app.tsx`)
- `useCallback` for handlers passed to `MealCard`

### Bundle Optimization
- Route-level code splitting with `React.lazy()`
- Vendor chunks (`react-vendor`, `chart-vendor`, `i18n-vendor`) via `codeSplitting.groups` in `vite.config.ts`
