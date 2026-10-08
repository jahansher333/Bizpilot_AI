import { test, expect } from '@playwright/test';
import { setupMockApi, TEST_ORG_ID } from './helpers';

// SEC-P1 F3: the production server sends the CSP and hardening headers, and the real pages run
// under that policy without a single CSP violation.
test.describe('Security headers', () => {
  test('pages are served with the CSP and hardening headers', async ({ page }) => {
    const response = await page.goto('/login');
    const headers = response!.headers();
    expect(headers['content-security-policy']).toContain("frame-ancestors 'none'");
    expect(headers['content-security-policy']).toContain("object-src 'none'");
    expect(headers['content-security-policy']).not.toContain('unsafe-eval');
    expect(headers['referrer-policy']).toBe('no-referrer');
    expect(headers['x-content-type-options']).toBe('nosniff');
    expect(headers['x-frame-options']).toBe('DENY');
  });

  test('signed-in pages run without CSP violations', async ({ page }) => {
    // Record every violation the browser reports, from before any page script runs.
    await page.addInitScript(() => {
      const seen: string[] = [];
      (window as unknown as { __cspViolations: string[] }).__cspViolations = seen;
      document.addEventListener('securitypolicyviolation', (e) => seen.push(`${e.violatedDirective} ${e.blockedURI}`));
    });
    await setupMockApi(page, 'owner');
    const violations: string[] = [];
    for (const path of [`/workspace/${TEST_ORG_ID}`, `/workspace/${TEST_ORG_ID}/orders`, `/workspace/${TEST_ORG_ID}/catalog`, `/workspace/${TEST_ORG_ID}/assistant`, '/login']) {
      await page.goto(path);
      // Rendered app content means hydration, the inline scripts and the first API calls have run.
      await expect(page.getByRole('heading').first()).toBeVisible();
      violations.push(...(await page.evaluate(() => (window as unknown as { __cspViolations: string[] }).__cspViolations)));
    }
    expect(violations).toEqual([]);
  });
});
