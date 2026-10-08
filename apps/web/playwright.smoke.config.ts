import { defineConfig, devices } from '@playwright/test';
import { assertLocalSmokeDatabase } from './tests/smoke/smoke-db';

/**
 * Smoke test against the REAL API and a REAL PostgreSQL database (no mocks).
 * Run with: SMOKE_DATABASE_URL=postgresql://user@127.0.0.1:5433/bizpilot_smoke npm run test:smoke
 * The database must be local and disposable: it is wiped and re-migrated before every run.
 * Requires a production build of the web app (npm run build).
 */
const SMOKE_DATABASE_URL = assertLocalSmokeDatabase(process.env.SMOKE_DATABASE_URL);
const WEB_PORT = 3100;
const API_PORT = 8000; // the web build calls NEXT_PUBLIC_API_URL (http://localhost:8000)

export default defineConfig({
  testDir: './tests/smoke',
  globalSetup: './tests/smoke/global-setup.ts',
  timeout: 120_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: 'retain-on-failure',
    viewport: { width: 1280, height: 800 },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // Never reuse an already running API: it might be connected to a real database.
      command: `python -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT} --loop asyncio:SelectorEventLoop`,
      cwd: '../api',
      url: `http://127.0.0.1:${API_PORT}/ready`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        BIZPILOT_ENVIRONMENT: 'local',
        BIZPILOT_DEBUG: 'false',
        BIZPILOT_DATABASE__URL: SMOKE_DATABASE_URL,
        BIZPILOT_AUTH__SIGNING_SECRET: 'smoke-test-only-signing-secret-not-for-production',
        BIZPILOT_AUTH__ACCESS_TOKEN_MINUTES: '60',
        BIZPILOT_AI__ENABLED: 'false',
        BIZPILOT_CORS_ORIGINS: JSON.stringify([`http://localhost:${WEB_PORT}`, `http://127.0.0.1:${WEB_PORT}`]),
        BIZPILOT_LOGGING__LEVEL: 'WARNING',
      },
    },
    {
      command: `npm run start -- -p ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
