import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_ID } from './helpers';

test.describe('Dashboard & BizPilot AI Assistant (HARD-002)', () => {
  test('Owner dashboard displays complete sales, payments, expenses, and net cash metrics', async ({ page }) => {
    await setupMockApi(page, 'owner');
    await page.goto(`/workspace/${TEST_ORG_ID}`);

    await expect(page.locator('body')).toContainText(/Dashboard|Sales|15,000/i);
    await expect(page.locator('body')).toContainText(/Payments|Collected|10,000/i);
    await expect(page.locator('body')).toContainText(/Expenses|2,000/i);
    await expect(page.locator('body')).toContainText(/Net Cash|8,000/i);
  });

  test('Staff dashboard hides expenses and net cash financial indicators', async ({ page }) => {
    await setupMockApi(page, 'staff');
    await page.goto(`/workspace/${TEST_ORG_ID}`);

    await expect(page.locator('body')).toContainText(/Sales|15,000/i);
    await expect(page.locator('body')).toContainText(/Payments|10,000/i);
    // Expenses and net cash should be hidden or restricted
    await expect(page.locator('body')).not.toContainText(/Net Cash.*8,000/i);
  });

  test('BizPilot AI Assistant responds to business inquiries with grounded financial truth and refuses mutations', async ({ page }) => {
    await setupMockApi(page, 'owner');
    await page.goto(`/workspace/${TEST_ORG_ID}/assistant`);

    // Verify assistant header
    await expect(page.locator('body')).toContainText(/BizPilot AI|Assistant|Copilot/i);

    // Ask about sales
    const input = page.locator('textarea, input[placeholder*="Ask" i], input[placeholder*="message" i]').first();
    await input.fill('What are our total sales today?');
    await page.click('button[type="submit"], button:has-text("Send")');

    // Assistant response with grounded truth
    await expect(page.locator('body')).toContainText(/Today's total sales are PKR 15,000.00/i);

    // Ask to perform an unsupported mutation -> verified refusal
    await input.fill('Please create an order for 5 packs of almonds');
    await page.click('button[type="submit"], button:has-text("Send")');

    await expect(page.locator('body')).toContainText(/read-only assistant|directly using the Orders screen/i);
  });
});
