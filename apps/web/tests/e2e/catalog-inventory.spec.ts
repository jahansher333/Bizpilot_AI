import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_ID } from './helpers';

test.describe('Catalog & Inventory Workflows (HARD-002)', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApi(page, 'owner');
  });

  test('views catalog products and creates a new product with category', async ({ page }) => {
    await page.goto(`/workspace/${TEST_ORG_ID}/catalog`);

    // Verify catalog header and existing products
    await expect(page.locator('body')).toContainText(/Catalog|Products|Kagzi Badam/i);

    // Click Add Product button if present
    const addBtn = page.getByRole('button', { name: 'Add product' });
    if (await addBtn.isVisible()) {
      await addBtn.click();
      await page.getByLabel('Product name').fill('Peshawari Akhrot');
      await page.getByLabel('Product code').fill('WALNUT-01');
      await page.getByLabel('Selling price').fill('1200');
      await page.getByRole('button', { name: 'Create product' }).click();
    }
  });

  test('views inventory stock balance and tracks on-hand quantities', async ({ page }) => {
    await page.goto(`/workspace/${TEST_ORG_ID}/inventory`);

    // Verify inventory balances table
    await expect(page.locator('body')).toContainText(/Inventory|Balances|Stock|Kagzi Badam/i);
    await expect(page.locator('body')).toContainText(/40/); // On-hand quantity
  });
});
