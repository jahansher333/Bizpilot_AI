import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_ID } from './helpers';

test.describe('Payments & Operating Expenses Workflows (HARD-002)', () => {
  test('Owner can view payment receipts and inflow history', async ({ page }) => {
    await setupMockApi(page, 'owner');
    await page.goto(`/workspace/${TEST_ORG_ID}/payments`);

    await expect(page.locator('body')).toContainText(/Payments|Bank Transfer|Al-Madina Traders/i);
    await expect(page.locator('body')).toContainText(/10,?000/);
  });

  test('Owner can view operating expenses', async ({ page }) => {
    await setupMockApi(page, 'owner');
    await page.goto(`/workspace/${TEST_ORG_ID}/expenses`);

    await expect(page.locator('body')).toContainText(/Expenses|Operating Expenses|Lahore Goods Transport/i);
    await expect(page.locator('body')).toContainText(/2,?000/);
  });

  test('Staff role is restricted from viewing or recording operating expenses', async ({ page }) => {
    await setupMockApi(page, 'staff');
    await page.goto(`/workspace/${TEST_ORG_ID}/expenses`);

    // Staff receives 403 or permission denial notification/banner
    await expect(page.locator('body')).toContainText(/Forbidden|permission|denied|Restricted|Access Denied/i);
  });
});
