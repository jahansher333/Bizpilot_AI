# Test Boundary

Test categories are organized as:

- unit/: deterministic domain rules and calculations.
- integration/: API, PostgreSQL, repositories, and transactions.
- security/: authentication, authorization, IDOR, and tenant isolation.
- ai/: tool authorization, grounding, and evaluation.
- e2e/: approved critical browser workflows.

FND-001 adds the structure only. Test implementation begins with the relevant approved task.

## Test database (safety guard)

Integration and security tests write users, organizations and records, so they run only against a
local, disposable PostgreSQL database:

- Set `TEST_DATABASE_URL` in your shell or the repo-root `.env`, e.g.
  `TEST_DATABASE_URL=postgresql://bizpilot_test:<password>@localhost:5432/bizpilot_test`, then apply
  migrations to that database.
- The host must be `localhost`, `127.0.0.1`, `::1` or the docker-compose `postgres` service.
  Any other host stops pytest before a single test runs (`tests/db_guard.py`).
- The application's `BIZPILOT_DATABASE__URL` is never used by the test suite, even if it is set.
  Before this guard (until 2026-10-07) tests read it from `.env` and wrote test users to the shared
  Neon database.
- Without `TEST_DATABASE_URL`, database-backed tests are skipped and the rest still run.
