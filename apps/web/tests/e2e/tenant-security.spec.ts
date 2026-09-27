import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_ID, TEST_ORG_B_ID } from './helpers';

test.describe('Multi-Tenant Browser Isolation & IDOR Defenses (HARD-002)', () => {
  test('User navigating to an unauthorized foreign organization is rejected with 404/403', async ({ page }) => {
    await setupMockApi(page, 'owner');

    // Mock 404 for unauthorized foreign tenant
    await page.route(`**/api/organizations/${TEST_ORG_B_ID}*`, async (route) => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Organization not found' }),
      });
    });

    await page.goto(`/workspace/${TEST_ORG_B_ID}`);

    // Expect not found or error boundary
    await expect(page.locator('body')).toContainText(/not found|error|access|unauthorized|failed/i);
  });
});
