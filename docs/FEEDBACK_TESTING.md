# Feedback Feature Testing Documentation

This document describes the comprehensive test coverage for the feedback submission feature implemented in `005-mini-app-improvements`.

## Overview

The feedback feature has been thoroughly tested across all layers:
- **Backend API Tests**: API contract validation and error handling
- **Backend Service Tests**: Business logic and timezone handling
- **Frontend Unit Tests**: `FeedbackPage` rendering and submit-button state (Vitest)
- **Frontend E2E Tests**: Playwright spec (currently not matched by any Playwright project; see below)

**Feature under test** (`backend/src/calorie_track_ai_bot/api/v1/feedback.py`, `services/feedback_service.py`):
- `POST /api/v1/feedback` (201) and `GET /api/v1/feedback/{feedback_id}`; both require Telegram `initData` (`Authorization: tma <initData>`), or `x-user-id` when the backend runs with `ALLOW_INSECURE_USER_ID_HEADER=true`
- Rows are inserted into the `feedback_submissions` table (defined in `backend/infra/schema.sql`)
- After insert, a Telegram message is sent to `ADMIN_NOTIFICATION_CHAT_ID` when `FEEDBACK_NOTIFICATIONS_ENABLED` is `true` (the default); notification errors are logged and do not fail the submission

## Test Files

### Backend Tests

#### API Tests: `backend/tests/api/v1/test_feedback.py`
Tests the REST API endpoints for feedback submission and retrieval.

**Test Classes:**
- `TestFeedbackSubmissionContract` (9 tests)
- `TestFeedbackRetrievalContract` (3 tests)

**Coverage:**
- ✅ Successful feedback submission with valid data
- ✅ Authentication validation (Telegram initData, or x-user-id with the insecure-header flag)
- ✅ Message type validation (feedback, bug, question, support)
- ✅ Empty message validation
- ✅ Message length validation (max 5000 characters)
- ✅ User context handling (optional)
- ✅ Invalid user ID handling
- ✅ Feedback retrieval by ID
- ✅ 404 for non-existent feedback
- ✅ 401 for retrieval without auth

#### Service Tests: `backend/tests/services/test_feedback_service.py`
Tests the business logic layer and database interactions.

**Test Classes:**
- `TestFeedbackServiceSubmission` (8 tests)
- `TestFeedbackServiceRetrieval` (6 tests)

**Coverage:**
- ✅ **Timezone-aware datetime creation** (critical bug fix validation)
- ✅ Database record insertion with correct fields
- ✅ Response formatting and validation
- ✅ Admin notification sending
- ✅ All message types handling
- ✅ Optional user context handling
- ✅ Graceful notification failure handling
- ✅ Notification disabled mode
- ✅ Feedback retrieval by ID
- ✅ None return for non-existent feedback
- ✅ Admin user display formatting (`_get_user_display`: with/without handle, user not found, special characters)

### Frontend Tests

#### Unit Tests: `frontend/src/pages/feedback/__tests__/FeedbackPage.test.tsx`
Tests the `FeedbackPage` component (`frontend/src/pages/feedback/index.tsx`), which submits via the Orval-generated `useSubmitFeedbackApiV1FeedbackPost` mutation.

**Coverage:**
- ✅ Renders the feedback form
- ✅ Submit button disabled when the message is empty
- ✅ Submit button enabled once text is entered

The allowed `message_type` values are enforced at compile time by the Orval-generated `FeedbackMessageType` (`frontend/src/api/model/feedbackMessageType.ts`); the page always sends `message_type: "feedback"`.

#### E2E Tests: `frontend/tests/e2e/feedback-submission.spec.ts`
End-to-end tests using Playwright.

> **Status:** no project in `frontend/playwright.config.ts` has a `testMatch` that includes this file, so `playwright test` reports "No tests found" for it. The spec also predates the current `FeedbackPage`, which has no draft auto-save, inline validation messages, character-limit warning, or `user_context` payload, and caps input with `maxLength={5000}`. Expect many of these tests to fail until the spec is updated and added to a project.

**Test Suites:**
- `Feedback Form - Basic Functionality` (3 tests)
- `Feedback Form - Character Count` (4 tests)
- `Feedback Form - Validation` (4 tests)
- `Feedback Form - Draft Auto-Save` (3 tests)
- `Feedback Form - Submission` (4 tests)
- `Feedback Form - Error Handling` (5 tests)
- `Feedback Form - Touch Targets` (2 tests)

**Coverage:**
- ✅ Form element visibility and structure
- ✅ Accessibility attributes (ARIA, labels)
- ✅ Minimum 16px font size (prevents iOS zoom)
- ✅ Character count updates
- ✅ Character limit warnings
- ✅ Maximum length acceptance (5000 chars)
- ✅ Empty message validation
- ✅ Whitespace-only message validation
- ✅ Message length validation
- ✅ Error clearing on input
- ✅ Draft auto-save to localStorage
- ✅ Draft restoration on page load
- ✅ Draft clearing after successful submission
- ✅ Successful submission flow
- ✅ Submit button disabled during submission
- ✅ **Correct message_type sent ('feedback' not 'other')** (bug fix validation)
- ✅ User context inclusion
- ✅ 401 authentication error handling
- ✅ Backend error message display
- ✅ Network failure handling
- ✅ Message preservation after failed submission
- ✅ User ID availability checking
- ✅ Minimum 48px touch target for button
- ✅ Proper spacing between elements

