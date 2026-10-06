import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_ID } from './helpers';

test.describe('Payments & Operating Expenses Workflows (HARD-002)', () => {
  test('Owner can view payment receipts and inflow history', async ({ page }) => {
    await setupMockApi(page, 'owner');
    await page.goto(`/workspace/${TEST_ORG_ID}/payments`);

    await expect(page.locator('body')).toContainText(/Payments|Bank Transfer|Al-Madina Traders/i);
    await expect(page.locator('body')).toContainText(/10,?000/);
  });

  test('records a digital wallet payment (R7)', async ({ page }) => {
    await setupMockApi(page, 'staff');
    await page.goto(`/workspace/${TEST_ORG_ID}/payments`);
    await page.getByRole('button', { name: 'Record payment' }).first().click();

    const sheet = page.getByRole('dialog', { name: 'Record payment' });
    await sheet.getByLabel('Amount').fill('2,500');
    await sheet.getByRole('button', { name: 'Digital wallet' }).click();
    await sheet.getByLabel(/Reference/).fill('TID-9001');

    const request = page.waitForRequest((r) => r.url().includes(`/organizations/${TEST_ORG_ID}/payments`) && r.method() === 'POST');
    await sheet.getByRole('button', { name: 'Record PKR 2,500' }).click();
    const sent = await request;
    expect(sent.postDataJSON()).toMatchObject({ amount_minor: 250000, channel: 'digital', external_reference: 'TID-9001' });
    expect(sent.headers()['idempotency-key']).toBeTruthy();
    await expect(sheet.getByRole('heading', { name: 'Payment recorded' })).toBeVisible();
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

    await expect(page.getByRole('heading', { name: 'Expenses are visible to Owners and Managers' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Record expense/ })).toHaveCount(0);
  });
});
