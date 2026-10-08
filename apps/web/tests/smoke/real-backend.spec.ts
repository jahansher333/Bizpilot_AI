import { test, expect, type Page, type APIRequestContext } from '@playwright/test';

/**
 * End-to-end smoke test: real browser → real web build → real API → real PostgreSQL. No mocks.
 * Every money/stock figure the UI shows is also checked directly against the API.
 */
const API = 'http://localhost:8000';
const stamp = Date.now();
const PASSWORD = 'Smoke-test-pass-2026!';
const OWNER = { name: 'Smoke Owner', email: `owner.${stamp}@example.com` };
const STAFF = { name: 'Smoke Staff', email: `staff.${stamp}@example.com` };
const ORG_NAME = `Smoke Traders ${stamp}`;

/**
 * The access token lives only in the page's memory and the refresh token is an HttpOnly cookie
 * (SEC-P1 F3), so neither can be read from storage. The test keeps the latest access token each
 * page received from /api/auth/login or /api/auth/refresh, exactly as the app does.
 */
const accessTokens = new WeakMap<Page, string>();

function trackSession(page: Page): Page {
  page.on('response', async (res) => {
    if (!/\/api\/auth\/(login|refresh)$/.test(res.url()) || res.status() !== 200) return;
    try {
      const body = (await res.json()) as { access_token?: string; refresh_token?: string };
      expect(body.refresh_token, 'refresh token never in a response body').toBeUndefined();
      if (body.access_token) accessTokens.set(page, body.access_token);
    } catch {
      // The page navigated away before the body was read; the next refresh will record a token.
    }
  });
  return page;
}

async function token(page: Page): Promise<string> {
  await expect.poll(() => accessTokens.get(page), { message: 'signed in' }).toBeTruthy();
  return accessTokens.get(page)!;
}

/** No token may ever be readable by page scripts: not in storage, not in document.cookie. */
async function expectNoScriptReadableTokens(page: Page) {
  const exposed = await page.evaluate(() => ({
    storage: JSON.stringify({ ...localStorage, ...sessionStorage }),
    cookies: document.cookie,
  }));
  expect(exposed.storage).not.toMatch(/eyJ|bizpilot_access_token|bizpilot_refresh_token/);
  expect(exposed.cookies).not.toContain('bizpilot_refresh');
  const refresh = (await page.context().cookies()).find((c) => c.name === 'bizpilot_refresh');
  expect(refresh, 'refresh cookie set').toBeTruthy();
  expect(refresh).toMatchObject({ httpOnly: true, secure: true, sameSite: 'Strict', path: '/api/auth' });
}

async function apiGet(request: APIRequestContext, page: Page, path: string) {
  const res = await request.get(`${API}${path}`, { headers: { Authorization: `Bearer ${await token(page)}` } });
  return { status: res.status(), body: res.ok() ? await res.json() : null };
}

