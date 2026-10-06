import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_B_ID } from './helpers';

test.describe('Multi-Tenant Browser Isolation & IDOR Defenses (HARD-002)', () => {
  test('User navigating to a workspace they are not a member of is sent to the workspace chooser', async ({ page }) => {
    await setupMockApi(page, 'owner');

    // The backend never returns another tenant's data.
    await page.route(`**/api/organizations/${TEST_ORG_B_ID}/**`, async (route) => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Organization not found' }),
      });
    });

    await page.goto(`/workspace/${TEST_ORG_B_ID}`);

    // FIX-008 route guard: no membership → chooser listing only the user's own workspaces.
    await expect(page).toHaveURL(/\/workspaces$/);
    await expect(page.locator('body')).toContainText('Lahore Super Store');
    await expect(page.locator('body')).not.toContainText(TEST_ORG_B_ID);
  });
});
