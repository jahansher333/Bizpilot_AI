import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_ID } from './helpers';

test.use({ viewport: { width: 375, height: 812 }, hasTouch: true });

const PAGES = ['', '/orders', '/orders/new', '/catalog', '/inventory', '/customers', '/payments', '/expenses', '/assistant', '/team', '/settings'];

test.describe('Phone width (R10b)', () => {
  for (const path of PAGES) {
    test(`no sideways scrolling at 375px: ${path || '/dashboard'}`, async ({ page }) => {
      await setupMockApi(page, 'owner');
      await page.goto(`/workspace/${TEST_ORG_ID}${path}`);
      await expect(page.locator('h1').first()).toBeVisible();
      await page.waitForTimeout(300);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, `page is ${overflow}px wider than the screen`).toBeLessThanOrEqual(0);
    });
  }

  test('creates an order through the 4-step phone flow', async ({ page }) => {
    await setupMockApi(page, 'owner');
    await page.goto(`/workspace/${TEST_ORG_ID}/orders/new`);

    await expect(page.getByRole('heading', { name: 'Add products' })).toBeVisible();
    await expect(page.getByText('Step 1 of 4')).toBeVisible();
    await page.getByRole('button', { name: /Kagzi Badam 1kg, PKR 1,500/ }).click();
    await page.getByRole('button', { name: /View cart/ }).click();

    await expect(page.getByRole('heading', { name: 'Cart' })).toBeVisible();
    await page.getByRole('button', { name: 'Increase Kagzi Badam 1kg' }).click();
    await expect(page.getByLabel('Quantity of Kagzi Badam 1kg')).toHaveText('2');
    await page.getByRole('button', { name: 'Choose customer' }).click();

    await expect(page.getByRole('heading', { name: 'Customer' })).toBeVisible();
    await page.getByRole('button', { name: 'Review order' }).click();

    await expect(page.getByRole('heading', { name: 'Review' })).toBeVisible();
    const request = page.waitForRequest((r) => r.url().includes(`/organizations/${TEST_ORG_ID}/orders`) && r.method() === 'POST');
    await page.getByRole('button', { name: 'Complete order · PKR 3,000' }).click();
    expect((await request).postDataJSON().items).toEqual([{ product_id: 'prod-01', quantity: 2, unit_price_minor: 150000 }]);
    await expect(page.getByRole('heading', { name: 'Order completed' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Record payment' })).toBeVisible();
  });
});
