import { test, expect } from '@playwright/test';

test.describe('Page states (R10a)', () => {
  test('an unknown URL shows the not-found page with a way back', async ({ page }) => {
    const response = await page.goto('/this-page-does-not-exist');
    expect(response?.status()).toBe(404);
    await expect(page.getByRole('heading', { name: 'We couldn’t find that page' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Go to dashboard' })).toHaveAttribute('href', '/workspaces');
  });
});
