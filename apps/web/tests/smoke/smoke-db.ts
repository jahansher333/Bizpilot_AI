import { execFileSync } from 'node:child_process';
import path from 'node:path';

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]', '::1']);

/** The smoke database is wiped every run, so it must be on this machine. Returns the URL. */
export function assertLocalSmokeDatabase(url: string | undefined): string {
  if (!url) {
    throw new Error('Set SMOKE_DATABASE_URL to a local, disposable PostgreSQL database (it is wiped before every smoke run).');
  }
  const host = new URL(url).hostname.toLowerCase();
  if (!LOCAL_HOSTS.has(host)) {
    throw new Error(`Refusing to run the smoke test against database host '${host}': SMOKE_DATABASE_URL must be local and disposable.`);
  }
  return url;
}

/** Drops every table and re-applies all migrations, using the repo's Alembic setup. */
export function resetSmokeDatabase(url: string): void {
  const repoRoot = path.resolve(__dirname, '../../../..');
  const env = { ...process.env, BIZPILOT_DATABASE__URL: url };
  for (const target of [['downgrade', 'base'], ['upgrade', 'head']]) {
    execFileSync('python', ['-m', 'alembic', ...target], { cwd: repoRoot, env, stdio: 'pipe' });
  }
}
