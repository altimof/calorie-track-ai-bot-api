# Performance & Accessibility Guidelines

## Lighthouse Performance Targets

### Mobile Performance Goals
- **First Contentful Paint (FCP)**: < 1.8s
- **Largest Contentful Paint (LCP)**: < 2.5s
- **First Input Delay (FID)**: < 100ms
- **Cumulative Layout Shift (CLS)**: < 0.1
- **Speed Index**: < 3.4s
- **Time to Interactive (TTI)**: < 3.8s

### Accessibility Goals
- **Accessibility Score**: 100/100
- **Color Contrast**: AA compliance (4.5:1 for normal text, 3:1 for large text)
- **Keyboard Navigation**: Full support
- **Screen Reader**: Compatible with major screen readers
- **Focus Management**: Visible and logical focus order

## Performance Optimizations Implemented

### 1. Code Splitting & Lazy Loading
```typescript
// src/app.tsx: route-based code splitting
const Meals = lazy(() => import("@/pages/meals"));
const Stats = lazy(() => import("@/pages/stats"));
const Goals = lazy(() => import("@/pages/goals"));
const Feedback = lazy(() => import("@/pages/feedback"));
```
The `Suspense` boundary (spinner fallback) lives in `src/components/layout/AppLayout.tsx`.

### 2. Image Optimization
- `MealCard` renders the backend-provided `thumbnailUrl`; full-size `fullUrl` is used only by `PhotoCarousel`
- No WebP conversion, `srcset`, or `loading="lazy"` yet

### 3. Bundle Optimization
- Tree shaking and minification (Vite production build)
- Vendor chunk splitting via `codeSplitting.groups` in `vite.config.ts`: `react-vendor`, `chart-vendor` (Recharts), `i18n-vendor`
- `chunkSizeWarningLimit: 600` (KB)

### 4. Caching Strategy
- In-memory API response caching via TanStack Query (`staleTime` 50 minutes, `retry: 1`, `refetchOnWindowFocus: false`)
- No service worker / offline support, and theme/language overrides are not persisted

### 5. Network Optimization
- Parallel data fetching (independent query hooks per page)
- Request deduplication (TanStack Query shares in-flight queries by key)
- Targeted cache invalidation after mutations (meals, daily summary, goals)
- Request cancellation via `AbortSignal` (Orval `query.signal: true`)

## Accessibility Features Implemented

### 1. Semantic HTML
- One `<h1>` per page; `<h3>` chart headings in `StatsCharts`
- `<main>` in `AppLayout`, `<nav aria-label=...>` in `Navigation`
- `<html lang="en">` in `index.html`

### 2. ARIA Labels and Roles
```tsx
// Navigation: active tab
<button aria-current={isActive ? "page" : undefined}>

// Modal
<div role="dialog" aria-modal="true" aria-label={title}>

// PeriodSelector
<div role="group" aria-label={t("statistics.period.title")}>
  <button aria-pressed={selected === period}>

// Skeleton
<div role="status" aria-busy="true" aria-label="Loading" />
```
Icon/action buttons (meal edit/delete, goal edit, feedback submit, error reload) and `MealEditor` inputs have translated `aria-label`s. The goals progress bar is a styled `div` without `role="progressbar"`.

### 3. Keyboard Navigation
- All interactive elements are native `<button>`/`<input>`/`<textarea>`, so they are focusable in DOM order
- `Modal` closes on Escape (no focus trap)
- No skip links or custom keyboard shortcuts

### 4. Color and Contrast
- All colors come from Telegram theme variables (`--tg-*`) via Tailwind `@theme` tokens in `src/app.css`
- Dark mode via `data-theme` on `<html>`, with dark overrides for chart colors
- Contrast is checked by axe-core in `tests/e2e/accessibility.spec.ts`

### 5. Screen Reader Support
- Translated labels for controls (i18next, EN/RU)
- `MealCard` thumbnails use the meal description as `alt`; `PhotoCarousel` images use empty `alt`
- No `aria-live` regions yet; mutation errors are rendered as plain text

## Performance Testing Checklist

### Pre-deployment Tests
- [ ] Lighthouse audit (mobile) > 90
- [ ] Core Web Vitals pass
- [ ] Bundle size analysis
- [ ] Network waterfall analysis
- [ ] Memory leak detection

### Accessibility Testing
- [ ] Lighthouse accessibility audit = 100
- [ ] Keyboard-only navigation test
- [ ] Screen reader testing (NVDA, JAWS, VoiceOver)
- [ ] Color contrast validation
- [ ] Focus management verification

## Monitoring and Metrics

### Performance Monitoring
`@vercel/analytics` and `@vercel/speed-insights` are listed in `package.json` dependencies but are not wired into the app (no `<Analytics />` / `<SpeedInsights />` in `src/`). There is no `web-vitals` integration.

### Error Tracking
- `ErrorBoundary` logs render errors with `console.error`
- API errors surface as `ApiError` (status + detail) from `src/api/client.ts`

## Mobile-Specific Optimizations

### 1. Touch Interactions
- Full-width bottom navigation buttons
- Modal renders as a bottom sheet on small screens

### 2. Viewport Optimization
- Viewport meta tag with `viewport-fit=cover` (zoom disabled) in `index.html`
- Mobile-first responsive layout
- Safe area handling: `--safe-area-*` CSS variables from `env(safe-area-inset-*)` in `src/app.css`, applied in `AppLayout` and `Navigation`; `TelegramProvider` re-reads them on resize

### 3. Network Considerations
- Skeleton loading states while queries load
- Slow/failed network scenarios simulated in `tests/e2e/ui-ux-validation.spec.ts`

## Implementation Examples

### Optimized Component Loading
```tsx
// src/components/layout/AppLayout.tsx
<ErrorBoundary>
  <Suspense fallback={<PageLoading />}>
    <Outlet />
  </Suspense>
</ErrorBoundary>
```

### Efficient Data Fetching
```typescript
// src/pages/stats/index.tsx: both queries run in parallel and are cached/deduplicated by TanStack Query
const { data: dailyRaw, isLoading: loadingDaily } =
  useGetDailyStatisticsApiV1StatisticsDailyGet(dateRange);
const { data: macroRaw, isLoading: loadingMacro } =
  useGetMacroStatisticsApiV1StatisticsMacrosGet(dateRange);
```

## Continuous Improvement

### Regular Audits
- Weekly Lighthouse audits
- Monthly accessibility reviews
- Quarterly performance regression tests
- User feedback integration

### Performance Budgets
- JavaScript bundle: < 250KB gzipped
- CSS bundle: < 50KB gzipped
- Images: < 100KB per image
- Fonts: < 100KB total

### Monitoring Dashboard
- Real-time performance metrics
- Error rate tracking
- User experience scores
- Accessibility compliance status

## Resources

### Tools
- [Lighthouse](https://developers.google.com/web/tools/lighthouse)
- [Web Vitals](https://web.dev/vitals/)
- [axe-core](https://github.com/dequelabs/axe-core) (used via `@axe-core/playwright`)
- [Pa11y](https://pa11y.org/)

### Guidelines
- [WCAG 2.1 AA](https://www.w3.org/WAI/WCAG21/quickref/)
- [Web Performance Best Practices](https://web.dev/fast/)
- [Mobile Web Best Practices](https://developers.google.com/web/fundamentals/design-and-ux/responsive)

### Testing
- [Chrome DevTools](https://developers.google.com/web/tools/chrome-devtools)
- [WebPageTest](https://www.webpagetest.org/)
- [Accessibility Insights](https://accessibilityinsights.io/)