async function register(page: Page, user: { name: string; email: string }) {
  await page.goto('/register');
  await page.locator('#rg-name').fill(user.name);
  await page.locator('#rg-email').fill(user.email);
  await page.locator('#rg-pw').fill(PASSWORD);
  await page.locator('#rg-pw2').fill(PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
}

test('owner runs a day of business end to end against the real backend', async ({ page, browser, request }) => {
  let orgId = '';
  let productId = '';
  let customerId = '';
  let firstOrderId = '';
  const stockOf = async () => (await apiGet(request, page, `/api/organizations/${orgId}/inventory/balances/${productId}`)).body.on_hand_quantity as number;
  const today = async () => (await apiGet(request, page, `/api/organizations/${orgId}/dashboard?period=today`)).body;

  trackSession(page);

  await test.step('1. register the owner and create a business', async () => {
    await register(page, OWNER);
    await page.getByRole('button', { name: /Get started/ }).click();
    await page.locator('#display_name').fill(ORG_NAME);
    await page.getByRole('button', { name: 'Continue' }).click();
    await page.getByRole('button', { name: 'Create workspace' }).click();
    await page.getByRole('link', { name: 'Go to dashboard' }).click();
    await expect(page).toHaveURL(/\/workspace\/[0-9a-f-]{36}$/);
    orgId = page.url().split('/workspace/')[1];
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expectNoScriptReadableTokens(page);
  });

  await test.step('2. add a product with opening stock 10', async () => {
    await page.goto(`/workspace/${orgId}/catalog`);
    await page.getByRole('button', { name: 'Add product' }).first().click();
    await page.locator('#ap-name').fill('Smoke Rice 5kg');
    await page.locator('#ap-code').fill(`SMK-${stamp % 100000}`);
    await page.locator('#ap-price').fill('100');
    await page.locator('#ap-unit').fill('bag');
    await page.locator('#ap-stock').fill('10');
    await page.getByRole('button', { name: 'Create product' }).click();
    await expect(page.getByText('Smoke Rice 5kg').first()).toBeVisible();
    const products = (await apiGet(request, page, `/api/organizations/${orgId}/products?limit=10`)).body.items;
    productId = products.find((p: { name: string }) => p.name === 'Smoke Rice 5kg').id;
    expect(await stockOf()).toBe(10);
  });

  await test.step('3. add a customer', async () => {
    await page.goto(`/workspace/${orgId}/customers`);
    await page.getByRole('button', { name: 'Add customer' }).first().click();
    await page.locator('#cust-name').fill('Smoke Customer');
    await page.locator('#cust-phone').fill('0300 1112223');
    await page.getByRole('dialog').getByRole('button', { name: 'Add customer' }).click();
    await expect(page.getByRole('link', { name: 'Smoke Customer' }).first()).toBeVisible();
    customerId = (await apiGet(request, page, `/api/organizations/${orgId}/customers?limit=10`)).body.items[0].id;
  });

  await test.step('4. sell 2 bags from the POS: stock 10 → 8, sales PKR 200', async () => {
    await page.goto(`/workspace/${orgId}/orders/new`);
    const tile = page.getByRole('button', { name: /Smoke Rice 5kg, PKR 100, 10 in stock/ });
    await tile.click();
    await page.getByRole('button', { name: /Smoke Rice 5kg, PKR 100/ }).click();
    await page.getByLabel('Customer').selectOption(customerId);
    await page.getByRole('button', { name: /Complete order/ }).click();
    const done = page.getByRole('dialog', { name: /Order .+ completed/ });
    await expect(done).toBeVisible();
    firstOrderId = (await done.getByRole('link', { name: 'View order' }).getAttribute('href'))!.split('/orders/')[1];
    expect(await stockOf()).toBe(8);
    const d = await today();
    expect(d.sales).toMatchObject({ order_count: 1, total_sales_minor: 20000 });
  });

  await test.step('5. record a part payment from the order: balance PKR 150', async () => {
    await page.getByRole('dialog', { name: /completed/ }).getByRole('link', { name: 'Record payment' }).click();
    const sheet = page.getByRole('dialog', { name: 'Record payment' });
    await expect(sheet.getByText(/total is PKR 200 · nothing paid yet/)).toBeVisible();
    await expect(sheet.getByLabel('Amount')).toHaveValue('200');
    await sheet.getByLabel('Amount').fill('50');
    await sheet.getByRole('button', { name: 'Record PKR 50' }).click();
    await expect(sheet.getByRole('heading', { name: 'Payment recorded' })).toBeVisible();
    const bal = (await apiGet(request, page, `/api/organizations/${orgId}/customers/balances?customer_id=${customerId}`)).body.items[0];
    expect(bal).toMatchObject({ total_orders_minor: 20000, total_payments_minor: 5000, balance_minor: 15000 });
    await page.goto(`/workspace/${orgId}/orders/${firstOrderId}`);
    await expect(page.getByText('Part paid')).toBeVisible();
  });

  await test.step('6. record an expense: net cash PKR 50 − 30 = 20', async () => {
    await page.goto(`/workspace/${orgId}/expenses`);
    await page.getByRole('button', { name: /Record expense/ }).first().click();
    const dialog = page.getByRole('dialog', { name: 'Record expense' });
    await dialog.getByLabel('Description').fill('Smoke electricity');
    await dialog.getByLabel('Amount').fill('30');
    await dialog.getByRole('button', { name: 'Review expense' }).click();
    await dialog.getByRole('button', { name: /Confirm & record/ }).click();
    await expect(page.getByRole('button', { name: 'Smoke electricity' }).first()).toBeVisible();
    const d = await today();
    expect(d.expenses).toMatchObject({ total_expenses_minor: 3000 });
    expect(d.net_cash).toMatchObject({ net_cash_minor: 2000 });
  });

  await test.step('7. correct the order 2 → 1 bag: replacement created, stock 9', async () => {
    await page.goto(`/workspace/${orgId}/orders/${firstOrderId}`);
    await page.getByRole('button', { name: /Correct order/ }).click();
    await page.getByRole('button', { name: 'Decrease Smoke Rice 5kg' }).click();
    await page.getByLabel(/Reason/).fill('Customer took 1 bag');
    await page.getByRole('button', { name: 'Review correction' }).click();
    await page.getByRole('alertdialog').getByRole('button', { name: 'Submit correction' }).click();
    await expect(page).not.toHaveURL(new RegExp(firstOrderId));
    await expect(page.getByText(/This order replaces/)).toBeVisible();
    expect(await stockOf()).toBe(9);
    const original = (await apiGet(request, page, `/api/organizations/${orgId}/orders/${firstOrderId}`)).body;
    expect(original.status).toBe('corrected');
  });

  await test.step('8. sell 1 more bag, then void it: stock 9 → 8 → 9', async () => {
    await page.goto(`/workspace/${orgId}/orders/new`);
    await page.getByRole('button', { name: /Smoke Rice 5kg, PKR 100, 9 in stock/ }).click();
    await page.getByRole('button', { name: /Complete order/ }).click();
    const done = page.getByRole('dialog', { name: /completed/ });
    const orderId = (await done.getByRole('link', { name: 'View order' }).getAttribute('href'))!.split('/orders/')[1];
    expect(await stockOf()).toBe(8);
    await page.goto(`/workspace/${orgId}/orders/${orderId}`);
    await page.getByRole('button', { name: /Void order/ }).click();
    const dialog = page.getByRole('alertdialog');
    await dialog.getByLabel(/Reason/).fill('Smoke test void');
    await dialog.getByRole('button', { name: 'Void order' }).click();
    await expect(page.getByText(/^Voided/).first()).toBeVisible();
    expect(await stockOf()).toBe(9);
  });

  await test.step('9. invite a Staff member: Staff cannot see expenses (UI and API)', async () => {
    const staffContext = await browser.newContext();
    const staff = trackSession(await staffContext.newPage());
    await register(staff, STAFF);

    await page.goto(`/workspace/${orgId}/team`);
    await page.getByRole('button', { name: /Invite member/ }).click();
    const invite = page.getByRole('dialog', { name: 'Invite member' });
    await invite.getByLabel('Email').fill(STAFF.email);
    await invite.getByRole('radio', { name: /Staff/ }).check();
    await invite.getByRole('button', { name: 'Send invite' }).click();
    await expect(page.getByText(STAFF.email).first()).toBeVisible();

    await staff.goto('/workspaces');
    await staff.getByRole('button', { name: new RegExp(`Accept invitation to ${ORG_NAME}`, 'i') }).click();
    await expect(staff).toHaveURL(new RegExp(`/workspace/${orgId}`));
    await staff.goto(`/workspace/${orgId}/expenses`);
    await expect(staff.getByRole('heading', { name: 'Expenses are visible to Owners and Managers' })).toBeVisible();
    expect((await apiGet(request, staff, `/api/organizations/${orgId}/expenses`)).status).toBe(403);
    await staffContext.close();
  });

  await test.step('12. a full reload restores the session from the HttpOnly cookie alone', async () => {
    const restored = page.waitForResponse((r) => r.url().endsWith('/api/auth/refresh'));
    await page.reload();
    expect((await restored).status()).toBe(200);
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toHaveCount(0);
    await expectNoScriptReadableTokens(page);
  });

  await test.step('11. leaving pages before the session finishes loading keeps the user signed in', async () => {
    // Regression for the 2026-10-07 smoke finding: an aborted profile load used to wipe the session.
    for (let i = 0; i < 3; i++) {
      await page.goto(`/workspace/${orgId}`, { waitUntil: 'commit' });
    }
    await page.goto(`/workspace/${orgId}/orders`);
    await expect(page.getByRole('heading', { name: 'Orders', level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toHaveCount(0);
  });

  await test.step('10. BizPilot AI (disabled here) answers calmly instead of failing', async () => {
    await page.goto(`/workspace/${orgId}/assistant`);
    await page.getByRole('button', { name: /How are sales doing today/ }).click();
    await expect(page.getByText(/BizPilot AI Assistant is currently disabled/)).toBeVisible();
    // No failure notice (unavailable / timeout / offline) — the page also has Next's empty route announcer alert.
    await expect(page.getByText(/temporarily unavailable|took longer than expected|Couldn’t reach BizPilot AI/)).toHaveCount(0);
  });
});
