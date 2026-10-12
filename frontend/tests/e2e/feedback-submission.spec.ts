/**
 * E2E Tests for Feedback Submission
 * Feature: 005-mini-app-improvements
 *
 * Tests cover:
 * - Feedback form validation
 * - Successful submission flow
 * - Error handling (auth errors, validation errors)
 * - Character count and limits
 * - Draft auto-save functionality
 */

import { test, expect, Page } from '@playwright/test';

// Helper to navigate to feedback page
async function navigateToFeedback(page: Page) {
  await page.goto('/feedback');
  await page.waitForLoadState('networkidle');
}

// Helper to fill feedback form
async function fillFeedbackForm(page: Page, message: string) {
  const textarea = page.locator('textarea#message-content');
  await textarea.fill(message);
}

// Helper to submit feedback
async function submitFeedback(page: Page) {
  const submitButton = page.locator('button[type="submit"]');
  await submitButton.click();
}

test.describe('Feedback Form - Basic Functionality', () => {
  test('should display feedback form with all required elements', async ({ page }) => {
    await navigateToFeedback(page);

    // Check page title
    await expect(page.locator('h2')).toContainText('Feedback & Support');

    // Check form elements
    await expect(page.locator('label[for="message-content"]')).toBeVisible();
    await expect(page.locator('textarea#message-content')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();

    // Check character counter
    await expect(page.locator('#character-count')).toContainText('0 / 5000');

    // Check help text
    await expect(page.locator('text=We review all feedback')).toBeVisible();
  });

  test('should have proper accessibility attributes', async ({ page }) => {
    await navigateToFeedback(page);

    const textarea = page.locator('textarea#message-content');

    // Check ARIA attributes
    await expect(textarea).toHaveAttribute('aria-required', 'true');
    await expect(textarea).toHaveAttribute('aria-describedby', 'character-count');
    await expect(textarea).toHaveAttribute('required', '');

    // Check label association
    const label = page.locator('label[for="message-content"]');
    await expect(label).toBeVisible();
  });

  test('should have minimum 16px font size to prevent iOS zoom', async ({ page }) => {
    await navigateToFeedback(page);

    const textarea = page.locator('textarea#message-content');
    const fontSize = await textarea.evaluate((el) =>
      window.getComputedStyle(el).fontSize
    );

    // Parse font size (e.g., "16px" -> 16)
    const fontSizeValue = parseInt(fontSize);
    expect(fontSizeValue).toBeGreaterThanOrEqual(16);
  });
});

test.describe('Feedback Form - Character Count', () => {
  test('should update character count as user types', async ({ page }) => {
    await navigateToFeedback(page);

    const textarea = page.locator('textarea#message-content');
    const characterCount = page.locator('#character-count');

    // Type message
    await textarea.fill('Hello');
    await expect(characterCount).toContainText('5 / 5000');

    // Type more
    await textarea.fill('Hello World!');
    await expect(characterCount).toContainText('12 / 5000');
  });

  test('should show warning when approaching character limit', async ({ page }) => {
    await navigateToFeedback(page);

    const textarea = page.locator('textarea#message-content');
    const characterCount = page.locator('#character-count');

    // Fill with text approaching limit (4600 characters - within 500 of limit)
    const longMessage = 'x'.repeat(4600);
    await textarea.fill(longMessage);

    // Check that character count is displayed
    await expect(characterCount).toContainText('4600 / 5000');

    // Check that remaining characters are shown
    await expect(characterCount).toContainText('400');
    await expect(characterCount).toContainText('characters remaining');
  });

  test('should accept message at maximum length (5000 chars)', async ({ page }) => {
    await navigateToFeedback(page);

    const textarea = page.locator('textarea#message-content');
    const maxMessage = 'x'.repeat(5000);

    await textarea.fill(maxMessage);

    // Should show 5000 / 5000
    await expect(page.locator('#character-count')).toContainText('5000 / 5000');
  });

  test('should allow typing beyond 5000 characters (client-side)', async ({ page }) => {
    await navigateToFeedback(page);

    const textarea = page.locator('textarea#message-content');

    // Try to fill with more than 5000 characters
    const tooLongMessage = 'x'.repeat(5001);
    await textarea.fill(tooLongMessage);

    // Character count should show 5001 / 5000
    await expect(page.locator('#character-count')).toContainText('5001 / 5000');
  });
});

test.describe('Feedback Form - Validation', () => {
  test('should show error for empty message', async ({ page }) => {
    await navigateToFeedback(page);

    // Try to submit without entering message
    await submitFeedback(page);

    // Should show validation error
    await expect(page.locator('.error-message')).toBeVisible();
    await expect(page.locator('.error-message')).toContainText('Please enter a message');
  });

  test('should show error for whitespace-only message', async ({ page }) => {
    await navigateToFeedback(page);

    // Fill with only whitespace
    await fillFeedbackForm(page, '   \n\n   ');
    await submitFeedback(page);

    // Should show validation error
    await expect(page.locator('.error-message')).toBeVisible();
    await expect(page.locator('.error-message')).toContainText('Please enter a message');
  });

  test('should show error for message exceeding 5000 characters', async ({ page }) => {
    await navigateToFeedback(page);

    // Fill with message exceeding limit
    const tooLongMessage = 'x'.repeat(5001);
    await fillFeedbackForm(page, tooLongMessage);
    await submitFeedback(page);

    // Should show validation error
    await expect(page.locator('.error-message')).toBeVisible();
    await expect(page.locator('.error-message')).toContainText('exceeds maximum length');
  });

  test('should clear error message when user starts typing', async ({ page }) => {
    await navigateToFeedback(page);

    // Trigger validation error
    await submitFeedback(page);
    await expect(page.locator('.error-message')).toBeVisible();

    // Start typing
    const textarea = page.locator('textarea#message-content');
    await textarea.fill('T');

    // Error should be cleared
    await expect(page.locator('.error-message')).not.toBeVisible();
  });
});

test.describe('Feedback Form - Draft Auto-Save', () => {
  test('should save draft to localStorage', async ({ page }) => {
    await navigateToFeedback(page);

    const message = 'This is a draft message';
    await fillFeedbackForm(page, message);

    // Wait a moment for auto-save
    await page.waitForTimeout(100);

    // Check localStorage
    const draft = await page.evaluate(() => {
      const stored = localStorage.getItem('feedback_draft');
      return stored ? JSON.parse(stored) : null;
    });

    expect(draft).toBeTruthy();
    expect(draft.messageContent).toBe(message);
    expect(draft.savedAt).toBeTruthy();
  });

  test('should restore draft from localStorage on page load', async ({ page }) => {
    // Set a draft in localStorage before navigating
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('feedback_draft', JSON.stringify({
        messageContent: 'Restored draft message',
        savedAt: new Date().toISOString(),
      }));
    });

    // Navigate to feedback page
    await navigateToFeedback(page);

    // Check that draft is restored
    const textarea = page.locator('textarea#message-content');
    await expect(textarea).toHaveValue('Restored draft message');

    // Character count should also be updated
    await expect(page.locator('#character-count')).toContainText('22 / 5000');
  });

  test('should clear draft after successful submission', async ({ page }) => {
    // Mock successful API response
    await page.route('**/api/v1/feedback', async (route) => {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '123e4567-e89b-12d3-a456-426614174000',
          status: 'new',
          created_at: new Date().toISOString(),
          message: 'Thank you! We received your feedback.',
        }),
      });
    });

    await navigateToFeedback(page);

    // Fill and submit
    await fillFeedbackForm(page, 'Test feedback');
    await submitFeedback(page);

    // Wait for success message
    await expect(page.locator('.success-message')).toBeVisible();

    // Check that draft is cleared from localStorage
    const draft = await page.evaluate(() => localStorage.getItem('feedback_draft'));
    expect(draft).toBeNull();

    // Form should be cleared
    const textarea = page.locator('textarea#message-content');
    await expect(textarea).toHaveValue('');
  });
});

