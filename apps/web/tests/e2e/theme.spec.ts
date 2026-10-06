import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_ID } from './helpers';

test.describe('Dark mode (R10c)', () => {
  test.use({ colorScheme: 'dark' });

  test('follows the device and is set before the page renders', async ({ page }) => {
    await setupMockApi(page, 'owner');
    await page.goto(`/workspace/${TEST_ORG_ID}`);
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(bg).toBe('rgb(13, 15, 16)');
  });

  test('a Light choice in Settings overrides the device and survives a reload', async ({ page }) => {
    await setupMockApi(page, 'owner');
    await page.goto(`/workspace/${TEST_ORG_ID}/settings`);
    await page.getByRole('button', { name: 'Your account' }).click();
    await page.getByRole('radio', { name: /Light/ }).check();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  });
});

test('side panels and dialogs cover the whole window', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await setupMockApi(page, 'owner');
  await page.goto(`/workspace/${TEST_ORG_ID}/payments`);
  await page.getByRole('button', { name: 'Record payment' }).first().click();
  const box = await page.locator('.sheet-wrap').boundingBox();
  expect(box).toMatchObject({ y: 0, height: 800 });
});
