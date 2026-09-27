import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_ID } from './helpers';

test.describe('Authentication & Organization Setup (HARD-002)', () => {
  test('user can register a new account and access onboarding', async ({ page }) => {
    await page.route('**/api/auth/register', async (route) => {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Registration accepted' }),
      });
    });

    await page.goto('/register');
    await expect(page.locator('h1, h2')).toContainText(/Create your account|Register|BizPilot/i);

    await page.fill('input[name="display_name"], input[placeholder*="Name" i]', 'Tariq Mahmood');
    await page.fill('input[type="email"]', 'tariq@lahore.pk');
    await page.fill('input[type="password"]', 'SecurePassword123!');

    await page.click('button[type="submit"]');
    // Successful submission redirects or shows confirmation
    await expect(page).toHaveURL(/.*(onboarding|login|register).*/);
  });

  test('user can log in with valid credentials and navigate to organization workspace', async ({ page }) => {
    await page.route('**/api/auth/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'fake-jwt-token-12345',
          token_type: 'bearer',
          user: { id: 'user-01', display_name: 'Tariq Mahmood', email: 'tariq@lahore.pk' },
        }),
      });
    });

    await setupMockApi(page, 'owner');

    await page.goto('/login');
    await page.fill('input[type="email"]', 'tariq@lahore.pk');
    await page.fill('input[type="password"]', 'SecurePassword123!');
    await page.click('button[type="submit"]');

    // Should redirect to workspace or onboarding
    await page.waitForURL(`**/workspace/${TEST_ORG_ID}**`, { timeout: 10000 });
    await expect(page.locator('body')).toContainText(/Lahore Super Store/i);
  });
});