test.describe('Feedback Form - Submission', () => {
  test('should successfully submit valid feedback', async ({ page }) => {
    // Mock successful API response
    await page.route('**/api/v1/feedback', async (route) => {
      const request = route.request();
      const postData = request.postDataJSON();

      // Validate request payload
      expect(postData.message_type).toBe('feedback');
      expect(postData.message_content).toBe('This is test feedback');
      expect(postData.user_context).toBeTruthy();

      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '123e4567-e89b-12d3-a456-426614174000',
          status: 'new',
          created_at: new Date().toISOString(),
          message: 'Thank you! We received your feedback.',
        }),
      });
    });

    await navigateToFeedback(page);

    // Fill and submit
    await fillFeedbackForm(page, 'This is test feedback');
    await submitFeedback(page);

    // Should show success message
    await expect(page.locator('.success-message')).toBeVisible();
    await expect(page.locator('.success-message')).toContainText('Thank you');

    // Form should be cleared
    const textarea = page.locator('textarea#message-content');
    await expect(textarea).toHaveValue('');
    await expect(page.locator('#character-count')).toContainText('0 / 5000');
  });

  test('should disable submit button while submitting', async ({ page }) => {
    // Mock slow API response
    await page.route('**/api/v1/feedback', async (route) => {
      await page.waitForTimeout(1000); // Simulate slow response
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '123e4567-e89b-12d3-a456-426614174000',
          status: 'new',
          created_at: new Date().toISOString(),
          message: 'Thank you!',
        }),
      });
    });

    await navigateToFeedback(page);

    await fillFeedbackForm(page, 'Test feedback');

    const submitButton = page.locator('button[type="submit"]');
    await submitButton.click();

    // Button should be disabled while submitting
    await expect(submitButton).toBeDisabled();
    await expect(submitButton).toContainText('Sending...');

    // Wait for submission to complete
    await expect(page.locator('.success-message')).toBeVisible();

    // Button should be enabled again
    await expect(submitButton).toBeEnabled();
  });

  test('should send correct message_type in request', async ({ page }) => {
    let capturedMessageType: string | undefined;

    await page.route('**/api/v1/feedback', async (route) => {
      const postData = route.request().postDataJSON();
      capturedMessageType = postData.message_type;

      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '123e4567-e89b-12d3-a456-426614174000',
          status: 'new',
          created_at: new Date().toISOString(),
          message: 'Thank you!',
        }),
      });
    });

    await navigateToFeedback(page);
    await fillFeedbackForm(page, 'Test feedback');
    await submitFeedback(page);

    await expect(page.locator('.success-message')).toBeVisible();

    // Verify message_type is 'feedback' (not 'other')
    expect(capturedMessageType).toBe('feedback');
  });

  test('should include user_context in submission', async ({ page }) => {
    let capturedUserContext: any;

    await page.route('**/api/v1/feedback', async (route) => {
      const postData = route.request().postDataJSON();
      capturedUserContext = postData.user_context;

      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '123e4567-e89b-12d3-a456-426614174000',
          status: 'new',
          created_at: new Date().toISOString(),
          message: 'Thank you!',
        }),
      });
    });

    await navigateToFeedback(page);
    await fillFeedbackForm(page, 'Test feedback');
    await submitFeedback(page);

    await expect(page.locator('.success-message')).toBeVisible();

    // Verify user_context contains expected fields
    expect(capturedUserContext).toBeTruthy();
    expect(capturedUserContext.page).toBeTruthy();
    expect(capturedUserContext.user_agent).toBeTruthy();
    expect(capturedUserContext.app_version).toBeTruthy();
    expect(capturedUserContext.language).toBeTruthy();
  });
});