## Running Tests

### Backend Tests

Run all feedback tests:
```bash
cd backend
uv run pytest tests/api/v1/test_feedback.py tests/services/test_feedback_service.py -v
```

Run with coverage:
```bash
cd backend
uv run pytest tests/api/v1/test_feedback.py tests/services/test_feedback_service.py --cov=src --cov-report=html
```
Use `--cov=src` and read the `api/v1/feedback.py` and `services/feedback_service.py` rows; per-module `--cov` paths currently report "No data to report".

Run specific test:
```bash
cd backend
uv run pytest tests/services/test_feedback_service.py::TestFeedbackServiceSubmission::test_submit_feedback_creates_timezone_aware_datetime -v
```

### Frontend Tests

Run unit tests:
```bash
cd frontend
bun run test src/pages/feedback/__tests__/FeedbackPage.test.tsx
```

E2E commands (these find no tests until the spec is matched by a Playwright project, see status above):
```bash
cd frontend
bunx playwright test tests/e2e/feedback-submission.spec.ts
bunx playwright test tests/e2e/feedback-submission.spec.ts --ui
bunx playwright test tests/e2e/feedback-submission.spec.ts -g "should successfully submit valid feedback"
```

## Critical Bug Fix Tests

These tests specifically validate the two bugs that were fixed:

### Bug #1: Invalid message_type 'other'
**Problem**: Frontend was sending `message_type: 'other'` but backend only accepts: `'feedback', 'bug', 'question', 'support'`

**Tests:**
- ✅ `backend/tests/api/v1/test_feedback.py::test_submit_feedback_validates_message_type` - Verifies 'other' is rejected
- ✅ `backend/tests/api/v1/test_feedback.py::test_submit_feedback_validates_message_types` - Verifies all valid types accepted
- ✅ Orval-generated `FeedbackMessageType` type - TypeScript compile-time check (via `tsc -b` in `bun run build`)
- `frontend/tests/e2e/feedback-submission.spec.ts::should send correct message_type in request` - E2E validation (not currently run, see above)

### Bug #2: Naive datetime without timezone
**Problem**: Backend used `datetime.utcnow()` creating naive datetimes, but Pydantic requires timezone-aware datetimes

**Tests:**
- ✅ `backend/tests/services/test_feedback_service.py::test_submit_feedback_creates_timezone_aware_datetime` - **Primary validation**
  - Verifies `created_at` has timezone info
  - Checks `tzinfo` is not None
  - Validates timezone is UTC

This test is **critical** and will fail if the code regresses to using `datetime.utcnow()`.

## Test Results Summary

```
Backend Tests: 26 tests
├── API Tests:     12
└── Service Tests: 14

Frontend Tests:
├── Unit Tests:    3 (FeedbackPage.test.tsx)
└── E2E Tests:     25 defined, not matched by any Playwright project
```

## Continuous Integration

Tests run automatically on pull requests and pushes to `main` that touch the relevant paths:
- `.github/workflows/backend-ci.yml` runs the full backend suite (`uv run pytest -q`), which includes both feedback test files
- `.github/workflows/frontend-ci.yml` runs Vitest (`bun run test`), which includes `FeedbackPage.test.tsx`; it can also be triggered manually (`workflow_dispatch`)

Playwright E2E tests are not run in CI.

## Test Maintenance

### Adding New Tests
When adding new feedback functionality:
1. Add API contract tests to `test_feedback.py`
2. Add business logic tests to `test_feedback_service.py`
3. Add component tests to `frontend/src/pages/feedback/__tests__/FeedbackPage.test.tsx` and E2E tests to `feedback-submission.spec.ts`
4. Update this documentation

### Test Data
Tests use:
- Mock database pool for database operations
- Mock bot for Telegram notifications
- Playwright mock routes for API responses
- Mock localStorage for draft persistence

### Common Test Patterns

**Backend API Test Pattern:**
```python
def test_something(self):
    with patch("src.calorie_track_ai_bot.api.v1.feedback.get_feedback_service") as mock_service:
        # Setup mocks
        # Make request
        # Assertions
```

**Backend Service Test Pattern:**
```python
@pytest.mark.anyio
async def test_something(self, feedback_service):
    # Use feedback_service fixture
    # Call service methods
    # Assertions
```

**E2E Test Pattern:**
```typescript
test('should do something', async ({ page }) => {
    await page.route('**/api/v1/feedback', async (route) => {
        // Mock API response
    });
    // Interact with page
    // Assertions
});
```

## Known Issues
- `feedback-submission.spec.ts` is not matched by any Playwright project and is out of date with the current `FeedbackPage`.

## Related Documentation
- [API Documentation](../backend/README.md)
- [E2E Testing Guide](../frontend/docs/e2e-testing-guide.md)
