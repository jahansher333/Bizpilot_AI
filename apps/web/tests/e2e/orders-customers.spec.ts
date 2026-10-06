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

  test('creates an order from the POS (R6)', async ({ page }) => {
    await page.goto(`/workspace/${TEST_ORG_ID}/orders`);
    await page.getByRole('link', { name: 'New order' }).first().click();
    await expect(page).toHaveURL(new RegExp(`/workspace/${TEST_ORG_ID}/orders/new`));

    await page.getByRole('button', { name: /Kagzi Badam 1kg, PKR 1,500, 40 in stock/ }).click();
    await expect(page.getByLabel('Quantity of Kagzi Badam 1kg')).toHaveText('1');

    const request = page.waitForRequest((r) => r.url().includes(`/organizations/${TEST_ORG_ID}/orders`) && r.method() === 'POST');
    await page.getByRole('button', { name: /Complete order/ }).click();
    const body = (await request).postDataJSON();
    expect(body.items).toEqual([{ product_id: 'prod-01', quantity: 1, unit_price_minor: 150000 }]);
    expect((await request).headers()['idempotency-key']).toBeTruthy();

    await expect(page.getByRole('dialog', { name: /completed/ })).toBeVisible();
  });
});
