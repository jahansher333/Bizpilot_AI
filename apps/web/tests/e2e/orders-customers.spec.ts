import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_ID } from './helpers';

test.describe('Orders & Customers Lifecycle (HARD-002)', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApi(page, 'owner');
  });

  test('views customers and navigates customer list', async ({ page }) => {
    await page.goto(`/workspace/${TEST_ORG_ID}/customers`);

    await expect(page.locator('body')).toContainText(/Customers|Al-Madina Traders/i);
    await expect(page.locator('body')).toContainText(/03001234567/);
  });

  test('views sales orders and inspects confirmed order details', async ({ page }) => {
    await page.goto(`/workspace/${TEST_ORG_ID}/orders`);

    await expect(page.locator('body')).toContainText(/Orders|Sales Orders|Al-Madina Traders/i);
    await expect(page.locator('body')).toContainText(/15,000/);
  });
});
