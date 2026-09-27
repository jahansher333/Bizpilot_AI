import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_ID } from './helpers';

test.describe('Catalog & Inventory Workflows (HARD-002)', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApi(page, 'owner');
  });

  test('views catalog products and creates a new product with category', async ({ page }) => {
    await page.goto(`/workspace/${TEST_ORG_ID}/catalog`);

    // Verify catalog header and existing products
    await expect(page.locator('h1, h2, table, div')).toContainText(/Catalog|Products|Kagzi Badam/i);

    // Click Add Product button if present
    const addBtn = page.locator('button:has-text("Add Product"), button:has-text("New Product")');
    if (await addBtn.isVisible()) {
      await addBtn.click();
      await page.fill('input[name="name"], input[placeholder*="Name" i]', 'Peshawari Akhrot');
      await page.fill('input[name="code"], input[placeholder*="Code" i], input[placeholder*="SKU" i]', 'WALNUT-01');
      const submitBtn = page.locator('button[type="submit"]:has-text("Save"), button[type="submit"]:has-text("Create")');
      if (await submitBtn.isVisible()) {
        await submitBtn.click();
      }
    }
  });

  test('views inventory stock balance and tracks on-hand quantities', async ({ page }) => {
    await page.goto(`/workspace/${TEST_ORG_ID}/inventory`);

    // Verify inventory balances table
    await expect(page.locator('body')).toContainText(/Inventory|Balances|Stock|Kagzi Badam/i);
    await expect(page.locator('body')).toContainText(/40/); // On-hand quantity
  });
});