test.describe('Feedback Form - Error Handling', () => {
  test('should show error for 401 authentication failure', async ({ page }) => {
    await page.route('**/api/v1/feedback', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Missing Telegram initData' }),
      });
    });

    await navigateToFeedback(page);
    await fillFeedbackForm(page, 'Test feedback');
    await submitFeedback(page);

    // Should show authentication error
    await expect(page.locator('.error-message')).toBeVisible();
    await expect(page.locator('.error-message')).toContainText('Authentication');
    await expect(page.locator('.error-message')).toContainText('Telegram');
  });

  test('should show error message from backend', async ({ page }) => {
    await page.route('**/api/v1/feedback', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Database connection error' }),
      });
    });

    await navigateToFeedback(page);
    await fillFeedbackForm(page, 'Test feedback');
    await submitFeedback(page);

    // Should show error with backend message
    await expect(page.locator('.error-message')).toBeVisible();
    await expect(page.locator('.error-message')).toContainText('Database connection error');
  });

  test('should show generic error for network failure', async ({ page }) => {
    await page.route('**/api/v1/feedback', async (route) => {
      await route.abort('failed');
    });

    await navigateToFeedback(page);
    await fillFeedbackForm(page, 'Test feedback');
    await submitFeedback(page);

    // Should show generic error
    await expect(page.locator('.error-message')).toBeVisible();
    await expect(page.locator('.error-message')).toContainText('Failed to send');
  });

  test('should preserve message after failed submission', async ({ page }) => {
    await page.route('**/api/v1/feedback', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Server error' }),
      });
    });

    await navigateToFeedback(page);

    const message = 'This message should be preserved';
    await fillFeedbackForm(page, message);
    await submitFeedback(page);

    // Should show error
    await expect(page.locator('.error-message')).toBeVisible();

    // Message should still be in textarea
    const textarea = page.locator('textarea#message-content');
    await expect(textarea).toHaveValue(message);
  });

  test('should show error if user ID is not available', async ({ page }) => {
    // Mock the getUserId function to return null
    await page.addInitScript(() => {
      // Remove Telegram WebApp mock to simulate missing user ID
      (window as any).Telegram = undefined;
      localStorage.clear();
    });

    await navigateToFeedback(page);
    await fillFeedbackForm(page, 'Test feedback');
    await submitFeedback(page);

    // Should show authentication error before making API call
    await expect(page.locator('.error-message')).toBeVisible();
    await expect(page.locator('.error-message')).toContainText('User authentication not available');
    await expect(page.locator('.error-message')).toContainText('Telegram');
  });
});

test.describe('Feedback Form - Touch Targets', () => {
  test('should have minimum 48px height for submit button', async ({ page }) => {
    await navigateToFeedback(page);

    const submitButton = page.locator('button[type="submit"]');
    const box = await submitButton.boundingBox();

    expect(box).toBeTruthy();
    expect(box!.height).toBeGreaterThanOrEqual(48);
  });

  test('should have proper spacing between form elements', async ({ page }) => {
    await navigateToFeedback(page);

    // Check that elements are properly spaced
    const textarea = page.locator('textarea#message-content');
    const submitButton = page.locator('button[type="submit"]');

    const textareaBox = await textarea.boundingBox();
    const buttonBox = await submitButton.boundingBox();

    expect(textareaBox).toBeTruthy();
    expect(buttonBox).toBeTruthy();

    // There should be vertical space between textarea and button
    const gap = buttonBox!.y - (textareaBox!.y + textareaBox!.height);
    expect(gap).toBeGreaterThan(0);
  });
});
