import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_ID } from './helpers';

test.describe('Team & Settings (R9)', () => {
  test('Owner sees the team with roles and the permission table', async ({ page }) => {
    await setupMockApi(page, 'owner');
    await page.goto(`/workspace/${TEST_ORG_ID}/team`);

    await expect(page.getByRole('heading', { name: 'Team' })).toBeVisible();
    await expect(page.getByText('(you)')).toBeVisible();
    await expect(page.getByLabel('Role for Bilal Counter')).toHaveValue('staff');
    await expect(page.getByRole('heading', { name: 'What each role can do' })).toBeVisible();
  });

  test('Staff cannot open Team but can use Settings for their own account', async ({ page }) => {
    await setupMockApi(page, 'staff');
    await page.goto(`/workspace/${TEST_ORG_ID}/team`);
    await expect(page.getByRole('heading', { name: 'Only Owners can manage the team' })).toBeVisible();

    await page.getByRole('link', { name: /^Settings/ }).first().click();
    await expect(page).toHaveURL(new RegExp(`/workspace/${TEST_ORG_ID}/settings`));
    await expect(page.getByRole('heading', { name: 'Security' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Business profile' })).toHaveCount(0);
  });
});
