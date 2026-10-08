# Azure Deployment (P0 pilot)

**Status:** Draft for HARD-008 — hosting target approved by the founder on 2026-10-08 (Azure).
Resource names, region, database tier and secret storage below are proposals until approved.

## Shape

| Piece | Azure service (proposed) | Image / source |
| --- | --- | --- |
| API | Azure Container Apps, external ingress, target port 8000 | `apps/api/Dockerfile` (build from repo root) |
| Web | Azure Container Apps, external ingress, target port 3000 | `apps/web/Dockerfile` (build from `apps/web`) |
| Migrations | Container Apps **Job** (manual trigger) using the API image, command `alembic upgrade head` | same API image |
| Database | Azure Database for PostgreSQL – Flexible Server, PostgreSQL 16 | — |
| Images | Azure Container Registry | — |
| Secrets | Container Apps secrets, or Key Vault references | — |
| Email | Brevo, SendGrid or Resend over SMTP | — |

The browser calls the API directly at its own https origin (`NEXT_PUBLIC_API_URL`), not through the
Next.js `/api` proxy. Going through the proxy would make every request reach the API from the web
container's address, and the per-IP rate limits would then count all users as one client.

### Production domains

Decided 2026-10-09: web at `https://app.bizpilot.ai`, API at `https://api.bizpilot.ai`.

| Setting | Value |
| --- | --- |
| Web build arg `NEXT_PUBLIC_API_URL` | `https://api.bizpilot.ai` |
| `BIZPILOT_CORS_ORIGINS` | `["https://app.bizpilot.ai"]` |
| `BIZPILOT_EMAIL__FRONTEND_BASE_URL` | `https://app.bizpilot.ai` |

The refresh cookie is deliberately **host-only** on `api.bizpilot.ai` (no `Domain` attribute).
`app.bizpilot.ai` and `api.bizpilot.ai` are the same site, so `SameSite=Strict` already lets the
browser send it with the app's API calls; `Domain=.bizpilot.ai` would add nothing for the app but
would also send the 30-day refresh token to every other `*.bizpilot.ai` host.

### Session cookie: web and API must be on the same site

Since SEC-P1 F3 the refresh token is an `HttpOnly; Secure; SameSite=Strict` cookie set by the API
(`bizpilot_refresh`, `Path=/api/auth`); the access token stays in the page's memory. Browsers only
send a `SameSite=Strict` cookie on requests between the **same site** (same registrable domain), so:

- Serve both apps from subdomains of one domain over https, e.g. `app.<domain>` and `api.<domain>`.
- Do not rely on the default `*.azurecontainerapps.io` hostnames for the two apps: they are not
  guaranteed to count as the same site, and if they do not, sign-in works but every page load signs
  the user out (the browser never sends the cookie to `/api/auth/refresh`).
- `BIZPILOT_CORS_ORIGINS` must list the web origin exactly: CORS now allows credentials for it, and
  `/api/auth/refresh` and `/api/auth/logout` reject browser requests from any other `Origin`.

## Build

```bash
docker build -f apps/api/Dockerfile -t <registry>.azurecr.io/bizpilot-api:<tag> .
docker build -t <registry>.azurecr.io/bizpilot-web:<tag> \
  --build-arg NEXT_PUBLIC_API_URL=https://<api-domain> apps/web
```

`NEXT_PUBLIC_API_URL` is compiled into the browser bundle, so staging and production need separate
web images.

## API configuration

Set as Container App secrets/environment variables. Production startup rejects placeholders, debug
mode, non-TLS database connections, `*`/http CORS origins and non-TLS SMTP.

| Variable | Value |
| --- | --- |
| `BIZPILOT_ENVIRONMENT` | `production` (image default) |
| `BIZPILOT_DATABASE__URL` | `postgresql://<user>:<password>@<server>.postgres.database.azure.com:5432/<db>?sslmode=require` (secret) |
| `BIZPILOT_AUTH__SIGNING_SECRET` | 32+ random characters (secret) |
| `BIZPILOT_CORS_ORIGINS` | `["https://<web-domain>"]` |
| `BIZPILOT_EMAIL__SMTP_HOST` / `_PORT` / `_SECURITY` | see provider table in `apps/api/.env.example`; `587`, `starttls` |
| `BIZPILOT_EMAIL__SMTP_USERNAME` / `_PASSWORD` | provider login and key (password is a secret) |
| `BIZPILOT_EMAIL__FROM_ADDRESS` | address on a domain verified with the provider |
| `BIZPILOT_EMAIL__FRONTEND_BASE_URL` | `https://<web-domain>` |
| `BIZPILOT_AI__ENABLED` / `_API_KEY` / `_MODEL` | keep `false` until the AI provider's data terms are reviewed |
| `BIZPILOT_LOGGING__JSON_LOGS` | `true` |
| `FORWARDED_ALLOW_IPS` | Image default `10.0.0.0/8` (Azure private range, founder decision 2026-10-09). Override with the exact ingress subnet once known (the Container Apps environment's infrastructure subnet, comma-separated if several). If that subnet is outside `10.0.0.0/8` (e.g. `172.16.0.0/12`), the override is **required**, or every client is counted as the ingress IP. The image refuses to start with `*` or an empty value: trusting every proxy makes uvicorn take the client-written left-most `X-Forwarded-For` entry, which defeats every per-IP rate limit. |
| `BIZPILOT_AUTH__LOGIN_ACCOUNT_MAX_FAILURES` / `_COOLDOWN_MINUTES` | defaults `10` / `15`: consecutive failed logins per account (any IP) before a temporary cooldown |

## Probes

| Probe | Path |
| --- | --- |
| Liveness | `GET /healthz` |
| Readiness | `GET /readyz` (checks the database) |

## Release order

1. Build and push both images.
2. Run the migration job with the new API image and wait for it to succeed.
3. Update the API container app, then the web container app.
4. Check `/readyz`, sign in, and request a password reset to a real inbox.

## Still to decide (not covered by this draft)

- Azure region, resource names and PostgreSQL tier.
- Backup retention and the RPO/RTO targets in `PRODUCTION-READINESS-REVIEW.md` §4.
- Monitoring and alerting (for example Azure Monitor / Application Insights alerts on `/readyz`
  failures and 5xx rates).
- Custom domains and TLS certificates.
